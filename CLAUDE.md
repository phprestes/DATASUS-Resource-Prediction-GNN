# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Undergraduate research project (Iniciação Científica) on Brazilian CNES data (National Registry of Health Establishments, DATASUS). It asks whether resource scarcity in a municipal health network can be identified and anticipated from the network's *structure* — not just from each establishment's own attributes.

Code comments, docstrings, prints and docs are in **Portuguese**. Keep new code consistent with that. Commit messages are in Portuguese too.

## Read the docs first

Six Markdown files in [docs/](docs/) are the project's contract. They are not summaries of the code — the code is downstream of them.

- **[docs/01-selecao-tabelas.md](docs/01-selecao-tabelas.md)** — the **source of truth for the schema**. [src/config/schema.py](src/config/schema.py) parses it at import time and derives `FACT_TABLES`, `CNES_EXTRACT_COLUMNS`, `CNES_USEFUL_COLUMNS`, `CNES_DTYPES`, `CNES_PKEY`, `CNES_NATURAL_KEY`, `CNES_FKEY`. **Editing this file changes the pipeline.** There is no second list in code to keep in sync — that was the bug the refactor removed.
- **[docs/02-metodologia.md](docs/02-metodologia.md)** — research question, operational definition of scarcity, sample, temporal semantics, the four tracks, evaluation protocol.
- **[docs/03-decisoes.md](docs/03-decisoes.md)** — 38 numbered decisions with the evidence behind each and what was rejected. When something in the code looks surprising, the reason is usually a D-nn entry.
- **[docs/04-dados-externos.md](docs/04-dados-externos.md)** — the six-item admission test for any source outside CNES. The binding rule: no external source enters as a label.
- **[docs/05-esboco-artigo.md](docs/05-esboco-artigo.md)** — the article outline: what the paper claims, in what order, and what is still unwritten. Formal register, unlike the rest of the docs. Carries a figure manifest with eight slots whose captions are written and whose `![...]` lines sit commented until the file exists in [docs/figuras/](docs/figuras/) — naming convention and provenance in `docs/figuras/README.md`. The README describes the repository; this holds the argument.
- **[docs/06-pipeline-hpc.md](docs/06-pipeline-hpc.md)** — the second pipeline (server-side, national scope, CUDA) and the technique × scope matrix it exists to measure. Read before touching anything under `hpc/`.
- **[docs/DICIONARIO_DE_DADOS.pdf](docs/DICIONARIO_DE_DADOS.pdf)** — the DATASUS data dictionary (2025 edition), 155 pages. It describes the **Oracle** database, not the distributed CSV: the extraction exports a subset of the columns and renames some. Where the two disagree, the CSV wins. Read it with `pdftotext -layout`, never page by page.

`docs/SelecaoTabelas_v1.pdf` and `_v2.pdf` are historical records, superseded by `01-selecao-tabelas.md`. `docs/CNES_GNN-2.pdf` is the original project proposal; the code has deliberately diverged from it (see D-01).

## Environment & commands

Python 3.12 in `.venv`, managed by **uv** (there is no `pip` inside it). Package installed editable as `meu-projeto-ic`.

**The Makefile is the documented entry point** — `make` with no argument lists every target, its variables and examples. Prefer it over raw module invocations, and keep it in sync when you add a workflow.

```bash
make                     # list targets
make etl                 # full ETL, one competência at a time (resumable)
make etl-periodo PERIODOS=202601
make mudancas            # recompute change events (after touching keys or typing)
make reprocessar-tabelas TABELAS=tbEstabelecimento PERIODO=202601
make testes              # full suite
make verificar           # tests + schema summary derived from the doc
make experimento         # three tracks under a memory cap
make resultados          # print the paired table of the newest run
```

Underneath, the stages are still plain modules if you need them directly:

```bash
source .venv/bin/activate
python -m src.etl.pipeline             # orchestrated ETL; `--periodos`, `--pular-download`
python -m src.etl.extract 202601       # 10 annual ZIPs -> data/01_raw (~3.6 GB)
python -m src.etl.to_sql               # ZIP CSVs -> DuckDB per period -> data/02_intermediate
python -m src.etl.to_parquet           # DuckDB -> typed Parquet -> data/03_primary
python -m src.etl.changes              # snapshot diffs -> change events -> data/04_feature
python -m pytest tests/test_schema.py::test_fact_tables_e_useful_columns_nao_podem_divergir
```

All ETL stages default to `reprocess=False` (skip what exists) — the series is several GB, so re-downloading by accident is expensive. Pass `reprocess=True` explicitly to redo work.

`VIRTUAL_ENV=.venv uv pip install -e .` to reinstall. `pyg-lib`, `torch-scatter` and `torch-sparse` are not on PyPI and need the wheel index matched to the torch version — instructions are in the header of `requirements.txt`.

## Architecture

### Data layers

`data/01_raw` (`BASE_DE_DADOS_CNES_{YYYYMM}.ZIP`) → `data/02_intermediate` (`sql_cnes_{YYYYMM}.duckdb`) → `data/03_primary` (`{YYYYMM}/{tabela}.parquet`) → `data/04_feature/changes/{tabela}/{periodo}.parquet`. Nothing under `data/` is versioned; it is all reproducible from stage 1.

The period is always the 6-char string `YYYYMM` ("competência") and is the partition key everywhere. The canonical sample is `src.etl.extract.PERIODOS_ANUAIS` — January of each year, 2017–2026, ten snapshots and nine transitions (D-04, extended by D-29). Never hardcode the count: `changes.periodos_disponiveis()` reads the primary layer, `PERIODOS_ANUAIS` is the intended series, and `ANO_FINAL` in `extract.py` is the single place a new January is added.

### Time is the subtle part

Read this before touching anything temporal. A competência ZIP is a **snapshot of current state**, not an event log, and it keeps only the **last** `dt_atualizacao` per row. So:

- `to_chardt_atualizacaoddmmyyyy` is **right-censored**. Using it as a graph `time_col` — as the old code did — assigns each row an instant that depends on when the snapshot was taken.
- Changes between two snapshots are unrecoverable. The study's real temporal resolution is the snapshot spacing, not the date column's granularity.
- The unit of analysis is therefore the **transition** `t → t+1` ([src/etl/changes.py](src/etl/changes.py)), and the graph's `time_col` is the **snapshot date** (Jan 1 of the competência), which is exact and uniform. Events supply labels; snapshots supply state. See D-08.

### Modules

`src/` is three packages, split by responsibility (D-33). The dependency only ever points at the contract: `config` imports nothing from the others, `etl` imports nothing from `ml`.

| Package | Module | Role |
|---|---|---|
| [src/config](src/config/) | [paths.py](src/config/paths.py) | data layer locations, doc locations. `BASE_DIR` is `parents[2]` — it breaks if the file moves depth |
| | [schema.py](src/config/schema.py) | parses `01-selecao-tabelas.md`; strict, fails the import on malformed input |
| [src/etl](src/etl/) | [extract.py](src/etl/extract.py), [to_sql.py](src/etl/to_sql.py), [to_parquet.py](src/etl/to_parquet.py) | the three layer-producing stages |
| | [changes.py](src/etl/changes.py) | snapshot diffing, change events, change-rate measurement |
| | [pipeline.py](src/etl/pipeline.py) | orchestrates the stages one competência at a time |
| [src/ml](src/ml/) | [splits.py](src/ml/splits.py) | the single temporal partition, consumed by all modelling tracks |
| | [tasks.py](src/ml/tasks.py) | label tables: acquisition (primary), quantity (secondary) |
| | [baselines.py](src/ml/baselines.py) | track 1 — five baselines with no structural information |
| | [graph.py](src/ml/graph.py) | tracks 2 and 3 — RelBench `Database`, and the geographic kNN graph |
| | [gnn.py](src/ml/gnn.py) | encoders, shared pair decoder, training loop |
| | [metrics.py](src/ml/metrics.py) | average precision, AUC, MAP@k, RMSE/MAE, results table |

Each package's `__init__.py` carries the map of its own modules and the rule it obeys — read those before adding a module, and put it where the dependency direction allows.

`tools/build_selecao_inicial.py` is a one-shot migrator kept as a provenance record: it generated the first version of the selection doc by joining the old PDF, `src/constant.py` (read from git history — the file is deleted) and the empirical report. It refuses to overwrite the doc without `--force`.

### Conventions that will bite you

- **CSV naming.** Files inside the ZIP are `{TableName}{YYYYMM}.csv`. [to_sql.py](src/etl/to_sql.py) strips the 6-char period to match `FACT_TABLES` but creates the DuckDB table under the **full suffixed name** (`tbEstabelecimento201701`); [to_parquet.py](src/etl/to_parquet.py) strips it again. Changing the period width breaks both.
- **Everything is VARCHAR at the intermediate layer.** Ingest uses `all_varchar=True`, `normalize_names=True`, `sep=';'`, `encoding='ISO_8859_1'`. Typing happens only in `to_parquet`, driven by `CNES_DTYPES`. `datetime64[ns]` triggers `try_strptime` with `%d/%m/%Y` and nulls dates before 1900-01-01 (a CNES sentinel); string and category columns get `NULLIF(TRIM(...), '')`, because Oracle `CHAR(n)` arrives space-padded and the padding **changes when CNES widens a column** — that is D-30, and it silently broke every cross-snapshot comparison of `co_tipo_equipamento`.
- **Both ETL stages take `tabelas=[...]`.** Admitting a column in `01-selecao-tabelas.md` means the existing Parquet lacks it; reprocessing only the affected tables costs minutes instead of hours. The intermediate DuckDB produced that way is **partial** — delete it afterwards, or a later `to_parquet` run over it exports only those tables.
- **Three name spellings for the same thing.** Oracle dictionary (`RL_ESTAB_COMPLEMENTAR`), CSV/DuckDB (`rlEstabComplementar`), and date columns wrapped in the extraction's own SQL (`TO_CHAR(DT_ATUALIZACAO,'DD/MM/YYYY')` → `to_chardt_atualizacaoddmmyyyy`, sometimes with a table alias inside: `to_charadt_atualizacaoddmmyyyy`). Documented in `01-selecao-tabelas.md`.
- **`pkey` is not a row key.** `CNES_PKEY` is the *entity* key RelBench joins on (`co_unidade`) and is almost never unique — `rlEstabEquipamento` has one row per equipment, not per establishment. Row identity is `CNES_NATURAL_KEY`: **all 44** tables declare one, every tuple measured across every snapshot (D-27, D-38). **The natural key always contains the dictionary's composite PRIMARY KEY** — a PK column stays in the key even when the semantic filter would discard it, because identifying the row is what the key is for; `co_end_compl` in `rlEstabServClass` is that case, and without it the dictionary's PK duplicates 561 rows in 201701 and 4,991 in 202601. Minimality applies only *above* the PK (that is what took `tp_sus` and `co_tipo_leito` out). Two caveats: `rlEstabSipac` is unique only *up to exact duplicate rows* — 8 to 59 per snapshot are identical in every exported column, so no key separates them (D-38); and the dictionary's key is not authority either — for `rlMunUnidAcolhim` it duplicates in every snapshot and needed `co_municipio` added. Adding a key changes `changes.py` output, so re-run `python -m src.etl.changes` with `reprocess=True` after editing one.
- **`fkey_para` only when the column holds values of the destination's pkey.** The dictionary's foreign keys are composite and this format writes one column per row, so transcribing them column by column produced 33 declarations that join nothing — measured, literally zero matching values (D-28). `co_unidade` always points at `tbEstabelecimento`. Don't re-add component FKs; the composite case is unexpressible today.
- **Tables hold `pyarrow.Table`, not `pandas.DataFrame`.** Deliberate: the municipality filter is pushed into the Parquet scan. Call `.to_pandas()` explicitly; don't assume pandas.
- **`recorte` is the main cost lever.** [graph.py](src/ml/graph.py) filters the root on `co_municipio_gestor` by IBGE-code prefix, then pushes the resulting `co_unidade` set as an `isin` predicate into every child table's scan. Without it you load the whole country.

### Comparability is the point of the design

All tracks consume the same `TabelaTarefa` and the same `ParticaoTemporal`, and all return the same `Previsao` dataclass, so `src.ml.metrics.tabela_de_resultados` can put them in one table. **Never report a GNN number without the persistence baseline beside it** (D-11) — the previous version of the project reported training-set performance as test performance, and nothing caught it.

Track 1 must stay free of relational and spatial features. Adding neighbourhood aggregates to the baselines would erase the difference the experiment exists to measure.

## Numbers you should know before proposing anything

Measured on São Paulo. Figures below marked *(9 snapshots)* were taken before 202601 entered the series (D-29); the split moved with it, so any comparison against a new run needs the experiment re-run, not just the numbers re-read.

- **Scope is the state of São Paulo**, prefix `35` — 146.5k establishments in 202601 (136k in 202501), 645 municípios. It was the capital only; D-21 widened it because that nearly triples acquisition events and gives IBGE population non-zero variance. `recorte` is an IBGE-code *prefix*: `'355030'` gets the capital back, `None` the country.
- **Target.** `rlEstabEquipamento` yields **40,880** acquisition events across the nine transitions at state scope — 34,571 over the eight transitions before 202601 (D-29). `rlEstabServClass` yields 42,208 and stays the runner-up; `rlEstabComplementar` (beds) yields 3,062. That is why the target moved (D-01, D-18) and why it stayed.
- **Prevalence is 0.0472%** at state scope — 86.7M candidates for 40.9k events. Two candidate-space restrictions were tested and rejected (D-19). Don't propose a third without measuring first. **MAP@k is the headline metric**, and D-24 shows why in practice: AP and MAP@10 rank the baselines differently.
- **The bar to beat is MAP@10 = 0.300** (`gnn_relacional`, D-32); `popularidade_item` sits at 0.271. Persistence returns AP exactly equal to prevalence and AUC exactly 0.500 — if it ever doesn't, the harness is broken (D-24).
- **Latest results** (D-32, test 2026, paired on 127.9k positionable establishments): `gnn_relacional` AP 0.01061 / AUC 0.849 / MAP@10 **0.300**; `gnn_geografica` 0.00490 / 0.816 / 0.274; `gbdt_geral` 0.00355 / 0.766 / 0.257; `popularidade_item` 0.00220 / 0.700 / 0.271; `persistencia` 0.00055 / 0.500 / 0.032. The relational GNN now **wins both** metrics, reversing D-26. But three things changed at once — partition moved a year, D-28 fixed the graph's foreign keys, training reached epoch 99 instead of 47 — and **no ablation was run**, so don't state a cause. Decomposing that is the next experiment, ahead of any architecture change.
- **The paired table is the one that counts.** Prevalence is 0.0553% on positionable establishments vs 0.0478% overall, and **all 6,309 test positives are positionable** — unpaired comparison flatters track 3 by construction.
- **Two limitations are now quantified, not just mentioned** (D-32): node features come from the graph cutoff (201701), so **45% of nodes enter with an empty feature vector** — the state had 80,073 establishments in 2017 against 146,679 across the series; and the minimal projection (D-23) drops **298 of the 368 `util` columns** of the fact tables, so relational edges carry no weight and no attribute.
- **Change rate is flat**: 0.079–0.110 per year on the target, median 0.092 over the nine transitions, no pandemic spike. Annual density is settled (D-10). If a table ever shows a rate near 1.0, suspect a key or a padding change before believing the data (D-27, D-30).
- **Coordinates cover 87.3%** at state scope in 202601 (85.7% in 202501, 75.0% in the capital), 87.2% accumulated over the ten snapshots. Rising ~1.6 points a year. D-17 said 57% — measured on six of nine snapshots, superseded by D-22.
- **The schema drifts.** Three of 44 tables have columns that vanish and return, with 201901 the anomalous competência. Reading several Parquet files directly via DuckDB needs `union_by_name=true` (D-20).

## Memory is a hard constraint

The machine has 9 GB and building the state-scope task table once crashed the user's IDE. D-23 cut the table from 3.22 GB to 0.317 GB and the peak from 4.87 GB to 3.37 GB. Code touching the task table must not materialise `co_unidade` as strings or copy the frame whole — use `TabelaTarefa.codigos()` and `Previsao.mascara_de_entidades()`. Negative sampling (200:1) applies to **training only**; validation and test stay complete, or the measured prevalence is fiction.

## The two pipelines

`src/` runs on the 9 GB machine; `hpc/` runs on the IME cluster (`brucutuvii`: 440 GB, 2× RTX A6000), national scope, CUDA. They are isolated on purpose (D-34) — separate ETL, graph assembly and training loop, separate data root via `IC_HPC_DATA`, and **no module of `src` imports from `hpc`**.

`hpc` imports from `src` only what must be identical for the comparison to hold: `src.config.schema` (the schema contract), `src.ml.metrics`, `src.ml.splits`, `src.ml.artefatos`, `src.ml.baselines`.

**Never run the `hpc-*` targets on the user's machine.** The code refuses below 64 GB of RAM, and that guard exists because an attempt to exercise the full path locally exhausted system and editor memory. Validate `hpc/` logic with the synthetic tests (`pytest tests/test_hpc_*.py -q`), never with the real primary layer.

`--modo compativel | completo` is an experimental condition, not a code-compat switch: the compatible mode replicates the 9 GB limitations at any scope, which is what makes the four cells of the technique × scope matrix decomposable. Nothing has been run yet — the numbers land in D-36.

## Trained models are artifacts

Both pipelines write a package per run to `models/`, read by `src/ml/artefatos.py` (D-35): `state_dict` on CPU, manifest with provenance and machine profile, node/item index, training curve, and **per-example scores**. `make validar RUN=<dir>` recomputes AP, AUC and MAP@10 from the saved scores with no GPU and no `data/`, and checks them against the manifest.

The index is not optional: the item embedding is position-indexed, so weights without the `unidades`/`itens` order load fine and score garbage. `salvar_execucao` refuses.

## Reproducing the experiment

`make experimento` (or `python -m tools.roda_experimento`) runs all three tracks and writes
`docs/resultados/{date}-trilhas-{recorte}.json` incrementally. ~55 min at state
scope, **6.3 GB peak** with the ten-snapshot series. On this 9 GB machine that
only fits if the browser and IDE are not holding 7 GB: run it under a cgroup
— which is what the `make` target already does, wrapping the run in
`systemd-run --user --scope -p MemoryMax=$(MEM)` so an overrun kills the experiment
instead of the user's session. A 5.5 GB cap with swap disabled died right at the
start of GNN training.
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
