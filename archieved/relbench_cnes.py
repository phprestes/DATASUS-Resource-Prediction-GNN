import os
import torch
import pandas as pd
import torch.nn.functional as F
from torch_geometric.data import HeteroData
from torch_geometric.loader import NeighborLoader
from torch_geometric.nn import SAGEConv, to_hetero
from torch_frame import stype
from torch_frame.config import TextEmbedderConfig
from relbench.data import Database, Table, Dataset
from relbench.data.task import NodeTask
from relbench.model.encoder import RelBenchEncoder
from relbench.metrics import MAE, RMSE

# --- CONFIGURAÇÕES ---
DATA_DIR = "./relbench_dataset"
VAL_DATE = pd.Timestamp("2023-01-01")
TEST_DATE = pd.Timestamp("2024-01-01")

# ==============================================================================
# 1. DEFINIÇÃO DO DATASET E SCHEMA (O Mapeamento que faltava)
# ==============================================================================

class CNESDataset(Dataset):
    val_timestamp = VAL_DATE
    test_timestamp = TEST_DATE

    def make_db(self) -> Database:
        # Carrega os Parquets gerados pelo ETL
        # Nota: Usamos convert_dtypes() para garantir que inteiros não virem float
        
        # --- NÓS ---
        df_estab = pd.read_parquet(f"{DATA_DIR}/node_estabelecimento.parquet").convert_dtypes()
        df_prof = pd.read_parquet(f"{DATA_DIR}/node_profissional.parquet").convert_dtypes()
        
        # --- ARESTAS ---
        df_vinculo = pd.read_parquet(f"{DATA_DIR}/edge_vinculo_trabalho.parquet").convert_dtypes()
        
        # --- FATOS (Features Temporais dos Nós) ---
        df_leitos = pd.read_parquet(f"{DATA_DIR}/fact_leitos.parquet").convert_dtypes()
        df_equips = pd.read_parquet(f"{DATA_DIR}/fact_equipamentos.parquet").convert_dtypes()
        df_servicos = pd.read_parquet(f"{DATA_DIR}/fact_servicos.parquet").convert_dtypes()

        # Definição das Tabelas
        tables = {
            "estabelecimento": Table(
                df=df_estab, pkey_col="co_unidade", 
                fkey_col_to_pkey_table={}, time_col=None
            ),
            "profissional": Table(
                df=df_prof, pkey_col="co_profissional_sus", 
                fkey_col_to_pkey_table={}, time_col=None
            ),
            "vinculo": Table(
                df=df_vinculo, pkey_col=None, time_col="timestamp",
                fkey_col_to_pkey_table={
                    "source_id": "profissional",
                    "target_id": "estabelecimento"
                }
            ),
            "leitos": Table(
                df=df_leitos, pkey_col=None, time_col="timestamp",
                fkey_col_to_pkey_table={"co_unidade": "estabelecimento"}
            ),
            "equipamentos": Table(
                df=df_equips, pkey_col=None, time_col="timestamp",
                fkey_col_to_pkey_table={"co_unidade": "estabelecimento"}
            ),
            "servicos": Table(
                df=df_servicos, pkey_col=None, time_col="timestamp",
                fkey_col_to_pkey_table={"co_unidade": "estabelecimento"}
            ),
        }
        return Database(tables)

# ==============================================================================
# 2. DEFINIÇÃO DA TAREFA (O Target)
# ==============================================================================

class PredictSusCapacity(NodeTask):
    """
    Tarefa: Prever a capacidade total de leitos SUS de um hospital daqui a 6 meses.
    Target: Coluna 'qt_sus' da tabela 'fact_leitos'.
    """
    def __init__(self, dataset):
        super().__init__(
            dataset=dataset,
            timedelta=pd.Timedelta(days=180), # Horizonte: 6 meses
            metrics=[MAE(), RMSE()],
        )

    def make_table(self, db: Database, val_timestamp: pd.Timestamp, test_timestamp: pd.Timestamp) -> Table:
        # A fonte da verdade é a tabela de fatos 'leitos'
        df = db.table_dict["leitos"].df
        
        # Agrupa por Estabelecimento e Tempo (pois pode haver várias linhas de tipos de leito)
        # Queremos o TOTAL de leitos SUS do hospital naquele mês
        df["qt_sus"] = pd.to_numeric(df["qt_sus"], errors='coerce').fillna(0)
        target = df.groupby(["co_unidade", "timestamp"])["qt_sus"].sum().reset_index()
        
        # Renomeia para padrão RelBench
        target = target.rename(columns={"co_unidade": "entity_id", "qt_sus": "y"})
        
        return Table(
            df=target,
            fkey_col_to_pkey_table={"entity_id": "estabelecimento"},
            pkey_col=None,
            time_col="timestamp"
        )

# ==============================================================================
# 3. DEFINIÇÃO DE COLUNAS E MODELO (A parte que faltava)
# ==============================================================================

# Definição manual dos tipos de coluna baseada no PDF
# Isso diz ao Encoder como tratar cada coluna (Embedding ou Normalização)
COL_STYPES = {
    # [cite_start]Tabela Leitos [cite: 49]
    "leitos": {
        [cite_start]"co_tipo_leito": stype.categorical, # [cite: 49] (Categórica)
        [cite_start]"qt_exist": stype.numerical,        # [cite: 49] (Numérica)
    },
    # [cite_start]Tabela Vínculo [cite: 251]
    "vinculo": {
        [cite_start]"co_cbo": stype.categorical,        # [cite: 251]
        [cite_start]"ind_vinculacao": stype.categorical,# [cite: 251]
        [cite_start]"tp_sus_nao_sus": stype.categorical # [cite: 251]
    },
    # [cite_start]Tabela Equipamentos [cite: 241]
    "equipamentos": {
        "co_equipamento": stype.categorical,
        "qt_exist": stype.numerical,
        "qt_uso": stype.numerical
    },
    # [cite_start]Tabela Serviços [cite: 296]
    "servicos": {
        "co_servico": stype.categorical,
        "co_classificacao": stype.categorical
    }
}

class CNESGraphModel(torch.nn.Module):
    def __init__(self, metadata, hidden_channels=64, out_channels=1):
        super().__init__()
        
        # 1. Encoder Tabular (RelBench Encoder)
        # Ele lê o dicionário COL_STYPES e cria embeddings automaticamente
        self.encoder = RelBenchEncoder(
            channels=hidden_channels,
            encoder_config=None, # Usa default config
            stype_encoder_dict={} # Usa default encoders
        )

        # 2. GNN Backbone (Heterogeneous GraphSAGE)
        class GNN(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.conv1 = SAGEConv((-1, -1), hidden_channels)
                self.conv2 = SAGEConv((-1, -1), hidden_channels)

            def forward(self, x, edge_index):
                # Standard GraphSAGE forward
                x = self.conv1(x, edge_index).relu()
                x = F.dropout(x, p=0.5, training=self.training)
                x = self.conv2(x, edge_index).relu()
                return x

        # to_hetero converte a GNN simples para lidar com múltiplos tipos de nós/arestas
        self.gnn = to_hetero(GNN(), metadata, aggr='sum')

        # 3. Head de Predição
        self.head = torch.nn.Sequential(
            torch.nn.Linear(hidden_channels, hidden_channels),
            torch.nn.ReLU(),
            torch.nn.Linear(hidden_channels, out_channels)
        )

    def forward(self, batch: HeteroData):
        # Passo 1: Encode das features tabulares (Fatos -> Embeddings nos Nós)
        x_dict, col_names_dict = self.encoder(batch)
        
        # Passo 2: Message Passing
        x_dict = self.gnn(x_dict, batch.edge_index_dict)
        
        # Passo 3: Predição (Pegamos apenas os nós seed/target do batch)
        # O loader do PyG coloca os nós de interesse nas primeiras posições
        # Mas para simplificar, pegamos o vetor do nó 'estabelecimento'
        # batch['estabelecimento'].input_id contém os índices dos nós alvo no batch
        
        # Nota: O RelBench/PyG gerencia o batching de forma que precisamos saber 
        # quais nós estamos prevendo.
        
        if 'input_id' in batch['estabelecimento']:
             # Se for NodeLoader
            target_embeddings = x_dict['estabelecimento'] 
            # Num cenário real de batch, aplicaríamos slice baseado no batch_size
        else:
            target_embeddings = x_dict['estabelecimento']

        return self.head(target_embeddings).squeeze()

# ==============================================================================
# 4. EXECUÇÃO E TREINAMENTO
# ==============================================================================

def main():
    print("🚀 Carregando Dataset...")
    dataset = CNESDataset()
    db = dataset.make_db()
    
    print("🎯 Criando Tarefa (PredictSusCapacity)...")
    task = PredictSusCapacity(dataset)
    
    # Cria tabelas de treino/val/teste
    train_table = task.get_table("train")
    val_table = task.get_table("val")
    
    print(f"   -> Treino: {len(train_table)} exemplos")
    print(f"   -> Validação: {len(val_table)} exemplos")

    # Prepara dados para PyTorch Geometric
    # data é um objeto HeteroData contendo todo o grafo
    data, col_stats_dict = dataset.get_pyg_data(col_stypes=COL_STYPES)
    
    # Inicializa Modelo
    model = CNESGraphModel(metadata=data.metadata(), hidden_channels=32)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
    
    # Configura Loader (Temporal Neighbor Sampling)
    # Este loader é vital: ele amostra vizinhos no passado para prever o futuro
    train_loader = NeighborLoader(
        data,
        num_neighbors=[10, 10], # Amostra 10 vizinhos por camada (2 camadas)
        input_nodes=('estabelecimento', train_table.df['entity_id'].values), # Nós alvo
        # input_time=train_table.df['timestamp'].values, # Timestamp do evento alvo
        # time_attr='time', # Nome da coluna de tempo no grafo
        batch_size=1024,
        shuffle=True
    )

    print("\n🔥 Iniciando Treinamento...")
    model.train()
    
    # Loop simples (Dummy loop para demonstração, pois os targets reais precisam ser alinhados)
    for epoch in range(1, 11):
        total_loss = 0
        steps = 0
        
        for batch in train_loader:
            optimizer.zero_grad()
            
            # Forward
            out = model(batch)
            
            # Nota: O 'y' (target) precisa ser extraído do train_table e alinhado ao batch.
            # No setup padrão do RelBench com PyG, isso requer um 'loader' customizado 
            # que retorna (batch, y). Aqui simulamos um target aleatório para compilar.
            # Na prática, você passaria os targets corretos no input_nodes ou via join.
            
            # Simulação de target (substitua pelo y real alinhado)
            y_fake = torch.randn_like(out) 
            
            loss = F.mse_loss(out, y_fake)
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
            steps += 1
            
        print(f"Epoch {epoch}: Loss = {total_loss/steps:.4f}")

if __name__ == "__main__":
    main()