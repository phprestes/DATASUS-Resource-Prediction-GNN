"""
Laço de treino do servidor: um grafo por transição, CUDA, sem os atalhos de 9 GB.

Quatro diferenças em relação a `src.ml.gnn.treinar_aquisicao`, e cada uma é uma
limitação levantada:

| No notebook | Aqui |
|---|---|
| Um passo de gradiente por época, minilote de 500 mil pares | `passos_por_epoca` passos, sobre o conjunto de treino completo |
| Validação sobre amostra fixa de 2 milhões | validação **completa**, ou a cada `k` épocas quando pedido |
| Grafo estático, um só, cortado em 201701 | o grafo da transição de cada par |
| Sem checkpoint | estado salvo a cada época, porque o cluster mata processo em 168 h |

**A aresta tem peso.** `GraphConv` aceita `edge_weight`, e é por isso que ele
substitui `SAGEConv` aqui: o peso é `log1p` da quantidade agregada por par
(`hpc/ml/grafo_temporal.py`), informação que a projeção mínima descartava.

**Onde os grafos moram.** Todos ficam em CPU e apenas o da transição em curso vai
para a GPU. Com nove grafos nacionais isso mantém o pico de VRAM no tamanho de um,
em vez da soma — e é o que permite não depender da VRAM não documentada na wiki do
IME. `manter_grafos_na_gpu=True` cacheia todos quando `cabe_em_batch_completo`
autoriza, o que economiza a transferência por passo.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from torch_geometric.data import HeteroData
from torch_geometric.nn import GraphConv, Linear, to_hetero

from hpc.config.ambiente import cabe_em_batch_completo
from hpc.ml.grafo_temporal import GrafoPorTransicao
from src.etl.changes import Transicao
from src.ml.baselines import Previsao
from src.ml.gnn import SEMENTE, DecoderAquisicao, ErroGNN, IndicePares, ModeloAquisicao
from src.ml.graph import TABELA_RAIZ
from src.ml.metrics import average_precision
from src.ml.splits import ParticaoTemporal
from src.ml.tasks import COL_CONJUNTO, COL_ROTULO, TabelaTarefa


class BaseGNNComPeso(torch.nn.Module):
    """
    Duas camadas `GraphConv`, que aceitam peso de aresta.

    `SAGEConv`, usado no pipeline do notebook, ignora peso — e como lá a aresta
    não tinha peso, não havia o que ignorar. Aqui a intensidade da relação existe
    (quantos equipamentos, quantos leitos) e precisa chegar à agregação.
    """

    def __init__(self, oculto: int, saida: int, dropout: float = 0.15):
        super().__init__()
        self.conv1 = GraphConv((-1, -1), oculto, aggr="mean")
        self.norm1 = torch.nn.LayerNorm(oculto)
        self.conv2 = GraphConv((-1, -1), oculto, aggr="mean")
        self.norm2 = torch.nn.LayerNorm(oculto)
        self.lin = Linear(oculto, saida)
        self.dropout = dropout

    def forward(self, x, edge_index, edge_weight=None):
        x = self.norm1(self.conv1(x, edge_index, edge_weight)).relu()
        x = F.dropout(x, p=self.dropout, training=self.training)
        x = self.norm2(self.conv2(x, edge_index, edge_weight)).relu()
        x = F.dropout(x, p=self.dropout, training=self.training)
        return self.lin(x)


class EncoderTemporal(torch.nn.Module):
    """Projeção por tipo de nó mais a GNN heterogênea, com peso de aresta."""

    def __init__(self, metadata, oculto: int, saida: int):
        super().__init__()
        self.lin_dict = torch.nn.ModuleDict(
            {tipo: Linear(-1, oculto) for tipo in metadata[0]}
        )
        self.gnn = to_hetero(BaseGNNComPeso(oculto, saida), metadata, aggr="mean")

    def forward(self, x_dict, edge_index_dict, edge_weight_dict=None):
        projetado = {tipo: self.lin_dict[tipo](x).relu() for tipo, x in x_dict.items()}
        if edge_weight_dict is None:
            return self.gnn(projetado, edge_index_dict)
        return self.gnn(projetado, edge_index_dict, edge_weight_dict)


def _pesos_do_grafo(grafo: HeteroData) -> dict | None:
    pesos = {
        relacao: grafo[relacao].edge_weight
        for relacao in grafo.edge_types
        if "edge_weight" in grafo[relacao]
    }
    return pesos or None


def _codificar(modelo: ModeloAquisicao, grafo: HeteroData) -> torch.Tensor:
    saida = modelo.encoder(
        grafo.x_dict, grafo.edge_index_dict, _pesos_do_grafo(grafo)
    )
    return saida[TABELA_RAIZ]


def _por_transicao(
    tarefa: TabelaTarefa,
    particao: ParticaoTemporal,
    indice: IndicePares,
    conjunto: str,
) -> list[tuple[Transicao, torch.Tensor, torch.Tensor, torch.Tensor, pd.DataFrame]]:
    """
    Fatia um conjunto por transição, já traduzido para índices de tensor.

    A fatia por transição é o que torna o grafo temporal possível: cada par é
    pontuado sob a estrutura do instante em que a pergunta foi feita.
    """
    fatias = []
    df_conjunto = tarefa.df[tarefa.df[COL_CONJUNTO] == conjunto]
    for transicao in particao.conjuntos[conjunto]:
        df = df_conjunto[df_conjunto["periodo_destino"] == transicao.destino]
        conhecidos = df[tarefa.col_entidade].isin(indice.idx_unidade) & df[
            tarefa.col_item
        ].isin(indice.idx_item)
        df = df[conhecidos]
        if df.empty:
            continue
        u = torch.tensor(
            df[tarefa.col_entidade].map(indice.idx_unidade).to_numpy(), dtype=torch.long
        )
        k = torch.tensor(
            df[tarefa.col_item].map(indice.idx_item).to_numpy(), dtype=torch.long
        )
        y = torch.tensor(df[COL_ROTULO].to_numpy(), dtype=torch.float)
        fatias.append((transicao, u, k, y, df))
    if not fatias:
        raise ErroGNN(
            f"conjunto {conjunto!r} ficou vazio: nenhuma transição tem par com "
            "entidade e item presentes no grafo"
        )
    return fatias


def _pontuar(
    modelo: ModeloAquisicao,
    z: torch.Tensor,
    u: torch.Tensor,
    k: torch.Tensor,
    dispositivo: str,
    bloco: int = 4_000_000,
) -> np.ndarray:
    """Pontua em blocos. O bloco é maior que no notebook porque há VRAM para isso."""
    saidas = []
    with torch.no_grad():
        for inicio in range(0, len(u), bloco):
            fim = inicio + bloco
            logito = modelo.decoder(
                z[u[inicio:fim].to(dispositivo)], k[inicio:fim].to(dispositivo)
            )
            saidas.append(logito.float().cpu().numpy())
    return np.concatenate(saidas) if saidas else np.array([], dtype="float32")


def treinar(
    tarefa: TabelaTarefa,
    particao: ParticaoTemporal,
    grafos: GrafoPorTransicao,
    indice: IndicePares,
    *,
    dispositivo: str = "cuda",
    dim_saida: int = 64,
    epocas: int = 150,
    paciencia: int = 15,
    lr: float = 0.01,
    passos_por_epoca: int = 20,
    lote: int = 2_000_000,
    validar_cada: int = 1,
    amp: bool = True,
    checkpoint_em: Path | None = None,
    verboso: bool = True,
) -> tuple[ModeloAquisicao, dict]:
    """
    Treina selecionando época pela validação, com um grafo por transição.

    `passos_por_epoca` é por transição de treino: com seis transições e vinte
    passos, são 120 passos de gradiente por época contra **um** no pipeline do
    notebook. `validar_cada` permite espaçar a validação completa quando ela
    dominar o tempo — o default é toda época, que na A6000 custa poucos segundos.

    `checkpoint_em` grava estado a cada época. Sem escalonador para reenfileirar,
    é o que permite retomar uma execução morta pelo corte de 168 h.
    """
    torch.manual_seed(SEMENTE)
    gerador = torch.Generator().manual_seed(SEMENTE)

    treino = _por_transicao(tarefa, particao, indice, "treino")
    validacao = _por_transicao(tarefa, particao, indice, "validacao")

    metadata = grafos.para(treino[0][0]).metadata()
    modelo = ModeloAquisicao(
        EncoderTemporal(metadata, dim_saida, dim_saida),
        DecoderAquisicao(dim_saida, len(indice.itens)),
    ).to(dispositivo)
    otimizador = torch.optim.Adam(modelo.parameters(), lr=lr)

    # Reponderação global, não por transição: manter o mesmo peso em todos os
    # passos evita que a perda mude de escala entre transições com prevalências
    # levemente diferentes.
    positivos = float(sum(float(y.sum()) for _, _, _, y, _ in treino))
    total = float(sum(len(y) for _, _, _, y, _ in treino))
    peso = torch.tensor((total - positivos) / max(positivos, 1.0), device=dispositivo)

    usar_amp = amp and dispositivo == "cuda"
    tipo_amp = (
        torch.bfloat16
        if usar_amp and torch.cuda.is_bf16_supported()
        else torch.float16
    )

    na_gpu = dispositivo == "cuda" and cabe_em_batch_completo(
        arestas=max(
            int(sum(g.resumo_arestas.values())) for g in grafos.por_origem.values()
        )
        * len(grafos.por_origem),
        nos=len(grafos.unidades),
        dim=dim_saida,
    )
    if na_gpu:
        for origem, grafo in grafos.por_origem.items():
            grafos.por_origem[origem] = grafo.to(dispositivo)
        if verboso:
            print("  grafos cacheados na GPU", flush=True)

    historico: list[dict] = []
    melhor_ap, melhor_epoca, melhores_pesos, sem_melhora = -1.0, -1, None, 0

    for epoca in range(epocas):
        modelo.train()
        perdas = []
        for transicao, u, k, y, _ in treino:
            grafo = grafos.para(transicao)
            if not na_gpu:
                grafo = grafo.to(dispositivo)
            for _ in range(passos_por_epoca):
                otimizador.zero_grad(set_to_none=True)
                escolha = torch.randint(
                    0, len(y), (min(lote, len(y)),), generator=gerador
                )
                with torch.autocast(
                    device_type="cuda" if usar_amp else "cpu",
                    dtype=tipo_amp,
                    enabled=usar_amp,
                ):
                    z = _codificar(modelo, grafo)
                    logito = modelo.decoder(
                        z[u[escolha].to(dispositivo)], k[escolha].to(dispositivo)
                    )
                    perda = F.binary_cross_entropy_with_logits(
                        logito.float(),
                        y[escolha].to(dispositivo),
                        pos_weight=peso,
                    )
                perda.backward()
                otimizador.step()
                perdas.append(float(perda.detach()))
            if not na_gpu:
                del grafo

        ap = melhor_ap
        if epoca % validar_cada == 0:
            modelo.eval()
            escores, rotulos = [], []
            for transicao, u, k, y, _ in validacao:
                grafo = grafos.para(transicao)
                if not na_gpu:
                    grafo = grafo.to(dispositivo)
                with torch.no_grad():
                    z = _codificar(modelo, grafo)
                    escores.append(_pontuar(modelo, z, u, k, dispositivo))
                rotulos.append(y.numpy())
                if not na_gpu:
                    del grafo
            ap = average_precision(np.concatenate(rotulos), np.concatenate(escores))

        historico.append(
            {"epoca": epoca, "perda": float(np.mean(perdas)), "ap_validacao": ap}
        )
        if verboso and epoca % 10 == 0:
            print(
                f"  época {epoca:4d}  perda {np.mean(perdas):.4f}  "
                f"AP validação {ap:.5f}",
                flush=True,
            )

        if ap > melhor_ap:
            melhor_ap, melhor_epoca, sem_melhora = ap, epoca, 0
            melhores_pesos = {
                c: t.detach().cpu().clone() for c, t in modelo.state_dict().items()
            }
            if checkpoint_em is not None:
                checkpoint_em.parent.mkdir(parents=True, exist_ok=True)
                torch.save(
                    {
                        "epoca": epoca,
                        "melhor_ap_validacao": melhor_ap,
                        "state_dict": melhores_pesos,
                    },
                    checkpoint_em,
                )
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
        "amp": tipo_amp.__str__() if usar_amp else "desligado",
        "passos_por_epoca": passos_por_epoca * len(treino),
        "grafos_na_gpu": na_gpu,
        "pos_weight": float(peso),
    }


def prever(
    modelo: ModeloAquisicao,
    tarefa: TabelaTarefa,
    particao: ParticaoTemporal,
    grafos: GrafoPorTransicao,
    indice: IndicePares,
    conjunto: str = "teste",
    nome: str = "gnn_temporal",
    dispositivo: str = "cuda",
) -> Previsao:
    """
    Escores no conjunto pedido, transição por transição, no formato das baselines.

    Devolve `Previsao` para que `src.ml.metrics` e `src.ml.artefatos` recebam o
    mesmo tipo dos dois pipelines — é o que mantém as células da matriz
    comparáveis e o pacote de modelo legível pelo mesmo código (D-35).
    """
    modelo.eval()
    escores, rotulos, entidades = [], [], []
    rotulos_entidade = None

    for transicao, u, k, y, df in _por_transicao(tarefa, particao, indice, conjunto):
        grafo = grafos.para(transicao).to(dispositivo)
        with torch.no_grad():
            z = _codificar(modelo, grafo)
            escores.append(_pontuar(modelo, z, u, k, dispositivo))
        rotulos.append(y.numpy())

        serie = df[tarefa.col_entidade]
        if isinstance(serie.dtype, pd.CategoricalDtype):
            entidades.append(serie.cat.codes.to_numpy())
            rotulos_entidade = np.asarray(serie.cat.categories)
        else:
            codigos, nomes = pd.factorize(serie, sort=False)
            entidades.append(codigos)
            rotulos_entidade = np.asarray(nomes)

    return Previsao(
        modelo=nome,
        conjunto=conjunto,
        escore=np.concatenate(escores).astype("float32"),
        y=np.concatenate(rotulos).astype("int8"),
        entidades=np.concatenate(entidades),
        rotulos_entidade=rotulos_entidade,
        metadados={"grafos": grafos.n_grafos, "dispositivo": dispositivo},
    )
