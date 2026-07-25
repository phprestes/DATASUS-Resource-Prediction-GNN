import pandas as pd
import pyarrow.dataset as ds
import pyarrow.compute as pc
from relbench.base import Database, Table, Dataset
from src.constant import PRIMARY_FOLDER, CNES_PKEY, CNES_FKEY

class CNESDataset(Dataset):
    name = "cnes-dataset"
    # Example timestamps (can be overridden)
    val_timestamp = pd.Timestamp("2023-01-01")
    test_timestamp = pd.Timestamp("2025-01-01")
    
    def make_db(self, municipio_id: str = None) -> Database:
        paths = list(PRIMARY_FOLDER.glob('*/*.parquet'))
        all_tables = set([p.stem for p in paths])
        tables_dict = {}

        root_files = [str(p) for p in paths if p.stem == "tbEstabelecimento"]
        if not root_files:
            raise ValueError("Tabela raiz 'tbEstabelecimento' não encontrada na pasta primary.")
        
        root_dataset = ds.dataset(root_files, format="parquet")
        valid_unidades = None

        if municipio_id:
            root_filter = pc.field("co_municipio_gestor") == str(municipio_id)
            df_root = root_dataset.to_table(filter=root_filter)
    
            valid_unidades = df_root["co_unidade"] 
            print(f"[Grafo Raiz] tbEstabelecimento ancorada para {municipio_id}! Nós criados: {len(df_root)}")
        else:
            df_root = root_dataset.to_table()
        
        tables_dict["tbEstabelecimento"] = Table(
            df=df_root, 
            pkey_col="co_unidade",
            fkey_col_to_pkey_table={}
        )

        for t in all_tables:
            if t == "tbEstabelecimento":
                continue
            table_files = [str(p) for p in paths if p.stem == t]
            if not table_files: continue
            
            try:
                pdataset = ds.dataset(table_files, format="parquet")
                columns = pdataset.schema.names

                if valid_unidades is not None and "co_unidade" in columns:
                    child_filter = pc.field("co_unidade").isin(valid_unidades)
                    df_concat = pdataset.to_table(filter=child_filter)
                    print(f"[Subgrafo] {t} otimizada na leitura. Arestas capturadas: {len(df_concat)}")
                else:
                    df_concat = pdataset.to_table()
                
                columns = df_concat.column_names
                
                # Identificação automatica de colunas chave e tempo com base no padrao
                time_col = "to_chardt_atualizacaoddmmyyyy" if "to_chardt_atualizacaoddmmyyyy" in columns else None
                pkey_col = CNES_PKEY.get(t, None)

                fkey_col_to_pkey_table = {}
                for col, target in CNES_FKEY.get(t, {}).items():
                    if col in columns:
                        fkey_col_to_pkey_table[col] = target
                
                # Registrar Tabela
                kwargs = {
                    "df": df_concat,
                    "pkey_col": pkey_col,
                    "fkey_col_to_pkey_table": fkey_col_to_pkey_table
                }
                if time_col:
                    kwargs["time_col"] = time_col
                    
                tables_dict[t] = Table(**kwargs)
            except Exception as e:
                print(f"Erro no pyarrow para {t}: {e}")
                continue
                
        return Database(tables_dict)
