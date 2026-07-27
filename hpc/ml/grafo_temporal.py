"""
Um grafo por transição, com atributo e peso na aresta.

Levanta duas limitações de uma vez.

**A defasagem temporal (D-25).** O pipeline do notebook usa um grafo estático
cortado antes de *todos* os rótulos — 201701 na série de dez snapshots — porque
uma estrutura única serve treino, validação e teste, e cortá-la mais tarde
inscreveria o rótulo nela. O preço é uma rede nove anos mais velha que o conjunto
de teste, e, pior, features de nó do mesmo instante: 45% dos estabelecimentos
entram com vetor vazio, porque não existiam em 2017.

Aqui cada transição `t → t+1` recebe **seu próprio grafo**, montado com dado até
`t`. A garantia de D-25 se mantém por construção — nenhuma aresta é posterior à
origem da transição que ela serve —, e a estrutura passa a ser contemporânea do
exemplo. Não é tempo contínuo: é um grafo por passo, que é a aproximação de 80/20
e está declarada como tal no artigo.

**A projeção mínima (D-23).** No notebook cada tabela filha entra com duas
colunas, e 298 das 368 colunas `util` das tabelas de fato ficam fora: a aresta não
sabe *quantos* equipamentos existem, nem se estão disponíveis ao SUS. Aqui:

- cada coluna `category` da tabela vira **um vocabulário próprio**, em vez de só a
  primeira — `rlEstabServClass` passa a contribuir serviço *e* classificação;
- as colunas `Int64` viram **peso de aresta**, agregadas por par com soma;
- `min_arestas` cai para zero, então relação rara deixa de ser descartada.

O peso é escalar por decisão consciente: `SAGEConv` não aceita atributo de aresta,
e `GraphConv` aceita peso. Reduzir o vetor de quantidades a `log1p` da soma perde
a distinção entre existente e em uso, mas mantém a intensidade — que é o que a
projeção mínima descartava por completo. O resto do conteúdo entra como
vocabulário adicional, não como atributo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.compute as pc
import torch
from relbench.base import Database
from torch_geometric.data import HeteroData

from hpc.config.ambiente import exigir_memoria
from src.config.schema import CNES_DTYPES, CNES_FKEY, CNES_USEFUL_COLUMNS
from src.etl.changes import Transicao
from src.ml.gnn import SEMENTE, ErroGNN, _features_de_categoria, features_de_estabelecimento
from src.ml.graph import COL_ENTIDADE, COL_TEMPO, TABELA_RAIZ, data_do_periodo

# Colunas que nunca entram: são auditoria, não conteúdo.
PREFIXO_MUNICIPIO = "co_municipio"


@dataclass
class GrafoPorTransicao:
    """
    Os grafos de uma execução, um por transição, mais o índice de nós.

    `por_origem` é indexado pela **origem** da transição, que é o instante de
    corte: o grafo de `201701 -> 201801` é o estado do cadastro em 201701.
    """

    unidades: list[str]
    por_origem: dict[str, HeteroData] = field(default_factory=dict)
    resumo: dict[str, dict] = field(default_factory=dict)

    def para(self, transicao: Transicao) -> HeteroData:
        """
        Grafo que serve uma transição, indexado pela origem dela.

        Args:
            transicao: transição a atender.

        Returns:
            O `HeteroData` cortado em `transicao.origem`.

        Raises:
            ErroGNN: nenhum grafo montado para aquela origem.
        """
        if transicao.origem not in self.por_origem:
            raise ErroGNN(
                f"nenhum grafo montado para a origem {transicao.origem}. "
                f"Disponíveis: {sorted(self.por_origem)}"
            )
        return self.por_origem[transicao.origem]

    @property
    def n_grafos(self) -> int:
        """
        Returns:
            Quantos grafos distintos existem. No modo completo é um por origem de
            transição; no compatível é um só, replicado.
        """
        return len(self.por_origem)


def colunas_para_grafo_completo() -> dict[str, list[str]]:
    """
    Projeção **completa** das tabelas que entram no grafo.

    O oposto de `src.ml.graph.colunas_minimas_para_grafo`, que entrega duas
    colunas por tabela filha para caber em 9 GB. Aqui entram todas as colunas
    `util` de toda tabela filha com chave estrangeira para o estabelecimento, e a
    raiz inteira.
    """
    colunas = {TABELA_RAIZ: list(CNES_USEFUL_COLUMNS[TABELA_RAIZ])}
    for tabela, fkeys in CNES_FKEY.items():
        if tabela == TABELA_RAIZ or COL_ENTIDADE not in fkeys:
            continue
        colunas[tabela] = list(CNES_USEFUL_COLUMNS[tabela])
    return colunas


def _vocabularios(tabela: str) -> list[str]:
    """
    Toda coluna `category` da tabela, e não apenas a primeira.

    Exclui a chave do estabelecimento e as colunas de município: um nó por
    município ligaria todos os estabelecimentos da cidade entre si, que é a
    degeneração que `escolher_categoria` evita no pipeline do notebook (D-27).

    Args:
        tabela: nome da tabela de fato.

    Returns:
        Colunas que viram vocabulário. Mais de uma por tabela é a diferença
        central do modo completo: `rlEstabServClass` passa a contribuir serviço
        **e** classificação.
    """
    dtypes = CNES_DTYPES.get(tabela, {})
    return [
        coluna
        for coluna in CNES_USEFUL_COLUMNS.get(tabela, [])
        if dtypes.get(coluna) == "category"
        and coluna != COL_ENTIDADE
        and not coluna.startswith(PREFIXO_MUNICIPIO)
    ]


def _colunas_de_peso(tabela: str) -> list[str]:
    """
    Colunas inteiras da tabela, que viram peso de aresta.

    Args:
        tabela: nome da tabela de fato.

    Returns:
        Colunas `Int64`. Agregadas por par com soma e `log1p`, viram o
        `edge_weight` que `GraphConv` aceita — a projeção mínima descartava essa
        intensidade por completo.
    """
    dtypes = CNES_DTYPES.get(tabela, {})
    return [
        coluna
        for coluna in CNES_USEFUL_COLUMNS.get(tabela, [])
        if dtypes.get(coluna) == "Int64"
    ]


def montar_um_grafo(
    db: Database,
    unidades: list[str],
    ate_periodo: str,
    com_atributos: bool = True,
    min_arestas: int = 0,
) -> HeteroData:
    """
    Grafo heterogêneo com o estado do cadastro **até** `ate_periodo`.

    `com_atributos=False` reproduz a montagem do notebook: um vocabulário por
    tabela e aresta sem peso. É o que o modo compatível usa, e existe para que a
    diferença entre as metades da matriz seja atribuível (D-34).

    Args:
        db: `Database` de onde saem raiz e tabelas de fato.
        unidades: `co_unidade` na ordem dos índices de nó.
        ate_periodo: corte. Toda linha posterior é ignorada.
        com_atributos: projeção completa com peso de aresta e vários vocabulários
            por tabela. `False` replica a montagem do notebook.
        min_arestas: descarta relações com menos arestas que isso. Zero no modo
            completo, 100 no compatível.

    Returns:
        `HeteroData` com o atributo `ate_periodo` registrado, que
        `verificar_sem_vazamento` depois confere.
    """
    from src.ml.gnn import escolher_categoria

    limite = data_do_periodo(ate_periodo)
    idx_unidade = {u: i for i, u in enumerate(unidades)}

    dados = HeteroData()
    dados[TABELA_RAIZ].x = features_de_estabelecimento(
        db, unidades, ate_periodo=ate_periodo
    )
    resumo: dict[str, int] = {}

    for tabela, arrow in db.table_dict.items():
        if tabela == TABELA_RAIZ:
            continue
        fkeys = arrow.fkey_col_to_pkey_table or {}
        if COL_ENTIDADE not in fkeys:
            continue

        if com_atributos:
            vocabularios = _vocabularios(tabela)
            pesos = _colunas_de_peso(tabela)
        else:
            escolhida = escolher_categoria(tabela)
            vocabularios = [escolhida] if escolhida else []
            pesos = []

        presentes = set(arrow.df.column_names)
        vocabularios = [c for c in vocabularios if c in presentes]
        pesos = [c for c in pesos if c in presentes]
        if not vocabularios:
            continue

        # Filtra por tempo antes de sair do pyarrow: no recorte nacional a tabela
        # inteira em pandas custaria dezenas de gigabytes por competência.
        fatia = arrow.df.filter(pc.less_equal(pc.field(COL_TEMPO), limite))
        if fatia.num_rows == 0:
            continue

        for coluna in vocabularios:
            nome = f"{tabela}:{coluna}" if com_atributos else tabela
            projecao = [COL_ENTIDADE, coluna, *pesos]
            pares = fatia.select(projecao).to_pandas().dropna(subset=[COL_ENTIDADE, coluna])
            pares = pares[pares[COL_ENTIDADE].isin(idx_unidade)]
            if pares.empty:
                continue

            if pesos:
                # Um par pode aparecer em várias linhas — um estabelecimento com
                # três tomógrafos registrados separadamente. Somar é o que dá
                # sentido a "quantos", e a soma vira o peso da aresta.
                agrupado = (
                    pares.groupby([COL_ENTIDADE, coluna], observed=True)[pesos]
                    .sum()
                    .reset_index()
                )
                peso = np.log1p(
                    agrupado[pesos].sum(axis=1).to_numpy(dtype="float32")
                )
            else:
                agrupado = pares[[COL_ENTIDADE, coluna]].drop_duplicates()
                peso = np.ones(len(agrupado), dtype="float32")

            if len(agrupado) < min_arestas:
                continue

            categorias = pd.Categorical(agrupado[coluna])
            origem = torch.as_tensor(
                agrupado[COL_ENTIDADE].map(idx_unidade).to_numpy(), dtype=torch.long
            )
            destino = torch.as_tensor(categorias.codes.astype("int64"))
            w = torch.as_tensor(peso)

            dados[nome].x = _features_de_categoria(len(categorias.categories))
            ida = (TABELA_RAIZ, f"tem_{nome}", nome)
            volta = (nome, f"em_{nome}", TABELA_RAIZ)
            dados[ida].edge_index = torch.stack([origem, destino])
            dados[ida].edge_weight = w
            dados[volta].edge_index = torch.stack([destino, origem])
            dados[volta].edge_weight = w
            resumo[nome] = len(agrupado)

    if not dados.edge_types:
        raise ErroGNN(
            f"grafo de {ate_periodo} sem aresta alguma. Confira o recorte e se a "
            "camada primária do servidor tem as tabelas filhas."
        )
    dados.resumo_arestas = resumo
    dados.ate_periodo = ate_periodo
    return dados


def montar(
    db: Database,
    unidades: list[str],
    transicoes: list[Transicao],
    com_atributos: bool = True,
    min_arestas: int = 0,
    verboso: bool = True,
    permitir_maquina_pequena: bool = False,
) -> GrafoPorTransicao:
    """
    Um grafo por origem de transição, reaproveitando origens repetidas.

    Args:
        db: `Database` de onde os grafos são montados.
        unidades: `co_unidade` na ordem dos índices de nó, compartilhada por
            todos os grafos.
        transicoes: transições a atender.
        com_atributos: projeção completa com peso de aresta.
        min_arestas: mínimo de arestas por relação.
        verboso: imprime progresso por grafo.
        permitir_maquina_pequena: ignora a guarda de RAM. Só para dado sintético.

    Returns:
        `GrafoPorTransicao` com um grafo por origem distinta e o resumo de cada.

    Numa partição encadeada as origens são distintas, mas a função não assume
    isso: `202401 -> 202501` e `202401 -> 202601` compartilhariam o mesmo grafo.
    """
    exigir_memoria(
        o_que=f"montar {len(set(t.origem for t in transicoes))} grafos por transição",
        permitir_maquina_pequena=permitir_maquina_pequena,
    )
    torch.manual_seed(SEMENTE)
    grafos = GrafoPorTransicao(unidades=list(unidades))

    for origem in sorted({t.origem for t in transicoes}):
        grafo = montar_um_grafo(
            db, unidades, origem, com_atributos=com_atributos, min_arestas=min_arestas
        )
        grafos.por_origem[origem] = grafo
        grafos.resumo[origem] = {
            "tipos_no": len(grafo.node_types),
            "relacoes": len(grafo.edge_types),
            "arestas": int(sum(grafo.resumo_arestas.values())),
        }
        if verboso:
            r = grafos.resumo[origem]
            print(
                f"  grafo {origem}: {r['tipos_no']} tipos de nó, "
                f"{r['relacoes']} relações, {r['arestas']:,} arestas",
                flush=True,
            )
    return grafos


def verificar_sem_vazamento(
    grafos: GrafoPorTransicao, transicoes: list[Transicao]
) -> None:
    """
    Confere que nenhum grafo enxerga o instante em que o rótulo dele acontece.

    É a garantia de D-25 traduzida para o grafo por transição, e o teste que
    justifica trocar o corte estático: o grafo de uma transição pode ser
    contemporâneo da **origem**, nunca do destino.

    Args:
        grafos: conjunto a verificar.
        transicoes: transições que ele precisa atender.

    Raises:
        ErroGNN: grafo sem corte registrado, ou com corte que alcança o destino da
            transição que ele serve — caso em que a aresta estabelecimento-item em
            `t+1` é o próprio rótulo.
    """
    for transicao in transicoes:
        grafo = grafos.para(transicao)
        corte = getattr(grafo, "ate_periodo", None)
        if corte is None:
            raise ErroGNN(f"grafo de {transicao} sem corte registrado")
        if corte >= transicao.destino:
            raise ErroGNN(
                f"grafo da transição {transicao} cortado em {corte}, que alcança o "
                f"destino {transicao.destino}: a aresta estabelecimento-item em "
                "t+1 é o próprio rótulo (D-25)"
            )


def salvar(grafos: GrafoPorTransicao, pasta: Path) -> Path:
    """
    Materializa os grafos em disco, para não remontá-los a cada execução.

    No recorte nacional a montagem domina o tempo de preparação, e as quatro
    células da matriz reusam os mesmos grafos por escopo e modo.

    Args:
        grafos: conjunto a gravar.
        pasta: destino. Criada se não existir.

    Returns:
        Caminho do `grafos.pt` escrito.
    """
    pasta.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "unidades": grafos.unidades,
            "resumo": grafos.resumo,
            "grafos": {k: v for k, v in grafos.por_origem.items()},
        },
        pasta / "grafos.pt",
    )
    return pasta / "grafos.pt"


def carregar(caminho: Path) -> GrafoPorTransicao:
    """
    Lê os grafos materializados de volta.

    Args:
        caminho: arquivo `grafos.pt`.

    Returns:
        `GrafoPorTransicao` reconstruído. Carregado em CPU: só o grafo da
        transição em curso vai para a GPU, o que mantém o pico de VRAM no tamanho
        de um grafo em vez da soma.
    """
    pacote = torch.load(caminho, weights_only=False)
    return GrafoPorTransicao(
        unidades=pacote["unidades"],
        por_origem=pacote["grafos"],
        resumo=pacote.get("resumo", {}),
    )
