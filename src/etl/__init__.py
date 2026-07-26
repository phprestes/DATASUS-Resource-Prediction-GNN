"""
Os estágios que produzem as camadas de dados, do ZIP ao evento de mudança.

    extract.py      01_raw          baixa os ZIP de competência do CNES
    to_sql.py       02_intermediate carrega os CSV num DuckDB por competência
    to_parquet.py   03_primary      exporta Parquet tipado por CNES_DTYPES
    changes.py      04_feature      compara snapshots e materializa os eventos
    pipeline.py     orquestra os três primeiros, uma competência por vez

Cada estágio lê a camada anterior e escreve a seguinte, nunca para trás. Todos
usam `reprocess=False` por padrão: a série tem vários gigabytes e refazer
trabalho por acidente é caro.

Executáveis como módulo:

    python -m src.etl.pipeline           # caminho recomendado
    python -m src.etl.extract 202601
    python -m src.etl.changes
"""
