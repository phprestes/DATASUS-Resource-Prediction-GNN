from typing import List
import duckdb
import os
import pandas as pd
from tqdm import tqdm
from pathlib import Path

from src.config.paths import INTERMEDIATE_FOLDER, PRIMARY_FOLDER
from src.config.schema import CNES_DTYPES, CNES_EXTRACT_COLUMNS

INPUT_PREFIX = 'sql_cnes_'

def clean_cnes_data(
        periods : List[str],
        input_folder : Path = INTERMEDIATE_FOLDER,
        output_folder : Path = PRIMARY_FOLDER,
        reprocess : bool = False,
        tabelas : "List[str] | None" = None,
) -> None:
    """
    Converte o DuckDB de cada competência em Parquet tipado por `CNES_DTYPES`.

    `tabelas` restringe a conversão a um subconjunto, para o caso de uma coluna
    recém-admitida em `01-selecao-tabelas.md` que só afeta uma tabela. Com
    `reprocess=False` (default), Parquet já existente é preservado.

    A tipagem é onde o TRIM acontece: coluna de texto passa por
    `NULLIF(TRIM(...), '')`, porque `CHAR(n)` do Oracle chega com espaço à direita
    e o preenchimento muda quando o CNES alarga uma coluna. Sem isso toda
    comparação entre snapshots quebra em silêncio (D-30). Data usa `try_strptime`
    com `%d/%m/%Y` e anula valores antes de 1900, que são sentinela do CNES.

    Args:
        periods: competências a converter.
        input_folder: camada 02, com um DuckDB por competência.
        output_folder: camada 03, um diretório por competência.
        reprocess: reconverte Parquet já existente.
        tabelas: subconjunto a converter. `None` converte todas.

    Returns:
        Nada. O efeito é o Parquet em disco.

    Raises:
        ValueError: `tabelas` cita nome fora do escopo do documento de seleção.
    """
    if tabelas is not None:
        desconhecidas = [t for t in tabelas if t not in CNES_EXTRACT_COLUMNS]
        if desconhecidas:
            raise ValueError(
                f"tabelas fora do escopo de docs/01-selecao-tabelas.md: {desconhecidas}"
            )
        tabelas = set(tabelas)


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

                if tabelas is not None and base_table not in tabelas:
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
                            # TRIM não é cosmético. As colunas CHAR(n) do Oracle
                            # chegam preenchidas com espaço, e o preenchimento
                            # muda quando o CNES alarga a coluna: em 202601
                            # `co_tipo_equipamento` passou de CHAR(1) para
                            # CHAR(2), e '1' virou '1 '. Sem normalizar, nenhuma
                            # linha casa entre 202501 e 202601 — a taxa de
                            # mudança da tabela do alvo foi a 1,94, tudo contado
                            # como remoção mais inserção. Ver D-30.
                            # NULLIF depois do TRIM: string só de espaço é
                            # ausência de valor, não valor vazio.
                            cols_str_list.append(
                                f'NULLIF(TRIM(TRY_CAST("{col}" AS VARCHAR)), \'\') AS "{col}"'
                            )

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