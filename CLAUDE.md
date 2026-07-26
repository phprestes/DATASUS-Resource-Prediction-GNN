# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Undergraduate research project (Iniciação Científica) on Brazilian CNES data (National Registry of Health Establishments, DATASUS). It asks whether resource scarcity in a municipal health network can be identified and anticipated from the network's *structure* — not just from each establishment's own attributes.

Code comments, docstrings, prints and docs are in **Portuguese**. Keep new code consistent with that. Commit messages are in Portuguese too.

## Read the docs first

Four Markdown files in [docs/](docs/) are the project's contract. They are not summaries of the code — the code is downstream of them.

- **[docs/01-selecao-tabelas.md](docs/01-selecao-tabelas.md)** — the **source of truth for the schema**. [src/schema.py](src/schema.py) parses it at import time and derives `FACT_TABLES`, `CNES_EXTRACT_COLUMNS`, `CNES_USEFUL_COLUMNS`, `CNES_DTYPES`, `CNES_PKEY`, `CNES_NATURAL_KEY`, `CNES_FKEY`. **Editing this file changes the pipeline.** There is no second list in code to keep in sync — that was the bug the refactor removed.
- **[docs/02-metodologia.md](docs/02-metodologia.md)** — research question, operational definition of scarcity, sample, temporal semantics, the four tracks, evaluation protocol.
- **[docs/03-decisoes.md](docs/03-decisoes.md)** — 26 numbered decisions with the evidence behind each and what was rejected. When something in the code looks surprising, the reason is usually a D-nn entry.

`docs/SelecaoTabelas_v1.pdf` and `_v2.pdf` are historical records, superseded by `01-selecao-tabelas.md`. `docs/CNES_GNN-2.pdf` is the original project proposal; the code has deliberately diverged from it (see D-01).

## Environment & commands

Python 3.12 in `.venv`, managed by **uv** (there is no `pip` inside it). Package installed editable as `meu-projeto-ic`.

```bash
source .venv/bin/activate

# ETL. Each stage reads the previous layer and writes the next.
python -m src.extract              # 9 annual ZIPs -> data/01_raw   (~2.9 GB)
python -m src.extract 202501       # or specific competências
python -m src.to_sql               # ZIP CSVs -> DuckDB per period  -> data/02_intermediate
python -m src.to_parquet           # DuckDB -> typed Parquet        -> data/03_primary
python -m src.changes              # snapshot diffs -> change events -> data/04_feature

python -m pytest tests/ -q         # full suite
python -m pytest tests/test_schema.py::test_fact_tables_e_useful_columns_nao_podem_divergir
```

All ETL stages default to `reprocess=False` (skip what exists) — the series is several GB, so re-downloading by accident is expensive. Pass `reprocess=True` explicitly to redo work.

`VIRTUAL_ENV=.venv uv pip install -e .` to reinstall. `pyg-lib`, `torch-scatter` and `torch-sparse` are not on PyPI and need the wheel index matched to the torch version — instructions are in the header of `requirements.txt`.

## Architecture

### Data layers

`data/01_raw` (`BASE_DE_DADOS_CNES_{YYYYMM}.ZIP`) → `data/02_intermediate` (`sql_cnes_{YYYYMM}.duckdb`) → `data/03_primary` (`{YYYYMM}/{tabela}.parquet`) → `data/04_feature/changes/{tabela}/{periodo}.parquet`. Nothing under `data/` is versioned; it is all reproducible from stage 1.

The period is always the 6-char string `YYYYMM` ("competência") and is the partition key everywhere. The canonical sample is `src.extract.PERIODOS_ANUAIS` — January of each year, 2017–2025, nine snapshots and eight transitions (D-04).

### Time is the subtle part

Read this before touching anything temporal. A competência ZIP is a **snapshot of current state**, not an event log, and it keeps only the **last** `dt_atualizacao` per row. So:

- `to_chardt_atualizacaoddmmyyyy` is **right-censored**. Using it as a graph `time_col` — as the old code did — assigns each row an instant that depends on when the snapshot was taken.
- Changes between two snapshots are unrecoverable. The study's real temporal resolution is the snapshot spacing, not the date column's granularity.
- The unit of analysis is therefore the **transition** `t → t+1` ([src/changes.py](src/changes.py)), and the graph's `time_col` is the **snapshot date** (Jan 1 of the competência), which is exact and uniform. Events supply labels; snapshots supply state. See D-08.

### Modules

| Module | Role |
|---|---|
| [src/paths.py](src/paths.py) | data layer locations, doc locations |
| [src/schema.py](src/schema.py) | parses `01-selecao-tabelas.md`; strict, fails the import on malformed input |
| [src/extract.py](src/extract.py), [src/to_sql.py](src/to_sql.py), [src/to_parquet.py](src/to_parquet.py) | the three ETL stages |
| [src/changes.py](src/changes.py) | snapshot diffing, change events, change-rate measurement |
| [src/splits.py](src/splits.py) | the single temporal partition, consumed by all modelling tracks |
| [src/tasks.py](src/tasks.py) | label tables: acquisition (primary), quantity (secondary) |
| [src/baselines.py](src/baselines.py) | track 1 — five baselines with no structural information |
| [src/graph.py](src/graph.py) | tracks 2 and 3 — RelBench `Database`, and the geographic kNN graph |
| [src/gnn.py](src/gnn.py) | encoders, shared pair decoder, training loop |
| [src/metrics.py](src/metrics.py) | average precision, AUC, MAP@k, RMSE/MAE, results table |

`tools/build_selecao_inicial.py` is a one-shot migrator kept as a provenance record: it generated the first version of the selection doc by joining the old PDF, `src/constant.py` (read from git history — the file is deleted) and the empirical report. It refuses to overwrite the doc without `--force`.

### Conventions that will bite you

- **CSV naming.** Files inside the ZIP are `{TableName}{YYYYMM}.csv`. [to_sql.py](src/to_sql.py) strips the 6-char period to match `FACT_TABLES` but creates the DuckDB table under the **full suffixed name** (`tbEstabelecimento201701`); [to_parquet.py](src/to_parquet.py) strips it again. Changing the period width breaks both.
- **Everything is VARCHAR at the intermediate layer.** Ingest uses `all_varchar=True`, `normalize_names=True`, `sep=';'`, `encoding='ISO_8859_1'`. Typing happens only in `to_parquet`, driven by `CNES_DTYPES`. `datetime64[ns]` triggers `try_strptime` with `%d/%m/%Y` and nulls dates before 1900-01-01 (a CNES sentinel).
- **Three name spellings for the same thing.** Oracle dictionary (`RL_ESTAB_COMPLEMENTAR`), CSV/DuckDB (`rlEstabComplementar`), and date columns wrapped in the extraction's own SQL (`TO_CHAR(DT_ATUALIZACAO,'DD/MM/YYYY')` → `to_chardt_atualizacaoddmmyyyy`, sometimes with a table alias inside: `to_charadt_atualizacaoddmmyyyy`). Documented in `01-selecao-tabelas.md`.
- **`pkey` is not a row key.** `CNES_PKEY` is the *entity* key RelBench joins on (`co_unidade`) and is almost never unique — `rlEstabEquipamento` has one row per equipment, not per establishment. Row identity is `CNES_NATURAL_KEY`, declared per table where known.
- **Tables hold `pyarrow.Table`, not `pandas.DataFrame`.** Deliberate: the municipality filter is pushed into the Parquet scan. Call `.to_pandas()` explicitly; don't assume pandas.
- **`recorte` is the main cost lever.** [graph.py](src/graph.py) filters the root on `co_municipio_gestor` by IBGE-code prefix, then pushes the resulting `co_unidade` set as an `isin` predicate into every child table's scan. Without it you load the whole country.

### Comparability is the point of the design

All tracks consume the same `TabelaTarefa` and the same `ParticaoTemporal`, and all return the same `Previsao` dataclass, so `src.metrics.tabela_de_resultados` can put them in one table. **Never report a GNN number without the persistence baseline beside it** (D-11) — the previous version of the project reported training-set performance as test performance, and nothing caught it.

Track 1 must stay free of relational and spatial features. Adding neighbourhood aggregates to the baselines would erase the difference the experiment exists to measure.

## Numbers you should know before proposing anything

Measured on the nine annual snapshots, São Paulo. These constrain what is worth trying.

- **Scope is the state of São Paulo**, prefix `35` — 136k establishments, 645 municípios. It was the capital only; D-21 widened it because that nearly triples acquisition events and gives IBGE population non-zero variance. `recorte` is an IBGE-code *prefix*: `'355030'` gets the capital back, `None` the country.
- **Target.** `rlEstabEquipamento` yields 34,571 acquisition events across the eight transitions at state scope; `rlEstabComplementar` (beds) yields 688 in the capital alone. That is why the target moved (D-01, D-18).
- **Prevalence is 0.047%** at state scope — 73M candidates for 34k events. Two candidate-space restrictions were tested and rejected (D-19). Don't propose a third without measuring first. **MAP@k is the headline metric**, and D-24 shows why in practice: AP and MAP@10 rank the baselines differently.
- **The bar to beat is MAP@10 = 0.296** (`popularidade_item`), not the persistence floor. Persistence returns AP exactly equal to prevalence and AUC exactly 0.500 — if it ever doesn't, the harness is broken (D-24).
- **Results are in** (D-26, paired on 117k positionable establishments): `gnn_relacional` AP 0.00478 / MAP@10 0.213; `gnn_geografica` 0.00378 / 0.208; `gbdt_geral` 0.00280 / 0.252; `popularidade_item` 0.00215 / **0.296**; `persistencia` 0.00051 / 0.035. **The GNNs win AP and AUC and lose MAP@10** — they learned the establishment dimension, not the item dimension. The next experiment is a combined score (GNN + item-popularity log-odds); don't propose architecture changes before running it.
- **The paired table is the one that counts.** Prevalence is 0.0507% on positionable establishments vs 0.0428% overall — the subset is 18% richer in positives, so unpaired comparison flatters track 3.
- **Change rate is flat**: 0.082–0.112 per year, median 0.094, no pandemic spike. Annual density is settled (D-10).
- **Coordinates cover 85.7%** at state scope, 75.0% in the capital. D-17 said 57% — that was measured on six of nine snapshots and is superseded by D-22.
- **The schema drifts.** Three of 44 tables have columns that vanish and return, with 201901 the anomalous competência. Reading several Parquet files directly via DuckDB needs `union_by_name=true` (D-20).

## Memory is a hard constraint

The machine has 9 GB and building the state-scope task table once crashed the user's IDE. D-23 cut the table from 3.22 GB to 0.317 GB and the peak from 4.87 GB to 3.37 GB. Code touching the task table must not materialise `co_unidade` as strings or copy the frame whole — use `TabelaTarefa.codigos()` and `Previsao.mascara_de_entidades()`. Negative sampling (200:1) applies to **training only**; validation and test stay complete, or the measured prevalence is fiction.

## Reproducing the experiment

`python -m tools.roda_experimento` runs all three tracks and writes
`docs/resultados/{date}-trilhas-{recorte}.json` incrementally. ~45 min, 5.1 GB peak.
`--pular-gnn` stops after the baselines. The graph cutoff must be
`particao.antes_de_todos_os_rotulos`, never `fim_do_treino` — the latter puts the
label inside the graph (D-25), and `grafo_relacional_para_data` refuses the call
without the parameter for that reason.

## Notebooks

`00_analise_alvo` is the empirical gate — executed, all five verdicts closed, results recorded in D-18 to D-20. `01_perfil_dados` regenerates the profiling report from the primary layer. `02_relacoes` draws the schema graph from `schema.py` instead of a hand-written edge list. `03_modelagem` runs all three tracks against one partition. `04_recorte_e_dados_externos` measures the two things D-16 left conditional.

## External data

[docs/04-dados-externos.md](docs/04-dados-externos.md) sets a six-item admission test. The binding rule: **no external source enters as a label** — the task is measured inside CNES, and that is what keeps the three tracks comparable. Ranked by value over risk, widening the spatial scope beyond one município comes *before* any external source: it is cheaper, the data is already downloaded, and it introduces no new error (D-16).

## Also

`archieved/` uses the old RelBench API (`relbench.data`, `NodeTask`, `RelBenchEncoder`), absent from 2.1.1. Historical reference only — do not copy code from it (D-12).
