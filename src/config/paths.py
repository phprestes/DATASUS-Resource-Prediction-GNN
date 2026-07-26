"""
Localização das camadas de dados e dos documentos canônicos.

As camadas seguem a convenção numerada: cada estágio do ETL lê da camada
anterior e escreve na seguinte, sem nunca escrever para trás.

    01_raw           ZIP de competência baixados do CNES (src/etl/extract.py)
    02_intermediate  um DuckDB por competência, tudo VARCHAR (src/etl/to_sql.py)
    03_primary       Parquet por competência e tabela, tipado (src/etl/to_parquet.py)
    04_feature       eventos de mudança entre competências (src/etl/changes.py)
"""

from pathlib import Path

# src/config/paths.py -> src/config -> src -> raiz do projeto. Se este arquivo
# mudar de lugar, este índice muda com ele.
BASE_DIR = Path(__file__).resolve().parents[2]

DATA_DIR = BASE_DIR / "data"
RAW_FOLDER = DATA_DIR / "01_raw"
INTERMEDIATE_FOLDER = DATA_DIR / "02_intermediate"
PRIMARY_FOLDER = DATA_DIR / "03_primary"
FEATURE_FOLDER = DATA_DIR / "04_feature"

# Descompactação do ZIP: um CSV por vez, apagado logo após a carga no DuckDB.
# Fica sob data/ para que o .gitignore o cubra junto com as demais camadas.
TEMP_EXTRACT_DIR = DATA_DIR / "temp_extract"

# Eventos de mudança materializados por src/etl/changes.py.
CHANGES_FOLDER = FEATURE_FOLDER / "changes"

DOCS_DIR = BASE_DIR / "docs"

# Fonte da verdade do schema, lida por src/config/schema.py.
SELECAO_TABELAS = DOCS_DIR / "01-selecao-tabelas.md"
