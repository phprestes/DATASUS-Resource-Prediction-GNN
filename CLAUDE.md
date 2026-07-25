# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Undergraduate research project (Iniciação Científica) on Brazilian CNES data (National Registry of Health Establishments, DATASUS). Goal: turn the raw monthly CNES dumps into a [RelBench](https://relbench.stanford.edu/) relational-deep-learning dataset and train a heterogeneous GNN to predict hospital bed counts.

Code comments, print statements and docs are in **Portuguese**. Keep new code consistent with that.

Not a git repository (a `.gitignore` exists but no `.git`). No test suite, no linter, no `requirements.txt` — dependencies live only in `.venv`.

## Environment & commands

Python 3.12 in `.venv`. Package is installed editable as `meu_projeto_ic` (see [setup.py](setup.py)), so `src` is importable, but scripts still use absolute `from src.constant import ...` imports and **must be run from the project root as modules**:

```bash
source .venv/bin/activate

python -m src.extract      # download CNES ZIPs        -> data/01_raw
python -m src.to_sql       # ZIP CSVs -> DuckDB        -> data/02_intermediate
python -m src.to_parquet   # DuckDB -> cleaned Parquet -> data/03_primary
```

Each `__main__` block auto-discovers periods by globbing the previous stage's output, so re-running the chain needs no arguments. `src.extract`'s `__main__` is hardcoded to `["201701"]` — edit it or call `download_cnes_zips(periods)` directly. To pick periods explicitly, import the function in a notebook (notebook 01 does this).

Notebooks in [notebook/](notebook/) do `sys.path.append(Path.cwd().parent)` and are meant to run from that directory. Run order: `01_initial_analysis` (profiling, generates [docs/relatorio_analise_dados.md](docs/relatorio_analise_dados.md)) → `02_relacoes` (networkx graph of the schema from the data dictionary) → `03_relbench_modeling` (dataset → task → GNN training + naive-persistence baseline).

Key versions: relbench 2.1.1, torch 2.9.1, torch_geometric 2.7.0, duckdb 1.5.2, pandas 3.0.2, pyarrow 23.0.1.

## Architecture

### Pipeline stages (Kedro-style data layers)

`data/01_raw` (`BASE_DE_DADOS_CNES_{YYYYMM}.ZIP`) → `data/02_intermediate` (`sql_cnes_{YYYYMM}.duckdb`) → `data/03_primary` (`{YYYYMM}/{tableName}.parquet`) → relbench `Database`. `data/04_feature` exists but is unused.

Periods are always the 6-char string `YYYYMM` ("competência"). It is the partition key everywhere: filenames, DuckDB table suffixes, and primary-layer subfolders. The set used so far is `["201701", "201901", "202101", "202301", "202501"]`.

### `src/constant.py` is the schema contract

1298 lines, all hand-derived from [docs/DICIONARIO_DE_DADOS_CNES_2025.pdf](docs/DICIONARIO_DE_DADOS_CNES_2025.pdf). Five dicts/lists drive the whole pipeline; changing schema behavior means editing here, not the pipeline code:

- `FACT_TABLES` — allowlist of which CSVs get ingested at all (`to_sql`, `only_fact_tables=True`).
- `CNES_USEFUL_COLUMNS` — per-table column allowlist for the Parquet layer. A table absent here is silently skipped by `to_parquet`.
- `CNES_DTYPES` — per-column target types, expressed as pandas-ish strings (`'datetime64[ns]'`, `'Int64'`, `'float64'`) that `to_parquet` translates into DuckDB `TRY_CAST` / `try_strptime`.
- `CNES_PKEY` / `CNES_FKEY` — the relational graph fed to relbench `Table(pkey_col=..., fkey_col_to_pkey_table=...)`.

Path constants (`RAW_FOLDER`, `INTERMEDIATE_FOLDER`, `PRIMARY_FOLDER`, `TEMP_EXTRACT_DIR`) are derived from `BASE_DIR = parent of src/`.

### Naming and typing conventions to know

- CSVs inside the ZIP are named `{TableName}{YYYYMM}.csv`. [to_sql.py:43](src/to_sql.py#L43) recovers the base name with `stem_name[:-6]` (strip the period) to check against `FACT_TABLES`, but creates the DuckDB table under the **full suffixed name** (`tbEstabelecimento201701`). [to_parquet.py:35](src/to_parquet.py#L35) strips the suffix again to look up `CNES_USEFUL_COLUMNS`. Any change to the period width breaks both.
- Ingest uses `all_varchar=True`, `normalize_names=True`, `sep=';'`, `encoding='ISO_8859_1'`, `ignore_errors=True`. So the intermediate layer is **all strings with lowercase snake_case column names**; all real typing happens in `to_parquet` via `CNES_DTYPES`.
- `to_chardt_atualizacaoddmmyyyy` is the conventional timestamp column. Parsed as `%d/%m/%Y`; values before `1900-01-01` are nulled (CNES sentinel dates). `dataset.py` auto-detects it as relbench `time_col` when present.
- `reprocess` defaults are inconsistent across stages: `True` in `extract`/`to_sql`, `False` in `to_parquet`. Pass it explicitly.

### relbench layer

[src/dataset.py](src/dataset.py) — `CNESDataset.make_db(municipio_id=None)` builds the graph by globbing `data/03_primary/*/*.parquet`, so **all periods are unioned into one table per entity**; the period lives only in the timestamp column. `tbEstabelecimento` is the root node (pkey `co_unidade`).

The `municipio_id` argument is the main performance lever: it filters the root on `co_municipio_gestor`, then pushes an `isin(valid_unidades)` predicate down into every child table's pyarrow scan, extracting a municipal subgraph instead of loading the national dataset. Notebook 03 uses `"355030"` (São Paulo).

Tables are constructed with **pyarrow `Table` objects, not pandas DataFrames** (`Table(df=arrow_table)`). Downstream code must handle both — see the `hasattr(df_beds_pa, "select")` branch in [src/task.py:28](src/task.py#L28). Assume arrow unless proven otherwise.

[src/task.py](src/task.py) — `PredictBedsTask`, an `EntityTask` regression on `qt_exist` from `rlEstabComplementar` aggregated per `co_unidade` over a forward window of `timedelta=730 days`. That 2-year window is tied to the 2-year spacing of the ingested periods.

[src/model.py](src/model.py) — `BaseGNN` (2× `SAGEConv` + LayerNorm + dropout) wrapped by `to_hetero` inside `DynamicHeteroGNN`, with a per-node-type `Linear(-1, hidden)` projection dict to reconcile heterogeneous feature widths. Plus module-level `train`/`test` helpers that operate on a full `HeteroData` batch. Note `test()` currently reuses `train_mask` — the real val/test split logic lives inline in notebook 03, not in `model.py`.

### `archieved/`

Pre-refactor monolithic scripts. They target the **old relbench API** (`relbench.data`, `relbench.data.task.NodeTask`, `RelBenchEncoder`) which no longer exists in 2.1.1. Useful only as historical reference for the CSV→table mapping intent; do not copy code from them.
