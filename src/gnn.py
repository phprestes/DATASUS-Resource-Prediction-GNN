"""
Trilhas 2 e 3: redes neurais de grafo sobre a rede de saúde.

Substitui `src/model.py`. Mantém `DynamicHeteroGNN`, cuja projeção
`Linear(-1, hidden)` por tipo de nó resolve bem larguras heterogêneas de
feature, e conserta o erro central: `test()` avaliava sobre `train_mask`, então o
número reportado como desempenho de teste era desempenho de treino (D-11).

Duas decisões de projeto que valem explicitar:

**1. O decoder é o mesmo nas duas trilhas.** Tanto a trilha relacional quanto a
geográfica produzem um embedding por estabelecimento e o combinam com um
embedding aprendido do tipo de equipamento. Só o encoder difere. Sem isso, uma
diferença de resultado entre trilhas poderia vir do decoder e não da estrutura,
que é o que o experimento quer medir.

**2. O grafo heterogêneo é montado direto das chaves estrangeiras.** O caminho
canônico do RelBench (`make_pkey_fkey_graph`) exige a pilha `torch_frame` com
`col_to_stype` declarado por coluna. Aqui as arestas vêm de `CNES_FKEY` e as
features de uma codificação simples. É menos maquinaria e mais legível, ao custo
de não usar os encoders de coluna do torch_frame — anotado como extensão.

As funções de predição devolvem `src.baselines.Previsao`, o mesmo tipo das
baselines, para que `src.metrics.tabela_de_resultados` receba tudo junto e a
regra de reporte de D-11 seja o caminho mais curto.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from torch.nn import Embedding, LayerNorm, ModuleDict
from torch_geometric.data import Data, HeteroData
from torch_geometric.nn import Linear, SAGEConv, to_hetero
from relbench.base import Database

from src.baselines import Previsao
from src.graph import COL_ENTIDADE, GrafoGeografico
from src.splits import ParticaoTemporal
from src.tasks import COL_CONJUNTO, COL_ROTULO, TabelaTarefa

SEMENTE = 42


class ErroGNN(RuntimeError):
    """Treino ou montagem de grafo impossível com os dados fornecidos."""


# ---------------------------------------------------------------------------
# Encoders
# ---------------------------------------------------------------------------


class BaseGNN(torch.nn.Module):
    """Duas camadas SAGE com normalização e dropout. Herdada de src/model.py."""

    def __init__(self, hidden_channels: int, out_channels: int, dropout: float = 0.15):
        super().__init__()
        self.conv1 = SAGEConv((-1, -1), hidden_channels)
        self.norm1 = LayerNorm(hidden_channels)
        self.conv2 = SAGEConv((-1, -1), hidden_channels)
        self.norm2 = LayerNorm(hidden_channels)
        self.lin = Linear(hidden_channels, out_channels)
        self.dropout = dropout

    def forward(self, x, edge_index):
        x = self.norm1(self.conv1(x, edge_index)).relu()
        x = F.dropout(x, p=self.dropout, training=self.training)
        x = self.norm2(self.conv2(x, edge_index)).relu()
        x = F.dropout(x, p=self.dropout, training=self.training)
        return self.lin(x)


class DynamicHeteroGNN(torch.nn.Module):
    """
    Encoder heterogêneo: projeta cada tipo de nó e aplica a GNN convertida.

    A projeção `Linear(-1, hidden)` por tipo de nó é o que permite que tabelas
    com números diferentes de colunas coexistam no mesmo grafo sem padding
    manual.
    """

    def __init__(self, metadata, hidden_channels: int, out_channels: int):
        super().__init__()
        self.lin_dict = ModuleDict(
            {tipo: Linear(-1, hidden_channels) for tipo in metadata[0]}
        )
        self.gnn = to_hetero(
            BaseGNN(hidden_channels, out_channels), metadata, aggr="mean"
        )

    def forward(self, x_dict, edge_index_dict):
        projetado = {
            tipo: self.lin_dict[tipo](x).relu() for tipo, x in x_dict.items()
        }
        return self.gnn(projetado, edge_index_dict)


class GNNGeografica(torch.nn.Module):
    """
    Encoder homogêneo sobre o grafo de proximidade física (trilha 3).

    Ignora a estrutura de tabelas por construção: o único sinal estrutural é
    quem está perto de quem. É a formulação mais direta da hipótese de que
    escassez é um fenômeno de vizinhança.
    """

    def __init__(self, in_channels: int, hidden_channels: int, out_channels: int):
        super().__init__()
        self.proj = Linear(in_channels, hidden_channels)
        self.gnn = BaseGNN(hidden_channels, out_channels)

    def forward(self, x, edge_index):
        return self.gnn(self.proj(x).relu(), edge_index)


# ---------------------------------------------------------------------------
# Decoder compartilhado
# ---------------------------------------------------------------------------


class DecoderAquisicao(torch.nn.Module):
    """
    Pontua o par (estabelecimento, tipo de item) a partir do embedding do nó.

    Concatena o embedding do estabelecimento com um embedding aprendido do tipo
    de item e passa por um MLP. Idêntico nas duas trilhas — só o encoder que
    produz `z_estabelecimento` muda.
    """

    def __init__(self, dim_no: int, n_itens: int, dim_item: int = 32, oculto: int = 64):
        super().__init__()
        self.emb_item = Embedding(n_itens, dim_item)
        self.mlp = torch.nn.Sequential(
            torch.nn.Linear(dim_no + dim_item, oculto),
            torch.nn.ReLU(),
            torch.nn.Linear(oculto, 1),
        )

    def forward(self, z_no: torch.Tensor, idx_item: torch.Tensor) -> torch.Tensor:
        return self.mlp(torch.cat([z_no, self.emb_item(idx_item)], dim=-1)).squeeze(-1)


class ModeloAquisicao(torch.nn.Module):
    """Encoder de grafo mais decoder de par, treinados juntos."""

    def __init__(self, encoder: torch.nn.Module, decoder: DecoderAquisicao):
        super().__init__()
        self.encoder = encoder
        self.decoder = decoder


# ---------------------------------------------------------------------------
# Montagem dos tensores
# ---------------------------------------------------------------------------


@dataclass
class IndicePares:
    """
    Tradução entre os identificadores da tarefa e os índices dos tensores.

    Guardada explicitamente porque a fonte de erro mais comum neste tipo de
    código é embaralhar a ordem entre `y`, `escore` e os nós do grafo — e o
    sintoma é uma métrica plausível mas sem sentido.
    """

    unidades: list[str]
    itens: list[str]
    idx_unidade: dict[str, int]
    idx_item: dict[str, int]

    @classmethod
    def de(cls, unidades: list[str], itens: list[str]) -> "IndicePares":
        return cls(
            unidades=unidades,
            itens=itens,
            idx_unidade={u: i for i, u in enumerate(unidades)},
            idx_item={k: i for i, k in enumerate(itens)},
        )


def features_de_estabelecimento(
    db: Database, unidades: list[str], ate_periodo: str | None = None
) -> torch.Tensor:
    """
    Matriz de features por estabelecimento, na ordem de `unidades`.

    Codifica as colunas categóricas da tabela raiz como códigos inteiros e as
    numéricas como float, tomando a observação mais recente até `ate_periodo`.
    O corte por período é o que impede vazamento: as features do treino não
    podem enxergar snapshots posteriores ao fim da janela de treino.
    """
    from src.graph import COL_TEMPO, TABELA_RAIZ, data_do_periodo

    df = db.table_dict[TABELA_RAIZ].df.to_pandas()
    if ate_periodo:
        df = df[df[COL_TEMPO] <= data_do_periodo(ate_periodo)]
    if df.empty:
        raise ErroGNN(
            f"nenhuma linha de {TABELA_RAIZ} até {ate_periodo}; sem features "
            "não há o que treinar"
        )

    df = df.sort_values(COL_TEMPO).groupby(COL_ENTIDADE, as_index=False).last()
    df = df.set_index(COL_ENTIDADE).reindex(unidades)

    colunas = [c for c in df.columns if c != COL_TEMPO]
    matriz = []
    for coluna in colunas:
        serie = df[coluna]
        if pd.api.types.is_numeric_dtype(serie):
            matriz.append(serie.astype(float).fillna(-1.0).to_numpy())
        else:
            codigos = pd.Categorical(serie.astype("string")).codes
            matriz.append(codigos.astype(float))

    return torch.tensor(np.stack(matriz, axis=1), dtype=torch.float)


def grafo_geografico_para_data(
    grafo: GrafoGeografico, features: torch.Tensor
) -> Data:
    """Converte o grafo de proximidade para o formato do PyTorch Geometric."""
    arestas = grafo.arestas.to_pandas()
    edge_index = torch.tensor(
        np.stack([arestas["origem"].to_numpy(), arestas["destino"].to_numpy()]),
        dtype=torch.long,
    )
    return Data(x=features, edge_index=edge_index)


def grafo_relacional_para_data(
    db: Database, unidades: list[str], features: torch.Tensor
) -> HeteroData:
    """
    Monta o HeteroData a partir das chaves estrangeiras do Database.

    Cada tabela filha vira um tipo de nó, e cada chave estrangeira uma relação.
    As features de nó das filhas são as colunas numéricas da própria tabela; as
    categóricas entram como códigos. É uma codificação deliberadamente simples —
    ver a nota 2 no topo do módulo.
    """
    from src.graph import TABELA_RAIZ

    dados = HeteroData()
    dados[TABELA_RAIZ].x = features
    idx_unidade = {u: i for i, u in enumerate(unidades)}

    for nome, tabela in db.table_dict.items():
        if nome == TABELA_RAIZ:
            continue
        fkeys = tabela.fkey_col_to_pkey_table or {}
        if COL_ENTIDADE not in fkeys:
            continue

        df = tabela.df.to_pandas()
        df = df[df[COL_ENTIDADE].isin(idx_unidade)]
        if df.empty:
            continue

        numericas = [
            c
            for c in df.columns
            if c != COL_ENTIDADE and pd.api.types.is_numeric_dtype(df[c])
        ]
        x = (
            torch.tensor(
                df[numericas].astype(float).fillna(-1.0).to_numpy(), dtype=torch.float
            )
            if numericas
            else torch.ones((len(df), 1), dtype=torch.float)
        )
        dados[nome].x = x

        destino = torch.tensor(
            df[COL_ENTIDADE].map(idx_unidade).to_numpy(), dtype=torch.long
        )
        origem = torch.arange(len(df), dtype=torch.long)
        dados[nome, "pertence_a", TABELA_RAIZ].edge_index = torch.stack([origem, destino])
        dados[TABELA_RAIZ, "tem", nome].edge_index = torch.stack([destino, origem])

    if not dados.edge_types:
        raise ErroGNN(
            "grafo relacional sem aresta alguma. Confira se as tabelas filhas "
            "têm co_unidade e se o filtro de município não zerou tudo."
        )
    return dados


# ---------------------------------------------------------------------------
# Treino e avaliação
# ---------------------------------------------------------------------------


def _tensores_da_tarefa(
    tarefa: TabelaTarefa, indice: IndicePares, conjunto: str
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, pd.DataFrame]:
    """
    Traduz um conjunto da tarefa para índices de tensor, preservando a ordem.

    Devolve também o DataFrame filtrado, para que `Previsao` carregue as
    entidades na mesma ordem dos escores. Descarta pares cuja entidade ou item
    não estão no grafo — um estabelecimento sem coordenada válida, por exemplo,
    não é nó da trilha geográfica.
    """
    df = tarefa.por_conjunto(conjunto)
    conhecidos = df[tarefa.col_entidade].isin(indice.idx_unidade) & df[
        tarefa.col_item
    ].isin(indice.idx_item)
    df = df[conhecidos]
    if df.empty:
        raise ErroGNN(
            f"conjunto {conjunto!r} ficou vazio depois de descartar entidades e "
            "itens ausentes do grafo"
        )

    return (
        torch.tensor(
            df[tarefa.col_entidade].map(indice.idx_unidade).to_numpy(), dtype=torch.long
        ),
        torch.tensor(
            df[tarefa.col_item].map(indice.idx_item).to_numpy(), dtype=torch.long
        ),
        torch.tensor(df[COL_ROTULO].to_numpy(), dtype=torch.float),
        df,
    )


def _codificar_grafo(modelo: ModeloAquisicao, dados, tabela_raiz: str) -> torch.Tensor:
    """Roda o encoder e devolve o embedding dos estabelecimentos."""
    if isinstance(dados, HeteroData):
        saida = modelo.encoder(dados.x_dict, dados.edge_index_dict)
        return saida[tabela_raiz]
    return modelo.encoder(dados.x, dados.edge_index)


def treinar_aquisicao(
    tarefa: TabelaTarefa,
    particao: ParticaoTemporal,
    dados,
    indice: IndicePares,
    dim_saida: int = 64,
    epocas: int = 200,
    lr: float = 0.01,
    paciencia: int = 20,
    dispositivo: str | None = None,
    verboso: bool = False,
) -> tuple[ModeloAquisicao, dict]:
    """
    Treina o modelo de aquisição, selecionando época pela **validação**.

    A parada antecipada olha o AP de validação, nunca o de teste. Esse é o ponto
    que o código anterior errava: `test()` avaliava sobre `train_mask`, então não
    havia separação alguma entre ajustar e medir.

    Devolve o modelo com os pesos da melhor época de validação, e o histórico.
    """
    torch.manual_seed(SEMENTE)
    dispositivo = dispositivo or ("cuda" if torch.cuda.is_available() else "cpu")

    from src.graph import TABELA_RAIZ
    from src.metrics import average_precision

    dados = dados.to(dispositivo)
    dim_no = dim_saida
    encoder = (
        DynamicHeteroGNN(dados.metadata(), dim_saida, dim_no)
        if isinstance(dados, HeteroData)
        else GNNGeografica(dados.x.size(1), dim_saida, dim_no)
    )
    modelo = ModeloAquisicao(
        encoder, DecoderAquisicao(dim_no, len(indice.itens))
    ).to(dispositivo)

    conjuntos = {
        nome: _tensores_da_tarefa(tarefa, indice, nome)
        for nome in ("treino", "validacao")
    }
    otimizador = torch.optim.Adam(modelo.parameters(), lr=lr)

    # Positivos são raros; sem reponderação a perda é minimizada prevendo sempre
    # zero, que é exatamente a baseline de persistência.
    y_treino = conjuntos["treino"][2]
    positivos = float(y_treino.sum())
    peso = torch.tensor(
        (len(y_treino) - positivos) / max(positivos, 1.0), device=dispositivo
    )

    historico: list[dict] = []
    melhor_ap, melhor_epoca, melhores_pesos, sem_melhora = -1.0, -1, None, 0

    for epoca in range(epocas):
        modelo.train()
        otimizador.zero_grad()
        z = _codificar_grafo(modelo, dados, TABELA_RAIZ)
        u, k, y, _ = conjuntos["treino"]
        logito = modelo.decoder(z[u.to(dispositivo)], k.to(dispositivo))
        perda = F.binary_cross_entropy_with_logits(
            logito, y.to(dispositivo), pos_weight=peso
        )
        perda.backward()
        otimizador.step()

        modelo.eval()
        with torch.no_grad():
            z = _codificar_grafo(modelo, dados, TABELA_RAIZ)
            u_v, k_v, y_v, _ = conjuntos["validacao"]
            escore = torch.sigmoid(
                modelo.decoder(z[u_v.to(dispositivo)], k_v.to(dispositivo))
            )
            ap = average_precision(y_v.numpy(), escore.cpu().numpy())

        historico.append(
            {"epoca": epoca, "perda": float(perda.detach()), "ap_validacao": ap}
        )
        if verboso and epoca % 20 == 0:
            print(f"época {epoca:4d}  perda {float(perda):.4f}  AP validação {ap:.4f}")

        if ap > melhor_ap:
            melhor_ap, melhor_epoca, sem_melhora = ap, epoca, 0
            melhores_pesos = {c: t.detach().clone() for c, t in modelo.state_dict().items()}
        else:
            sem_melhora += 1
            if sem_melhora >= paciencia:
                break

    if melhores_pesos is None:
        raise ErroGNN("treino não completou nenhuma época com AP de validação finito")
    modelo.load_state_dict(melhores_pesos)

    return modelo, {
        "melhor_epoca": melhor_epoca,
        "melhor_ap_validacao": melhor_ap,
        "epocas_rodadas": len(historico),
        "historico": pd.DataFrame(historico),
        "dispositivo": dispositivo,
        "pos_weight": float(peso),
    }


def prever_aquisicao(
    modelo: ModeloAquisicao,
    tarefa: TabelaTarefa,
    dados,
    indice: IndicePares,
    conjunto: str = "teste",
    nome: str = "gnn",
    dispositivo: str | None = None,
) -> Previsao:
    """
    Escores num conjunto ainda não visto, no mesmo formato das baselines.

    Devolver `Previsao` é o que permite jogar GNN e baselines na mesma tabela de
    `src.metrics.tabela_de_resultados` — a regra de reporte de D-11 vira o
    caminho de menor esforço em vez de disciplina manual.
    """
    from src.graph import TABELA_RAIZ

    dispositivo = dispositivo or next(modelo.parameters()).device.type
    dados = dados.to(dispositivo)
    u, k, y, df = _tensores_da_tarefa(tarefa, indice, conjunto)

    modelo.eval()
    with torch.no_grad():
        z = _codificar_grafo(modelo, dados, TABELA_RAIZ)
        escore = torch.sigmoid(
            modelo.decoder(z[u.to(dispositivo)], k.to(dispositivo))
        )

    return Previsao(
        modelo=nome,
        conjunto=conjunto,
        escore=escore.cpu().numpy(),
        y=y.numpy(),
        entidades=df[tarefa.col_entidade].to_numpy(),
        metadados={
            "n_nos": int(dados[TABELA_RAIZ].num_nodes)
            if isinstance(dados, HeteroData)
            else int(dados.num_nodes),
            "pares_avaliados": int(len(df)),
            "pares_descartados": int(len(tarefa.por_conjunto(conjunto)) - len(df)),
        },
    )
