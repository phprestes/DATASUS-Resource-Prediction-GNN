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

As funções de predição devolvem `src.ml.baselines.Previsao`, o mesmo tipo das
baselines, para que `src.ml.metrics.tabela_de_resultados` receba tudo junto e a
regra de reporte de D-11 seja o caminho mais curto.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import pyarrow.compute as pc
import torch
import torch.nn.functional as F
from torch.nn import Embedding, LayerNorm, ModuleDict
from torch_geometric.data import Data, HeteroData
from torch_geometric.nn import Linear, SAGEConv, to_hetero
from relbench.base import Database

from src.ml.baselines import Previsao
from src.ml.graph import COL_ENTIDADE, GrafoGeografico
from src.ml.splits import ParticaoTemporal
from src.ml.tasks import COL_CONJUNTO, COL_ROTULO, TabelaTarefa

SEMENTE = 42


class ErroGNN(RuntimeError):
    """Treino ou montagem de grafo impossível com os dados fornecidos."""


# ---------------------------------------------------------------------------
# Encoders
# ---------------------------------------------------------------------------


class BaseGNN(torch.nn.Module):
    """Duas camadas SAGE com normalização e dropout. Herdada de src/model.py."""

    def __init__(self, hidden_channels: int, out_channels: int, dropout: float = 0.15):
        """
        Args:
            hidden_channels: dimensão das duas camadas de convolução.
            out_channels: dimensão do embedding de saída.
            dropout: taxa aplicada depois de cada convolução, só em treino.
        """
        super().__init__()
        self.conv1 = SAGEConv((-1, -1), hidden_channels)
        self.norm1 = LayerNorm(hidden_channels)
        self.conv2 = SAGEConv((-1, -1), hidden_channels)
        self.norm2 = LayerNorm(hidden_channels)
        self.lin = Linear(hidden_channels, out_channels)
        self.dropout = dropout

    def forward(self, x, edge_index):
        """
        Args:
            x: features de nó.
            edge_index: arestas em formato `(2, E)`.

        Returns:
            Embedding por nó, com `out_channels` dimensões.
        """
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
        """
        Args:
            metadata: par `(tipos_de_no, tipos_de_aresta)`, como
                `HeteroData.metadata()` devolve.
            hidden_channels: dimensão da projeção e das convoluções.
            out_channels: dimensão do embedding de saída.
        """
        super().__init__()
        self.lin_dict = ModuleDict(
            {tipo: Linear(-1, hidden_channels) for tipo in metadata[0]}
        )
        self.gnn = to_hetero(
            BaseGNN(hidden_channels, out_channels), metadata, aggr="mean"
        )

    def forward(self, x_dict, edge_index_dict):
        """
        Args:
            x_dict: features por tipo de nó.
            edge_index_dict: arestas por tipo de relação.

        Returns:
            Mapa `{tipo_de_no: embedding}`. O do tipo raiz é o que o decoder usa.
        """
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
        """
        Args:
            in_channels: número de colunas das features de estabelecimento.
            hidden_channels: dimensão da projeção e das convoluções.
            out_channels: dimensão do embedding de saída.
        """
        super().__init__()
        self.proj = Linear(in_channels, hidden_channels)
        self.gnn = BaseGNN(hidden_channels, out_channels)

    def forward(self, x, edge_index):
        """
        Args:
            x: features dos estabelecimentos posicionáveis.
            edge_index: arestas do kNN geográfico, já simetrizadas.

        Returns:
            Embedding por estabelecimento.
        """
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
        """
        Args:
            dim_no: dimensão do embedding de estabelecimento vindo do encoder.
            n_itens: tamanho do vocabulário de itens. **Indexado por posição**,
                então a ordem de `IndicePares.itens` é parte dos pesos (D-35).
            dim_item: dimensão do embedding aprendido de item.
            oculto: largura da camada escondida do MLP.
        """
        super().__init__()
        self.emb_item = Embedding(n_itens, dim_item)
        self.mlp = torch.nn.Sequential(
            torch.nn.Linear(dim_no + dim_item, oculto),
            torch.nn.ReLU(),
            torch.nn.Linear(oculto, 1),
        )

    def forward(self, z_no: torch.Tensor, idx_item: torch.Tensor) -> torch.Tensor:
        """
        Args:
            z_no: embedding do estabelecimento de cada par, forma `(N, dim_no)`.
            idx_item: índice do item de cada par, forma `(N,)`.

        Returns:
            Logito por par, forma `(N,)`. Sem sigmoide — a perda usada é
            `binary_cross_entropy_with_logits`.
        """
        return self.mlp(torch.cat([z_no, self.emb_item(idx_item)], dim=-1)).squeeze(-1)


class ModeloAquisicao(torch.nn.Module):
    """Encoder de grafo mais decoder de par, treinados juntos."""

    def __init__(self, encoder: torch.nn.Module, decoder: DecoderAquisicao):
        """
        Args:
            encoder: `DynamicHeteroGNN` na trilha 2, `GNNGeografica` na trilha 3.
            decoder: o mesmo nas duas trilhas, para que a diferença de resultado
                não possa vir do decoder.
        """
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
        """
        Constrói o índice a partir das duas listas ordenadas.

        Args:
            unidades: `co_unidade` **na ordem em que o grafo tem os nós**. Ordem
                diferente da do grafo produz um modelo que carrega sem erro e
                pontua lixo.
            itens: vocabulário de itens, na ordem que o embedding vai usar.

        Returns:
            Índice com as duas listas e os dois mapas de tradução.
        """
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

    Args:
        db: `Database` de onde sai a tabela raiz.
        unidades: `co_unidade` na ordem desejada das linhas. Unidade ausente do
            recorte até o corte sai com a linha toda nula, o que no estado
            acontece com 45% dos nós (D-32).
        ate_periodo: competência limite, inclusive. `None` usa a série inteira, o
            que só é correto fora de contexto de treino.

    Returns:
        Tensor `float` de forma `(len(unidades), n_colunas)`. Categórica vira
        código inteiro em float; numérica ausente vira -1.

    Raises:
        ErroGNN: nenhuma linha da tabela raiz até o corte.
    """
    from src.ml.graph import COL_TEMPO, TABELA_RAIZ, data_do_periodo

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
    """
    Converte o grafo de proximidade para o formato do PyTorch Geometric.

    Args:
        grafo: `GrafoGeografico` com as arestas já simetrizadas.
        features: matriz de features na ordem de `grafo.unidades`.

    Returns:
        `Data` homogêneo. Sem peso de aresta: `SAGEConv` o ignoraria, e a
        distância só entra como critério de existência da aresta.
    """
    arestas = grafo.arestas.to_pandas()
    edge_index = torch.tensor(
        np.stack([arestas["origem"].to_numpy(), arestas["destino"].to_numpy()]),
        dtype=torch.long,
    )
    return Data(x=features, edge_index=edge_index)


# Prefixo das colunas de município das tabelas filhas. `COL_MUNICIPIO` do
# `graph.py` é `co_municipio_gestor`, que só existe na raiz.
PREFIXO_MUNICIPIO = "co_municipio"


def _e_categoria_de_relacao(coluna: str, dtypes: dict[str, str]) -> bool:
    """
    Se a coluna pode ser o vocabulário de categorias de uma tabela de fato.

    Exige `dtype` `category` — sequencial, data e código livre têm cardinalidade
    da ordem do número de linhas e viram um nó por linha, que é justamente o que
    D-25 removeu. E exclui município: é localização, e um nó por município liga
    todos os estabelecimentos da cidade entre si.

    Args:
        coluna: nome da coluna a avaliar.
        dtypes: mapa `{coluna: dtype}` da tabela, vindo de `CNES_DTYPES`.

    Returns:
        `True` se a coluna serve de vocabulário: é `category`, não é a chave da
        entidade e não é município.
    """
    return (
        dtypes.get(coluna) == "category"
        and coluna != COL_ENTIDADE
        and not coluna.startswith(PREFIXO_MUNICIPIO)
    )


def escolher_categoria(tabela: str) -> str | None:
    """
    Coluna que define o vocabulário de categorias de uma tabela de fato.

    Prefere a chave natural declarada em `docs/01-selecao-tabelas.md`, porque ela
    é exatamente o que identifica a linha além do estabelecimento — mas só a
    parte dela que é categoria de fato. Desde D-38 as 44 tabelas de fato têm chave
    natural declarada, e várias começam por `co_municipio` ou trazem sequenciais
    (`co_seq_central`, `sq_acolhimento`): tomar `natural[0]` cegamente escolheria
    essas. Sem componente aproveitável, cai para a coluna `category` da tabela.

    Args:
        tabela: nome da tabela de fato.

    Returns:
        Nome da coluna escolhida, ou `None` se a tabela não tem nenhuma coluna
        aproveitável — caso em que ela não entra no grafo como relação.
    """
    from src.config.schema import CNES_DTYPES, CNES_NATURAL_KEY, CNES_USEFUL_COLUMNS

    dtypes = CNES_DTYPES.get(tabela, {})
    natural = [
        c
        for c in CNES_NATURAL_KEY.get(tabela, ())
        if _e_categoria_de_relacao(c, dtypes)
    ]
    if natural:
        return natural[0]

    candidatas = [
        c for c in CNES_USEFUL_COLUMNS.get(tabela, []) if _e_categoria_de_relacao(c, dtypes)
    ]
    if candidatas:
        return candidatas[0]

    # Último recurso: município. Pior que nada só quando a tabela não tem
    # nenhuma outra categoria — é o caso das três tabelas `rlMun*`.
    municipio = [
        c
        for c in CNES_USEFUL_COLUMNS.get(tabela, [])
        if dtypes.get(c) == "category" and c != COL_ENTIDADE
    ]
    return municipio[0] if municipio else None


def _features_de_categoria(n: int, dim: int = 32, semente: int = SEMENTE) -> torch.Tensor:
    """
    Vetores fixos e distinguíveis, um por categoria.

    Nós de categoria não têm atributos próprios: são apenas identidades. Dar a
    todos o mesmo vetor de uns os tornaria indistinguíveis depois da projeção
    linear, e a GNN não conseguiria diferenciar tomógrafo de aparelho de raio-X.

    A alternativa óbvia, one-hot, custaria uma matriz `n × n` — inviável para os
    vocabulários maiores. Usa-se então uma projeção aleatória fixa, que preserva
    distinguibilidade em dimensão baixa e é determinística pela semente.

    Args:
        n: tamanho do vocabulário de categorias.
        dim: dimensão desejada. Reduzida a `n` quando o vocabulário é menor.
        semente: semente da projeção. Fixa, senão os nós de categoria mudariam
            de representação entre execuções.

    Returns:
        Tensor `(n, min(dim, n))` com a projeção aleatória fixa.
    """
    gerador = torch.Generator().manual_seed(semente)
    return torch.randn((n, min(dim, max(n, 1))), generator=gerador)


def grafo_relacional_para_data(
    db: Database,
    unidades: list[str],
    features: torch.Tensor,
    ate_periodo: str | None = None,
    min_arestas: int = 100,
) -> HeteroData:
    """
    Monta o HeteroData tratando as tabelas de fato como **listas de arestas**.

    Esta é a correção de uma modelagem errada que só ficou visível ao expandir o
    recorte. A versão anterior criava **um nó por linha** de tabela filha. No
    município isso dava algumas centenas de milhares de nós e passava; no estado
    dá 28 milhões, o que é inviável — e, mais importante, é conceitualmente
    errado.

    Uma linha de `rlEstabEquipamento` não é uma entidade: é a afirmação de que
    um estabelecimento tem um **tipo** de equipamento. A maioria das tabelas de
    fato do CNES é assim, uma lista de arestas entre o estabelecimento e um
    código de um vocabulário pequeno — 99 tipos de equipamento, 69 tipos de
    leito, 72 serviços. Modelando desse jeito, os 28 milhões de nós viram cerca
    de 20 mil nós de categoria e um número comparável de arestas.

    O ganho não é só de custo. Com um nó por linha, duas unidades com o mesmo
    tomógrafo não compartilhavam nenhum vizinho, e a GNN não tinha por onde
    propagar informação entre elas. Com nó por categoria, o tomógrafo é um
    vizinho comum — que é exatamente a estrutura que a trilha 2 existe para
    testar.

    `ate_periodo` é obrigatório e deve ser
    `ParticaoTemporal.antes_de_todos_os_rotulos`, **não** `fim_do_treino`. O
    grafo aqui é estático: uma única estrutura serve treino, validação e teste.
    Cortá-lo em `fim_do_treino` deixaria a transição de treino que termina nesse
    período com o rótulo escrito no grafo, porque a aresta entre estabelecimento
    e equipamento em `t+1` é exatamente o alvo. Ver D-25.

    Args:
        db: `Database` de onde saem a raiz e as tabelas de fato.
        unidades: `co_unidade` na ordem dos índices de nó.
        features: matriz de features da raiz, na ordem de `unidades`.
        ate_periodo: **obrigatório**, e tem de ser
            `ParticaoTemporal.antes_de_todos_os_rotulos`. Ver a explicação acima.
        min_arestas: relações com menos arestas que isso são descartadas, por
            serem raras demais para contribuir.

    Returns:
        `HeteroData` com um tipo de nó por vocabulário de categoria mais a raiz,
        e uma relação por tabela de fato aproveitável. No estado dá 25 tipos de
        nó e 48 relações.

    Raises:
        ErroGNN: `ate_periodo` não foi passado. A recusa é deliberada — o default
            silencioso deixaria o rótulo dentro do grafo (D-25).
    """
    from src.ml.graph import COL_TEMPO, TABELA_RAIZ, data_do_periodo

    if ate_periodo is None:
        raise ErroGNN(
            "grafo relacional estático exige `ate_periodo`. Passe "
            "`particao.antes_de_todos_os_rotulos` — usar `fim_do_treino` coloca "
            "o rótulo dentro do grafo (D-25)."
        )

    dados = HeteroData()
    dados[TABELA_RAIZ].x = features
    idx_unidade = {u: i for i, u in enumerate(unidades)}
    limite = data_do_periodo(ate_periodo)
    resumo: dict[str, int] = {}

    for nome, tabela in db.table_dict.items():
        if nome == TABELA_RAIZ:
            continue
        if COL_ENTIDADE not in (tabela.fkey_col_to_pkey_table or {}):
            continue
        coluna = escolher_categoria(nome)
        if coluna is None or coluna not in tabela.df.column_names:
            continue

        # Projeta só as três colunas necessárias antes de sair do pyarrow: a
        # tabela inteira em pandas custaria gigabytes nas maiores.
        fatia = tabela.df.select([COL_ENTIDADE, coluna, COL_TEMPO])
        if limite is not None:
            fatia = fatia.filter(pc.less_equal(pc.field(COL_TEMPO), limite))
        if fatia.num_rows == 0:
            continue

        pares = (
            fatia.select([COL_ENTIDADE, coluna])
            .to_pandas()
            .dropna()
            .drop_duplicates()
        )
        pares = pares[pares[COL_ENTIDADE].isin(idx_unidade)]
        if len(pares) < min_arestas:
            continue

        categorias = pd.Categorical(pares[coluna])
        origem = torch.as_tensor(
            pares[COL_ENTIDADE].map(idx_unidade).to_numpy(), dtype=torch.long
        )
        destino = torch.as_tensor(categorias.codes.astype("int64"))

        dados[nome].x = _features_de_categoria(len(categorias.categories))
        dados[TABELA_RAIZ, f"tem_{nome}", nome].edge_index = torch.stack([origem, destino])
        dados[nome, f"em_{nome}", TABELA_RAIZ].edge_index = torch.stack([destino, origem])
        resumo[nome] = len(pares)

    if not dados.edge_types:
        raise ErroGNN(
            "grafo relacional sem aresta alguma. Confira se as tabelas filhas "
            "têm co_unidade e se o recorte não zerou tudo."
        )
    dados.resumo_arestas = resumo
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

    Args:
        tarefa: tabela de rótulos.
        indice: mapeamento de entidade e item para posição de tensor.
        conjunto: `"treino"`, `"validacao"` ou `"teste"`.

    Returns:
        Tupla `(u, k, y, df)`: índices de unidade, índices de item, rótulos e o
        DataFrame filtrado, todos na mesma ordem. Como o minilote de treino é
        sorteado por posição sobre estes tensores, a ordem da tabela de tarefa
        precisa ser canônica — ver D-43.
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


def _pontuar_em_blocos(
    modelo: ModeloAquisicao,
    z: torch.Tensor,
    u: torch.Tensor,
    k: torch.Tensor,
    dispositivo: str,
    bloco: int = 1_000_000,
) -> np.ndarray:
    """
    Pontua pares em blocos, devolvendo `float32`.

    O conjunto de teste do estado tem 11,7 milhões de pares. Passar tudo de uma
    vez pelo MLP do decoder materializaria uma matriz de entrada de vários
    gigabytes; em blocos, o pico é o de um bloco. `float32` em vez de `float64`
    corta o resultado pela metade sem perda relevante para ranquear.

    Args:
        modelo: modelo treinado; só o decoder é usado aqui.
        z: embedding de todos os nós, já calculado uma vez.
        u: índice de unidade de cada par.
        k: índice de item de cada par.
        dispositivo: `"cuda"` ou `"cpu"`.
        bloco: pares por bloco.

    Returns:
        Vetor `float32` de logitos, na ordem de `u`.
    """
    saidas = []
    for inicio in range(0, len(u), bloco):
        fim = inicio + bloco
        logito = modelo.decoder(
            z[u[inicio:fim].to(dispositivo)], k[inicio:fim].to(dispositivo)
        )
        saidas.append(torch.sigmoid(logito).cpu().numpy().astype(np.float32))
    return np.concatenate(saidas) if saidas else np.empty(0, dtype=np.float32)


def _codificar_grafo(modelo: ModeloAquisicao, dados, tabela_raiz: str) -> torch.Tensor:
    """
    Roda o encoder e devolve o embedding dos estabelecimentos.

    Args:
        modelo: modelo com o encoder a executar.
        dados: `HeteroData` na trilha 2, `Data` na trilha 3.
        tabela_raiz: tipo de nó a extrair do resultado heterogêneo.

    Returns:
        Embedding por estabelecimento. Absorve a diferença entre as duas trilhas,
        que é o que permite o resto do laço de treino ser um só.
    """
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
    lote_treino: int = 500_000,
    amostra_validacao: int = 2_000_000,
    semente: int = SEMENTE,
) -> tuple[ModeloAquisicao, dict]:
    """
    Treina o modelo de aquisição, selecionando época pela **validação**.

    A parada antecipada olha o AP de validação, nunca o de teste. Esse é o ponto
    que o código anterior errava: `test()` avaliava sobre `train_mask`, então não
    havia separação alguma entre ajustar e medir.

    ### Por que há minilote e subamostra aqui

    No recorte estadual o treino tem 4,2 milhões de pares e a validação 21
    milhões. Pontuar tudo a cada época é inviável em tempo e memória: só a
    entrada do MLP do decoder para 4,2 milhões de pares passa de um gigabyte.

    - `lote_treino` sorteia um minilote de pares por época. O encoder roda uma
      vez sobre o grafo inteiro — que é pequeno — e só o decoder trabalha em
      lote. Ao longo das épocas o modelo vê o conjunto todo.
    - `amostra_validacao` usa um subconjunto **fixo** da validação como sinal de
      parada antecipada. Fixo importa: se a amostra mudasse a cada época, a
      comparação entre épocas mediria ruído de amostragem além de desempenho.

    Nada disso toca o **teste**, que é sempre pontuado por completo em
    `prever_aquisicao`. Subamostrar a avaliação final tornaria a prevalência
    artificial e o AP incomparável (D-23).

    Args:
        tarefa: tabela de rótulos, já particionada.
        particao: partição temporal, usada para localizar os conjuntos.
        dados: `HeteroData` do grafo relacional, ou `Data` do geográfico.
        indice: mapeamento de `co_unidade` e item para posição, na ordem em que o
            grafo tem os nós. Ordem errada carrega sem erro e pontua lixo (D-35).
        dim_saida: dimensão do embedding produzido pelo encoder.
        epocas: teto de épocas; a parada antecipada normalmente corta antes.
        lr: taxa de aprendizado do Adam.
        paciencia: épocas sem melhora de AP de validação antes de parar.
        dispositivo: `"cuda"` ou `"cpu"`. `None` escolhe CUDA se houver.
        verboso: imprime perda e AP de validação a cada 20 épocas.
        lote_treino: pares sorteados por época para o passo de gradiente.
        amostra_validacao: teto de pares da validação usados como sinal de parada.
        semente: semente do sorteio de minilote e da amostra de validação.
            Variá-la entre execuções é a única forma de medir a banda de ruído —
            duas execuções idênticas já divergiram 15% em AP de baseline.

    Returns:
        Par `(modelo, historico)`. O modelo carrega os pesos da melhor época de
        validação, não os da última. `historico` traz `melhor_epoca`,
        `melhor_ap_validacao`, `epocas_rodadas`, `dispositivo` e a curva por época.
    """
    torch.manual_seed(semente)
    dispositivo = dispositivo or ("cuda" if torch.cuda.is_available() else "cpu")

    from src.ml.graph import TABELA_RAIZ
    from src.ml.metrics import average_precision

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

    u_tr, k_tr, y_tr, _ = _tensores_da_tarefa(tarefa, indice, "treino")
    u_va, k_va, y_va, _ = _tensores_da_tarefa(tarefa, indice, "validacao")

    # Amostra de validação fixa, sorteada uma vez. Ver a docstring.
    gerador = torch.Generator().manual_seed(semente)
    if len(y_va) > amostra_validacao:
        escolha = torch.randperm(len(y_va), generator=gerador)[:amostra_validacao]
        u_va, k_va, y_va = u_va[escolha], k_va[escolha], y_va[escolha]
    y_va_np = y_va.numpy()

    otimizador = torch.optim.Adam(modelo.parameters(), lr=lr)

    # Positivos são raros; sem reponderação a perda é minimizada prevendo sempre
    # zero, que é exatamente a baseline de persistência.
    positivos = float(y_tr.sum())
    peso = torch.tensor(
        (len(y_tr) - positivos) / max(positivos, 1.0), device=dispositivo
    )

    historico: list[dict] = []
    melhor_ap, melhor_epoca, melhores_pesos, sem_melhora = -1.0, -1, None, 0
    n_lote = min(lote_treino, len(y_tr))

    for epoca in range(epocas):
        modelo.train()
        otimizador.zero_grad()
        z = _codificar_grafo(modelo, dados, TABELA_RAIZ)

        lote = torch.randint(0, len(y_tr), (n_lote,), generator=gerador)
        logito = modelo.decoder(
            z[u_tr[lote].to(dispositivo)], k_tr[lote].to(dispositivo)
        )
        perda = F.binary_cross_entropy_with_logits(
            logito, y_tr[lote].to(dispositivo), pos_weight=peso
        )
        perda.backward()
        otimizador.step()

        modelo.eval()
        with torch.no_grad():
            z = _codificar_grafo(modelo, dados, TABELA_RAIZ)
            escore = _pontuar_em_blocos(modelo, z, u_va, k_va, dispositivo)
            ap = average_precision(y_va_np, escore)

        historico.append(
            {"epoca": epoca, "perda": float(perda.detach()), "ap_validacao": ap}
        )
        if verboso and epoca % 20 == 0:
            print(
                f"época {epoca:4d}  perda {float(perda.detach()):.4f}  "
                f"AP validação {ap:.4f}"
            )

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
    `src.ml.metrics.tabela_de_resultados` — a regra de reporte de D-11 vira o
    caminho de menor esforço em vez de disciplina manual.

    Args:
        modelo: modelo treinado, com os pesos da melhor época de validação.
        tarefa: tabela de rótulos.
        dados: grafo, o mesmo usado no treino.
        indice: índice do **modelo**, não do experimento. A trilha 3 alcança só
            os posicionáveis e portanto tem outra ordem de `unidades`.
        conjunto: conjunto a pontuar. Pontuado por completo, nunca amostrado.
        nome: rótulo que aparece na tabela de resultados.
        dispositivo: `"cuda"` ou `"cpu"`. `None` usa o do modelo.

    Returns:
        `Previsao` com rótulos, escores e entidades alinhados, mais metadados com
        o número de pares avaliados e descartados. Descartados são pares cuja
        entidade não é nó do grafo.
    """
    from src.ml.graph import TABELA_RAIZ

    dispositivo = dispositivo or next(modelo.parameters()).device.type
    dados = dados.to(dispositivo)
    u, k, y, df = _tensores_da_tarefa(tarefa, indice, conjunto)

    modelo.eval()
    with torch.no_grad():
        z = _codificar_grafo(modelo, dados, TABELA_RAIZ)
        escore = _pontuar_em_blocos(modelo, z, u, k, dispositivo)

    entidades = df[tarefa.col_entidade]
    if isinstance(entidades.dtype, pd.CategoricalDtype):
        codigos = entidades.cat.codes.to_numpy()
        rotulos = np.asarray(entidades.cat.categories)
    else:
        codigos, rotulos = pd.factorize(entidades, sort=False)
        rotulos = np.asarray(rotulos)

    return Previsao(
        modelo=nome,
        conjunto=conjunto,
        escore=escore,
        y=y.numpy(),
        entidades=codigos,
        rotulos_entidade=rotulos,
        metadados={
            "n_nos": int(dados[TABELA_RAIZ].num_nodes)
            if isinstance(dados, HeteroData)
            else int(dados.num_nodes),
            "pares_avaliados": int(len(df)),
            "pares_descartados": int(len(tarefa.por_conjunto(conjunto)) - len(df)),
        },
    )
