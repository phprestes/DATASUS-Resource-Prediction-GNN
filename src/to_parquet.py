from typing import List
import duckdb
import os
import pandas as pd
from tqdm import tqdm
from pathlib import Path

from src.paths import INTERMEDIATE_FOLDER, PRIMARY_FOLDER
from src.schema import CNES_DTYPES, CNES_EXTRACT_COLUMNS

INPUT_PREFIX = 'sql_cnes_'

def clean_cnes_data(
        periods : List[str],
        input_folder : Path = INTERMEDIATE_FOLDER,
        output_folder : Path = PRIMARY_FOLDER,
        reprocess : bool = False,
) -> None:
    
    for period in tqdm(periods, desc="Processando períodos"):
        input_path = input_folder / f"{INPUT_PREFIX}{period}.duckdb"
        period_folder = output_folder / str(period)
        
        if not input_path.exists():
            print(f"[AVISO] Arquivo intermediário não encontrado: {input_path}")
            continue
        
        period_folder.mkdir(parents=True, exist_ok=True)
        con = duckdb.connect(str(input_path))
        
        try:
            tables_in_db = [t[0] for t in con.execute("SHOW TABLES").fetchall()]
            
            for table in tables_in_db:
                # O DuckDB possui tabelas gravadas com o sufixo do periodo ex: tbEstabelecimento201701
                if table.endswith(period):
                    base_table = table[:-len(period)]
                else:
                    base_table = table
                    
                if base_table not in CNES_EXTRACT_COLUMNS:
                    continue
                
                parquet_path = period_folder / f"{base_table}.parquet"
                
                if parquet_path.exists() and not reprocess:
                    continue
                
                cols = CNES_EXTRACT_COLUMNS[base_table]
                dtypes = CNES_DTYPES.get(base_table, {})
                
                try:
                    df_schema = con.execute(f"DESCRIBE {table}").df()
                    actual_cols = df_schema['column_name'].tolist()
                    cols_to_select = [c for c in cols if c in actual_cols]
                    
                    if not cols_to_select:
                        continue
                        
                    cols_str_list = []
                    for col in cols_to_select:
                        dtype = dtypes.get(col, '')
                        if 'datetime' in dtype:
                            cols_str_list.append(f"CASE WHEN try_strptime(\"{col}\"::VARCHAR, '%d/%m/%Y') < '1900-01-01'::DATE THEN NULL ELSE try_strptime(\"{col}\"::VARCHAR, '%d/%m/%Y') END AS \"{col}\"")
                        elif dtype == 'Int64':
                            cols_str_list.append(f'TRY_CAST("{col}" AS BIGINT) AS "{col}"')
                        elif dtype in ['float64', 'float32']:
                            cols_str_list.append(f'TRY_CAST("{col}" AS DOUBLE) AS "{col}"')
                        else:
                            cols_str_list.append(f'TRY_CAST("{col}" AS VARCHAR) AS "{col}"')

                    cols_str = ", ".join(cols_str_list)
                    query = f"SELECT {cols_str} FROM {table}"
                    
                    con.execute(f"COPY ({query}) TO '{parquet_path}' (FORMAT 'parquet')")
                    
                except Exception as e:
                    tqdm.write(f"[ERRO] Falha ao exportar {base_table} do {period}: {e}")
                    
        except Exception as e:
            print(f"[ERRO] Erro na conexão com DuckDB {period}: {e}")
        finally:
            con.close()
            
    print("Processamento para Parquet finalizado com sucesso.")

if __name__ == "__main__":
    duckdb_files = sorted(INTERMEDIATE_FOLDER.glob('sql_cnes_*.duckdb'))
    print(f"Encontrados {len(duckdb_files)} arquivos DuckDB intermediários.")
    periodos = [f.stem.split('_')[-1] for f in duckdb_files]
    clean_cnes_data(periodos)