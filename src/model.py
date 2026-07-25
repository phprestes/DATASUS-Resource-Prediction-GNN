import torch
from torch.nn import LayerNorm
import torch.nn.functional as F
from torch_geometric.nn import SAGEConv, to_hetero, Linear

class BaseGNN(torch.nn.Module):
    def __init__(self, hidden_channels, out_channels):
        super().__init__()
        self.conv1 = SAGEConv((-1, -1), hidden_channels)
        self.norm1 = LayerNorm(hidden_channels) # Escudo 1
        self.conv2 = SAGEConv((-1, -1), hidden_channels)
        self.norm2 = LayerNorm(hidden_channels) # Escudo 2
        self.lin = Linear(hidden_channels, out_channels)

    def forward(self, x, edge_index):
        x = self.conv1(x, edge_index).relu()
        x = self.norm1(x).relu()
        x = F.dropout(x, p=0.15, training=self.training)
        x = self.conv2(x, edge_index).relu()
        x = F.dropout(x, p=0.15, training=self.training)
        return self.lin(x)

class DynamicHeteroGNN(torch.nn.Module):
    def __init__(self, metadata, hidden_channels, out_channels):
        super().__init__()
        self.lin_dict = torch.nn.ModuleDict()
        for node_type in metadata[0]:
            self.lin_dict[node_type] = Linear(-1, hidden_channels)
            
        self.gnn = to_hetero(BaseGNN(hidden_channels, out_channels), metadata, aggr='mean')

    def forward(self, x_dict, edge_index_dict):
        x_dict_projected = {
            node_type: self.lin_dict[node_type](x).relu()
            for node_type, x in x_dict.items()
        }
        return self.gnn(x_dict_projected, edge_index_dict)

def train(model, optimizer, data, device, entity_table="tbEstabelecimento"):
    model.train()
    data = data.to(device)
    optimizer.zero_grad()
    
    # O forward de um modelo heterogêneo recebe o dicionário de nós e arestas diretamente do grafo
    out = model(data.x_dict, data.edge_index_dict)
    
    # Mascara apenas os nós de destino que fazem parte da janela de treino
    train_mask = data[entity_table].train_mask
    pred = out[entity_table][train_mask].squeeze(-1)
    target = data[entity_table].y[train_mask].float()
    
    loss = F.mse_loss(pred, target)
    loss.backward()
    optimizer.step()
    
    return float(loss)

def test(model, data, device, entity_table="tbEstabelecimento"):
    model.eval()
    data = data.to(device)
    
    with torch.no_grad():
        out = model(data.x_dict, data.edge_index_dict)
        # Assumindo o uso da mesma máscara para demonstração (ou crie data_val)
        test_mask = data[entity_table].train_mask 
        pred = out[entity_table][test_mask].squeeze(-1)
        target = data[entity_table].y[test_mask].float()
        
        val_loss = F.mse_loss(pred, target)
        
    return float(val_loss) ** 0.5
