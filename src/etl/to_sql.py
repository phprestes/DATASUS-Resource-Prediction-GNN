from typing import List
import duckdb
import os
import zipfile
import shutil
from tqdm import tqdm
from pathlib import Path
from src.config.paths import RAW_FOLDER, INTERMEDIATE_FOLDER, TEMP_EXTRACT_DIR
from src.config.schema import FACT_TABLES

INPUT_PREFIX = 'BASE_DE_DADOS_CNES_'
OUTPUT_PREFIX = 'sql_cnes_'

def process_cnes_zip(
        periods : List[str],
        input_folder : Path = RAW_FOLDER,
        output_folder : Path = INTERMEDIATE_FOLDER,
        reprocess : bool = False,
        only_fact_tables : bool = True,
        tabelas : "List[str] | None" = None
) -> None:
    """
    Carrega os CSV de cada ZIP de competência num DuckDB por competência.

    Tudo entra como VARCHAR (`all_varchar=True`): a tipagem acontece só na
    conversão para Parquet, guiada por CNES_DTYPES. `reprocess=False` pula
    competências já convertidas, mesmo default dos outros estágios do ETL.

    `tabelas` restringe a ingestão a um subconjunto. Serve para o caso em que
    `01-selecao-tabelas.md` admite uma coluna nova e só uma tabela precisa voltar
    ao ZIP — reprocessar a competência inteira custa dezenas de minutos e vários
    gigabytes de DuckDB por nada. Cuidado: com `tabelas`, o DuckDB resultante é
    **parcial**, e `to_parquet` executado sem argumento sobre ele exportaria só o
    que estiver lá. Apague o intermediário depois de usar, ou passe o mesmo
    subconjunto adiante.
    """
    if tabelas is not None:
        desconhecidas = [t for t in tabelas if t not in FACT_TABLES]
        if desconhecidas:
            raise ValueError(
                f"tabelas fora do escopo de docs/01-selecao-tabelas.md: {desconhecidas}"
            )
        tabelas = set(tabelas)
    # Limpa diretório temporário se existir de execuções anteriores falhas
    if TEMP_EXTRACT_DIR.exists():
        shutil.rmtree(TEMP_EXTRACT_DIR)
    TEMP_EXTRACT_DIR.mkdir(parents=True, exist_ok=True)

    for period in tqdm(periods, desc="Processando períodos"):
        input_path = input_folder / f"{INPUT_PREFIX}{period}.ZIP"
        output_path = output_folder / f"{OUTPUT_PREFIX}{period}.duckdb"

        if not input_path.exists():
            print(f"[AVISO] Arquivo não encontrado: {input_path}")
            continue
        
        if output_path.exists() and not reprocess:
            print(f"[AVISO] Pulando base existente: {output_path}")
            continue

        con = duckdb.connect(output_path)

        try:
            with zipfile.ZipFile(input_path, 'r') as z:
                for csv_file in z.namelist():
                    stem_name = Path(csv_file).stem
                    clean_name = stem_name[:-6]
                    
                    if only_fact_tables and clean_name not in FACT_TABLES:
                        continue

                    if tabelas is not None and clean_name not in tabelas:
                        continue

                    temp_csv_path = TEMP_EXTRACT_DIR / csv_file
                    z.extract(csv_file, TEMP_EXTRACT_DIR)

                    try:
                        read_params = (
                            f"'{temp_csv_path}', "
                            "header=True, "
                            "sep=';', "
                            "quote='\"', "
                            "encoding='ISO_8859_1', " 
                            "normalize_names=True, "
                            "ignore_errors=True, "
                            "all_varchar=True"
                        )

                        query = f"""
                            CREATE OR REPLACE TABLE {stem_name} AS 
                            SELECT * FROM read_csv({read_params})
                        """
                        con.execute(query)
                            
                    except Exception as e:
                        tqdm.write(f"[ALERTA] Erro ao processar {stem_name}. Erro: {e}")
                    
                    finally:
                        if temp_csv_path.exists():
                            temp_csv_path.unlink()

        except zipfile.BadZipFile:
            print(f"\n[ERRO] O arquivo ZIP {input_path} está corrompido.")
        except Exception as e:
            print(f"\n[ERRO] Falha no arquivo {input_path}: {e}")
            
        con.close()

    # Limpeza final
    if TEMP_EXTRACT_DIR.exists():
        shutil.rmtree(TEMP_EXTRACT_DIR)
    
    print("Processamento finalizado com tabelas separadas por competência.")

if __name__ == "__main__":
    zip_files = sorted(RAW_FOLDER.glob('BASE_DE_DADOS_CNES_*.ZIP'))
    print(f"Encontrados {len(zip_files)} arquivos ZIP.")
    periodos = [f.stem.split('_')[-1] for f in zip_files]
    process_cnes_zip(periodos)