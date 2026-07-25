"""
Tarefas de predição: aquisição de equipamento (primária) e quantidade (secundária).

Arquitetura, e por que ela é assim: a tabela de rótulos é produzida aqui em
pandas, a partir da camada primária, e as **três trilhas consomem a mesma
tabela**. O RelBench é usado para o grafo (`src/graph.py`), não para a tarefa.

O motivo é que a tarefa primária é predição de aresta num grafo bipartido
estabelecimento × tipo de equipamento, e não uma `EntityTask` — que é o que o
RelBench modela bem. Forçá-la na API de task do framework exigiria contorções
que tornariam difícil garantir que a baseline tabular e a GNN vissem exatamente
os mesmos exemplos. E ver os mesmos exemplos é a condição para a comparação
entre trilhas significar algo (D-11).

Ver docs/02-metodologia.md, seção 2.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd

from src.changes import Transicao
from src.graph import COL_ENTIDADE, COL_MUNICIPIO, MUNICIPIO_SAO_PAULO, data_do_periodo
from src.paths import PRIMARY_FOLDER
from src.splits import ParticaoTemporal

TABELA_EQUIPAMENTO = "rlEstabEquipamento"
TABELA_LEITO = "rlEstabComplementar"
TABELA_RAIZ = "tbEstabelecimento"

COL_EQUIPAMENTO = "co_equipamento"
COL_QUANTIDADE = "qt_existente"
COL_ROTULO = "rotulo"
COL_CONJUNTO = "conjunto"


class ErroTarefa(RuntimeError):
    """Tabela de tarefa impossível de montar."""


@dataclass
class TabelaTarefa:
    """
    Rótulos prontos para modelagem, com a proveniência anexada.

    `df` está em formato longo: uma linha por (entidade, item, transição), com
    `rotulo` e `conjunto`. `conjunto` vem de `src/splits.py` e nunca é
    recalculado a jusante — é o que garante que as trilhas comparem o mesmo.
    """

    df: pd.DataFrame
    nome: str
    tipo: str
    col_entidade: str
    col_item: str | None
    col_rotulo: str

    def __post_init__(self) -> None:
        faltando = [
            c
            for c in (self.col_entidade, self.col_rotulo, COL_CONJUNTO, "timestamp")
            if c not in self.df.columns
        ]
        if faltando:
            raise ErroTarefa(f"tarefa {self.nome!r} sem as colunas {faltando}")

    @property
    def prevalencia(self) -> float:
        """Fração de positivos. Base de comparação obrigatória num problema desbalanceado."""
        return float(self.df[self.col_rotulo].mean())

    def por_conjunto(self, conjunto: str) -> pd.DataFrame:
        return self.df[self.df[COL_CONJUNTO] == conjunto]

    def resumo(self) -> pd.DataFrame:
        agrupado = self.df.groupby([COL_CONJUNTO, "periodo_destino"], as_index=False).agg(
            exemplos=(self.col_rotulo, "size"),
            positivos=(self.col_rotulo, "sum"),
        )
        agrupado["prevalencia"] = agrupado["positivos"] / agrupado["exemplos"]
        return agrupado


def _parquet(periodo: str, tabela: str, pasta: Path) -> Path:
    caminho = pasta / periodo / f"{tabela}.parquet"
    if not caminho.exists():
        raise ErroTarefa(
            f"{caminho} não existe. Rode o ETL para a competência {periodo}."
        )
    return caminho


def _universo_de_itens(
    con: duckdb.DuckDBPyConnection,
    periodos: list[str],
    tabela: str,
    col_item: str,
    pasta: Path,
) -> list[str]:
    """
    Todos os valores do item observados na série, que formam o espaço candidato.

    Precisa ser o universo da série inteira, e não o do snapshot corrente: um
    equipamento que só aparece em 2025 ainda assim era um candidato possível em
    2018, e omiti-lo tiraria do conjunto de teste justamente as aquisições mais
    informativas.
    """
    caminhos = [str(_parquet(p, tabela, pasta)) for p in periodos]
    lista = ", ".join(f"'{c}'" for c in caminhos)
    return [
        r[0]
        for r in con.execute(
            f'SELECT DISTINCT "{col_item}" FROM read_parquet([{lista}]) '
            f'WHERE "{col_item}" IS NOT NULL ORDER BY 1'
        ).fetchall()
    ]


def tarefa_aquisicao(
    particao: ParticaoTemporal,
    tabela: str = TABELA_EQUIPAMENTO,
    col_item: str = COL_EQUIPAMENTO,
    municipio_id: str | None = MUNICIPIO_SAO_PAULO,
    pasta: Path = PRIMARY_FOLDER,
) -> TabelaTarefa:
    """
    Monta a tarefa primária: o estabelecimento passa a ter o item em t+1?

    Para cada transição, o espaço de exemplos é o produto dos estabelecimentos
    **ativos em t** pelo universo de itens, menos os pares que **já existiam em
    t**. Rótulo 1 se o par existe em t+1.

    Nenhuma amostragem de negativos é feita. Amostrar enviesaria a prevalência, e
    a métrica principal (average precision) é sensível a ela — um AP calculado
    sobre negativos subamostrados não é comparável ao de outra trilha que
    amostrou diferente. O espaço completo para São Paulo é da ordem de milhões de
    pares, o que é tratável.

    Só pares ausentes em t entram: perguntar se um estabelecimento que já tem
    tomógrafo vai "adquirir" tomógrafo não é a pergunta, e incluir esses pares
    como positivos triviais infla qualquer métrica.
    """
    transicoes = [
        (nome, t) for nome, grupo in particao.conjuntos.items() for t in grupo
    ]
    periodos = sorted({p for _, t in transicoes for p in (t.origem, t.destino)})

    fatias: list[pd.DataFrame] = []
    with duckdb.connect() as con:
        itens = _universo_de_itens(con, periodos, tabela, col_item, pasta)
        if not itens:
            raise ErroTarefa(f"nenhum valor de {col_item!r} em {tabela}")
        con.execute(
            "CREATE TEMP TABLE universo_itens AS "
            f"SELECT UNNEST(?::VARCHAR[]) AS \"{col_item}\"",
            [itens],
        )

        for nome, transicao in transicoes:
            fatia = _aquisicao_de_transicao(
                con, transicao, tabela, col_item, municipio_id, pasta
            )
            fatia[COL_CONJUNTO] = nome
            fatias.append(fatia)

    df = pd.concat(fatias, ignore_index=True)
    return TabelaTarefa(
        df=df,
        nome=f"aquisicao:{tabela}.{col_item}",
        tipo="classificacao_binaria",
        col_entidade=COL_ENTIDADE,
        col_item=col_item,
        col_rotulo=COL_ROTULO,
    )


def _aquisicao_de_transicao(
    con: duckdb.DuckDBPyConnection,
    transicao: Transicao,
    tabela: str,
    col_item: str,
    municipio_id: str | None,
    pasta: Path,
) -> pd.DataFrame:
    raiz = _parquet(transicao.origem, TABELA_RAIZ, pasta)
    fato_origem = _parquet(transicao.origem, tabela, pasta)
    fato_destino = _parquet(transicao.destino, tabela, pasta)

    filtro_municipio = (
        f"WHERE \"{COL_MUNICIPIO}\" = '{municipio_id}'" if municipio_id else ""
    )

    query = f"""
        WITH ativos AS (
            SELECT DISTINCT "{COL_ENTIDADE}"
            FROM read_parquet('{raiz}')
            {filtro_municipio}
        ),
        tinha AS (
            SELECT DISTINCT "{COL_ENTIDADE}", "{col_item}"
            FROM read_parquet('{fato_origem}')
        ),
        passou_a_ter AS (
            SELECT DISTINCT "{COL_ENTIDADE}", "{col_item}"
            FROM read_parquet('{fato_destino}')
        ),
        candidatos AS (
            SELECT a."{COL_ENTIDADE}", u."{col_item}"
            FROM ativos a CROSS JOIN universo_itens u
            EXCEPT
            SELECT "{COL_ENTIDADE}", "{col_item}" FROM tinha
        )
        SELECT c."{COL_ENTIDADE}",
               c."{col_item}",
               CASE WHEN p."{COL_ENTIDADE}" IS NULL THEN 0 ELSE 1 END AS {COL_ROTULO}
        FROM candidatos c
        LEFT JOIN passou_a_ter p
               ON c."{COL_ENTIDADE}" = p."{COL_ENTIDADE}"
              AND c."{col_item}" = p."{col_item}"
    """
    df = con.execute(query).df()
    if df.empty:
        raise ErroTarefa(
            f"transição {transicao} não gerou candidato algum. Confira o "
            f"filtro de município ({municipio_id!r}) e o ETL das competências."
        )
    df["periodo_origem"] = transicao.origem
    df["periodo_destino"] = transicao.destino
    df["timestamp"] = data_do_periodo(transicao.destino)
    return df


def tarefa_quantidade(
    particao: ParticaoTemporal,
    tabela: str = TABELA_EQUIPAMENTO,
    col_item: str = COL_EQUIPAMENTO,
    col_quantidade: str = COL_QUANTIDADE,
    municipio_id: str | None = MUNICIPIO_SAO_PAULO,
    pasta: Path = PRIMARY_FOLDER,
) -> TabelaTarefa:
    """
    Monta a tarefa secundária: quanto o par (estabelecimento, item) terá em t+1.

    Ao contrário da aquisição, aqui os exemplos são os pares que **existem em t**,
    e o alvo é a quantidade em t+1 — zero quando o par desapareceu. Serve para
    verificar se o ganho estrutural observado na tarefa primária sobrevive a uma
    formulação de regressão, e para comparabilidade com a literatura, que trata
    capacidade assistencial como regressão.
    """
    fatias: list[pd.DataFrame] = []
    with duckdb.connect() as con:
        for nome, grupo in particao.conjuntos.items():
            for transicao in grupo:
                raiz = _parquet(transicao.origem, TABELA_RAIZ, pasta)
                origem = _parquet(transicao.origem, tabela, pasta)
                destino = _parquet(transicao.destino, tabela, pasta)
                filtro = (
                    f"WHERE \"{COL_MUNICIPIO}\" = '{municipio_id}'"
                    if municipio_id
                    else ""
                )
                query = f"""
                    WITH ativos AS (
                        SELECT DISTINCT "{COL_ENTIDADE}"
                        FROM read_parquet('{raiz}') {filtro}
                    ),
                    agora AS (
                        SELECT "{COL_ENTIDADE}", "{col_item}",
                               SUM("{col_quantidade}") AS quantidade_origem
                        FROM read_parquet('{origem}')
                        GROUP BY 1, 2
                    ),
                    depois AS (
                        SELECT "{COL_ENTIDADE}", "{col_item}",
                               SUM("{col_quantidade}") AS quantidade_destino
                        FROM read_parquet('{destino}')
                        GROUP BY 1, 2
                    )
                    SELECT a."{COL_ENTIDADE}", a."{col_item}",
                           a.quantidade_origem,
                           COALESCE(d.quantidade_destino, 0) AS {COL_ROTULO}
                    FROM agora a
                    JOIN ativos v ON a."{COL_ENTIDADE}" = v."{COL_ENTIDADE}"
                    LEFT JOIN depois d
                           ON a."{COL_ENTIDADE}" = d."{COL_ENTIDADE}"
                          AND a."{col_item}" = d."{col_item}"
                """
                fatia = con.execute(query).df()
                fatia["periodo_origem"] = transicao.origem
                fatia["periodo_destino"] = transicao.destino
                fatia["timestamp"] = data_do_periodo(transicao.destino)
                fatia[COL_CONJUNTO] = nome
                fatias.append(fatia)

    df = pd.concat(fatias, ignore_index=True)
    return TabelaTarefa(
        df=df,
        nome=f"quantidade:{tabela}.{col_quantidade}",
        tipo="regressao",
        col_entidade=COL_ENTIDADE,
        col_item=col_item,
        col_rotulo=COL_ROTULO,
    )
