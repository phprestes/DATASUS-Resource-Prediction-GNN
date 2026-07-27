"""
Tarefas de predição: aquisição de equipamento (primária) e quantidade (secundária).

Arquitetura, e por que ela é assim: a tabela de rótulos é produzida aqui em
pandas, a partir da camada primária, e as **três trilhas consomem a mesma
tabela**. O RelBench é usado para o grafo (`src/ml/graph.py`), não para a tarefa.

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
import pyarrow as pa

from src.etl.changes import Transicao
from src.ml.graph import (
    COL_ENTIDADE,
    RECORTE_PADRAO,
    data_do_periodo,
    filtro_recorte_sql,
)
from src.config.paths import PRIMARY_FOLDER
from src.ml.splits import ParticaoTemporal

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
    `rotulo` e `conjunto`. `conjunto` vem de `src/ml/splits.py` e nunca é
    recalculado a jusante — é o que garante que as trilhas comparem o mesmo.
    """

    df: pd.DataFrame
    nome: str
    tipo: str
    col_entidade: str
    col_item: str | None
    col_rotulo: str

    def __post_init__(self) -> None:
        """
        Recusa uma tarefa sem as colunas que todas as trilhas assumem existir.

        Raises:
            ErroTarefa: falta `col_entidade`, `col_rotulo`, a coluna de conjunto
                ou `periodo_destino`.
        """
        faltando = [
            c
            for c in (self.col_entidade, self.col_rotulo, COL_CONJUNTO, "periodo_destino")
            if c not in self.df.columns
        ]
        if faltando:
            raise ErroTarefa(f"tarefa {self.nome!r} sem as colunas {faltando}")

    @property
    def timestamp(self) -> pd.Series:
        """
        Instante de cada exemplo, derivado sob demanda.

        Não é coluna materializada de propósito: `datetime64[ns]` custa 8 bytes
        por linha, e com dezenas de milhões de linhas isso são centenas de
        megabytes para armazenar o que `periodo_destino` já determina.

        Returns:
            Série `datetime64[ns]` com a data do snapshot de destino de cada
            exemplo, na ordem das linhas.
        """
        return self.df["periodo_destino"].astype(str).map(data_do_periodo)

    def memoria_gb(self) -> float:
        """
        Tamanho da tabela em memória, contando o conteúdo das colunas de objeto.

        Returns:
            Gigabytes ocupados. Serve para checar o efeito da compactação de
            D-23, que cortou a tabela do estado de 3,22 GB para 0,32 GB.
        """
        return float(self.df.memory_usage(deep=True).sum()) / 1024**3

    def codigos(self, coluna: str) -> "np.ndarray":
        """
        Códigos inteiros de uma coluna categórica, sem materializar strings.

        É o acesso que o código a jusante deve usar para agrupar, indexar ou
        codificar. Chamar `.astype(str)` numa coluna com dezenas de milhões de
        linhas reconstrói o dicionário inteiro em objetos Python e foi o que
        estourou a memória antes.

        Args:
            coluna: nome da coluna, categórica ou não.

        Returns:
            Vetor de códigos inteiros. Coluna não categórica é convertida na
            hora, o que não preserva o mapeamento entre chamadas.
        """
        serie = self.df[coluna]
        if isinstance(serie.dtype, pd.CategoricalDtype):
            return serie.cat.codes.to_numpy()
        return pd.Categorical(serie).codes

    @property
    def prevalencia(self) -> float:
        """
        Fração de positivos na tabela inteira.

        Base de comparação obrigatória: com prevalência de 0,05%, um AP de 0,006
        é doze vezes a linha de base e ainda parece zero.

        Returns:
            Fração entre 0 e 1, sobre todos os conjuntos juntos. Para a
            prevalência de um conjunto só, use `resumo`.
        """
        return float(self.df[self.col_rotulo].mean())

    def por_conjunto(self, conjunto: str) -> pd.DataFrame:
        """
        Fatia da tabela pertencente a um conjunto.

        Args:
            conjunto: `"treino"`, `"validacao"` ou `"teste"`.

        Returns:
            Visão do DataFrame, não uma cópia. Não escreva nela.
        """
        return self.df[self.df[COL_CONJUNTO] == conjunto]

    def resumo(self) -> pd.DataFrame:
        """
        Exemplos, positivos e prevalência por conjunto e período de destino.

        Returns:
            DataFrame com uma linha por par `(conjunto, periodo_destino)`. A
            prevalência por linha revela o efeito da subamostragem: no treino ela
            fica em 0,5% por causa dos negativos 200:1, e em validação e teste
            fica no valor real, perto de 0,05%.
        """
        agrupado = self.df.groupby([COL_CONJUNTO, "periodo_destino"], as_index=False).agg(
            exemplos=(self.col_rotulo, "size"),
            positivos=(self.col_rotulo, "sum"),
        )
        agrupado["prevalencia"] = agrupado["positivos"] / agrupado["exemplos"]
        return agrupado


def _parquet(periodo: str, tabela: str, pasta: Path) -> Path:
    """
    Caminho de um Parquet da camada primária, checando que existe.

    Args:
        periodo: competência `YYYYMM`.
        tabela: nome da tabela na grafia do CSV.
        pasta: raiz da camada primária.

    Returns:
        Caminho do arquivo.

    Raises:
        ErroTarefa: o arquivo não existe, o que significa ETL faltando para
            aquela competência.
    """
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

    Args:
        con: conexão DuckDB já configurada, com o teto de memória posto.
        periodos: competências a varrer, tipicamente a série inteira.
        tabela: tabela de fato de onde sai o item.
        col_item: coluna do item, por exemplo `co_equipamento`.
        pasta: raiz da camada primária.

    Returns:
        Valores distintos e não nulos, em ordem crescente. A ordem é fixada pelo
        `ORDER BY` da consulta e vira a ordem do índice do decoder, então mudá-la
        invalida pesos já treinados.
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


def _universo_de_entidades(
    con: duckdb.DuckDBPyConnection,
    periodos: list[str],
    recorte: str | None,
    pasta: Path,
) -> list[str]:
    """
    Todos os `co_unidade` do recorte, em qualquer snapshot da janela.

    Serve de índice categórico compartilhado entre as fatias. Precisa ser a
    união da série, e não do snapshot corrente: um estabelecimento que só
    aparece em 2023 tem de ter código no índice para que a fatia de 2023 possa
    usá-lo sem criar categorias próprias.

    Args:
        con: conexão DuckDB já configurada.
        periodos: competências a varrer.
        recorte: prefixo de código IBGE; `None` é o país inteiro.
        pasta: raiz da camada primária.

    Returns:
        `co_unidade` distintos do recorte, em ordem crescente. A leitura usa
        `union_by_name=true` porque três das 44 tabelas têm colunas que
        aparecem e desaparecem ao longo da série (D-20).
    """
    caminhos = [str(_parquet(p, TABELA_RAIZ, pasta)) for p in periodos]
    lista = ", ".join(f"'{c}'" for c in caminhos)
    return [
        r[0]
        for r in con.execute(
            f'SELECT DISTINCT "{COL_ENTIDADE}" '
            f"FROM read_parquet([{lista}], union_by_name=true) "
            f"WHERE {filtro_recorte_sql(recorte)} ORDER BY 1"
        ).fetchall()
    ]


def tarefa_aquisicao(
    particao: ParticaoTemporal,
    tabela: str = TABELA_EQUIPAMENTO,
    col_item: str = COL_EQUIPAMENTO,
    recorte: str | None = RECORTE_PADRAO,
    pasta: Path = PRIMARY_FOLDER,
    negativos_por_positivo: int | None = 200,
    semente: int = 42,
    limite_duckdb: str = "2GB",
) -> TabelaTarefa:
    """
    Monta a tarefa primária: o estabelecimento passa a ter o item em t+1?

    Para cada transição, o espaço de exemplos é o produto dos estabelecimentos
    **ativos em t** pelo universo de itens, menos os pares que **já existiam em
    t**. Rótulo 1 se o par existe em t+1.

    Só pares ausentes em t entram: perguntar se um estabelecimento que já tem
    tomógrafo vai "adquirir" tomógrafo não é a pergunta, e incluir esses pares
    como positivos triviais infla qualquer métrica.

    ### Amostragem de negativos, e por que só no treino

    Com o recorte do estado, o espaço completo tem 73 milhões de pares para 34
    mil eventos. Treinar sobre isso é caro e desnecessário: o gradiente vindo do
    milionésimo negativo quase idêntico acrescenta pouco.

    `negativos_por_positivo` subamostra os negativos **apenas no conjunto de
    treino**. Validação e teste ficam **completos**, sempre. Essa assimetria é
    deliberada:

    - O treino só precisa de sinal suficiente para ajustar parâmetros, e a
      reponderação da perda em `src/ml/gnn.py` já corrige o desbalanceamento
      restante.
    - A avaliação precisa do espaço íntegro, senão a prevalência medida é
      artificial e o average precision deixa de significar o que diz significar.
      Subamostrar no teste inflaria toda métrica de forma invisível.

    Como todas as trilhas recebem a mesma `TabelaTarefa`, elas veem exatamente a
    mesma amostra de treino e o mesmo teste completo — a comparação continua
    pareada. Use `None` para desligar e treinar sobre o espaço inteiro.

    Args:
        particao: partição temporal. Todas as trilhas precisam receber a mesma.
        tabela: tabela de fato do alvo. `rlEstabEquipamento` rende 40.880 eventos
            no estado e é por isso que é o default (D-18).
        col_item: coluna do item dentro da tabela de fato.
        recorte: prefixo de código IBGE. `'35'` é o estado, `'355030'` a capital,
            `None` o país. O filtro é empurrado para dentro da leitura Parquet.
        pasta: raiz da camada primária. No cluster aponta para `$IC_HPC_DATA`.
        negativos_por_positivo: negativos mantidos por positivo **no treino**.
            `None` desliga a subamostragem.
        semente: semente da amostra de negativos.
        limite_duckdb: teto de memória do DuckDB. Explícito porque sem ele o
            buffer é dimensionado pela RAM total e disputa memória com o pandas
            no mesmo processo.

    Returns:
        `TabelaTarefa` com um exemplo por par candidato, colunas de entidade,
        item, rótulo, conjunto e as duas competências. Entidade e item vêm como
        `category` com índice compartilhado entre as fatias — sem isso o `concat`
        cairia para `object` e o pico de memória seria o da tabela em strings.

    Raises:
        ErroTarefa: nenhum valor de item na tabela, Parquet ausente para alguma
            competência, ou transição sem candidato algum.
    """
    import numpy as np

    transicoes = [
        (nome, t) for nome, grupo in particao.conjuntos.items() for t in grupo
    ]
    periodos = sorted({p for _, t in transicoes for p in (t.origem, t.destino)})
    rng = np.random.default_rng(semente)

    fatias: list[pd.DataFrame] = []
    with duckdb.connect() as con:
        # Teto explícito: sem ele o DuckDB dimensiona o buffer pela RAM total da
        # máquina e disputa memória com o pandas no mesmo processo. Com teto, ele
        # derrama para disco, que é lento mas termina.
        con.execute(f"SET memory_limit='{limite_duckdb}'")
        itens = _universo_de_itens(con, periodos, tabela, col_item, pasta)
        if not itens:
            raise ErroTarefa(f"nenhum valor de {col_item!r} em {tabela}")
        con.execute(
            "CREATE TEMP TABLE universo_itens AS "
            f"SELECT UNNEST(?::VARCHAR[]) AS \"{col_item}\"",
            [itens],
        )

        # Universo de entidades definido antes do laço, para que todas as fatias
        # compartilhem o mesmo índice categórico. Sem isso, cada fatia teria
        # categorias próprias, o `concat` cairia de volta para `object` e o pico
        # de memória seria o da tabela inteira em strings — que é justamente o
        # que se quer evitar.
        entidades = _universo_de_entidades(con, periodos, recorte, pasta)
        cat_entidade = pd.CategoricalDtype(entidades)
        cat_item = pd.CategoricalDtype(itens)

        for nome, transicao in transicoes:
            fatia = _aquisicao_de_transicao(
                con, transicao, tabela, col_item, recorte, pasta
            )
            # Só o treino é subamostrado. Ver a docstring acima.
            if nome == "treino" and negativos_por_positivo is not None:
                fatia = _subamostrar_negativos(fatia, negativos_por_positivo, rng)
            fatia[COL_ENTIDADE] = fatia[COL_ENTIDADE].astype(cat_entidade)
            fatia[col_item] = fatia[col_item].astype(cat_item)
            fatia[COL_CONJUNTO] = nome
            fatias.append(fatia)

    df = _compactar(pd.concat(fatias, ignore_index=True), [COL_ENTIDADE, col_item])
    return TabelaTarefa(
        df=df,
        nome=f"aquisicao:{tabela}.{col_item}",
        tipo="classificacao_binaria",
        col_entidade=COL_ENTIDADE,
        col_item=col_item,
        col_rotulo=COL_ROTULO,
    )


def _compactar(df: pd.DataFrame, categoricas: list[str]) -> pd.DataFrame:
    """
    Converte colunas de baixa cardinalidade para `category`, no lugar.

    É a diferença entre caber na memória e não caber. `co_unidade` é uma string
    de 13 caracteres: como `object`, o pandas guarda um ponteiro de 8 bytes mais
    o objeto Python de ~60 bytes por linha; como `category`, guarda um código
    int32 mais o dicionário uma única vez. Em 37 milhões de linhas isso é a
    diferença entre 3,2 GB e algo em torno de 600 MB.

    A conversão é feita coluna a coluna, com o original descartado logo em
    seguida, para que o pico de memória não seja o dobro do resultado.

    Args:
        df: tabela a compactar. Modificada no lugar.
        categoricas: colunas a converter, além de `periodo_origem`,
            `periodo_destino` e a coluna de conjunto, que sempre entram.

    Returns:
        O mesmo objeto recebido, com as colunas convertidas. Devolvido por
        conveniência de encadeamento, não por ser uma cópia.
    """
    for coluna in [*categoricas, "periodo_origem", "periodo_destino", COL_CONJUNTO]:
        if coluna in df.columns and not isinstance(
            df[coluna].dtype, pd.CategoricalDtype
        ):
            df[coluna] = df[coluna].astype("category")
    return df


def _subamostrar_negativos(
    fatia: pd.DataFrame, por_positivo: int, rng
) -> pd.DataFrame:
    """
    Mantém todos os positivos e uma amostra aleatória dos negativos.

    Amostra uniformemente sobre os negativos da transição, sem estratificar por
    estabelecimento nem por item. Estratificar pareceria mais cuidadoso, mas
    distorceria a distribuição conjunta que o modelo precisa aprender: um
    equipamento raro deve continuar raro na amostra de treino.

    Aplica-se **somente ao treino**. Validação e teste ficam completos, senão a
    prevalência medida seria artificial e o AP incomparável (D-23).

    Args:
        fatia: exemplos de uma transição, com a coluna de rótulo.
        por_positivo: quantos negativos manter por positivo.
        rng: gerador do numpy, de semente fixa, para a amostra ser reprodutível.

    Returns:
        Nova tabela com todos os positivos e a amostra de negativos. Se já houver
        negativos suficientes ou nenhum positivo, devolve a fatia intacta.
    """
    positivos = fatia[fatia[COL_ROTULO] == 1]
    negativos = fatia[fatia[COL_ROTULO] == 0]
    alvo = len(positivos) * por_positivo

    if len(negativos) <= alvo or positivos.empty:
        return fatia

    escolhidos = rng.choice(len(negativos), size=alvo, replace=False)
    return pd.concat(
        [positivos, negativos.iloc[escolhidos]], ignore_index=True
    )


def _aquisicao_de_transicao(
    con: duckdb.DuckDBPyConnection,
    transicao: Transicao,
    tabela: str,
    col_item: str,
    recorte: str | None,
    pasta: Path,
) -> pd.DataFrame:
    """
    Rótulos de uma transição: o par ausente em `t` passa a existir em `t+1`?

    O espaço de candidatos é o produto entre os estabelecimentos ativos em `t` e
    o universo de itens da série, menos os pares que já existiam — daí o
    `CROSS JOIN` seguido de `EXCEPT`. É o passo que gera dezenas de milhões de
    linhas por transição, e é onde o recorte espacial paga.

    Args:
        con: conexão DuckDB com a tabela temporária `universo_itens` já criada.
        transicao: par de competências `t` e `t+1`.
        tabela: tabela de fato do alvo, por exemplo `rlEstabEquipamento`.
        col_item: coluna do item.
        recorte: prefixo de código IBGE; `None` é o país inteiro.
        pasta: raiz da camada primária.

    Returns:
        Tabela com entidade, item, rótulo binário e as duas competências. **Em
        ordem canônica** por entidade e item — ver a nota junto da consulta.

    Raises:
        ErroTarefa: a transição não gerou candidato algum, o que costuma ser
            recorte errado ou ETL faltando.
    """
    raiz = _parquet(transicao.origem, TABELA_RAIZ, pasta)
    fato_origem = _parquet(transicao.origem, tabela, pasta)
    fato_destino = _parquet(transicao.destino, tabela, pasta)

    filtro = filtro_recorte_sql(recorte)

    query = f"""
        WITH ativos AS (
            SELECT DISTINCT "{COL_ENTIDADE}"
            FROM read_parquet('{raiz}')
            WHERE {filtro}
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
        ORDER BY c."{COL_ENTIDADE}", c."{col_item}"
    """
    # O `ORDER BY` acima não é cosmético. Sem ele o hash join paralelo do DuckDB
    # devolve as linhas em ordem arbitrária, que muda de processo para processo.
    # O treino sorteia o minilote por índice com semente fixa, então a mesma
    # semente sobre ordens diferentes seleciona linhas diferentes e o treino
    # deixa de ser reprodutível — medido em D-42: melhor época 10 contra 99,
    # MAP@10 0,189 contra 0,300. O LightGBM das baselines sofre do mesmo.
    #
    # Arrow com dicionário em vez de `.df()` direto. `.df()` materializa cada
    # `co_unidade` como um objeto Python — na transição de teste do estado são
    # 11,7 milhões de strings, mais de um gigabyte só nisso. O dicionário
    # converte para `category` sem nunca construir esse vetor.
    tabela_arrow = con.execute(query).fetch_arrow_table()
    if tabela_arrow.num_rows == 0:
        raise ErroTarefa(
            f"transição {transicao} não gerou candidato algum. Confira o "
            f"recorte ({recorte!r}) e o ETL das competências."
        )
    tabela_arrow = tabela_arrow.cast(
        pa.schema(
            [
                pa.field(COL_ENTIDADE, pa.dictionary(pa.int32(), pa.string())),
                pa.field(col_item, pa.dictionary(pa.int32(), pa.string())),
                # Rótulo cabe em int8; o default int64 custa 8x sem motivo.
                pa.field(COL_ROTULO, pa.int8()),
            ]
        )
    )
    df = tabela_arrow.to_pandas()
    del tabela_arrow

    # `timestamp` não é materializado: é derivável de `periodo_destino`,
    # ver TabelaTarefa.timestamp.
    df["periodo_origem"] = transicao.origem
    df["periodo_destino"] = transicao.destino
    return df


def tarefa_quantidade(
    particao: ParticaoTemporal,
    tabela: str = TABELA_EQUIPAMENTO,
    col_item: str = COL_EQUIPAMENTO,
    col_quantidade: str = COL_QUANTIDADE,
    recorte: str | None = RECORTE_PADRAO,
    pasta: Path = PRIMARY_FOLDER,
) -> TabelaTarefa:
    """
    Monta a tarefa secundária: quanto o par (estabelecimento, item) terá em t+1.

    Ao contrário da aquisição, aqui os exemplos são os pares que **existem em t**,
    e o alvo é a quantidade em t+1 — zero quando o par desapareceu. Serve para
    verificar se o ganho estrutural observado na tarefa primária sobrevive a uma
    formulação de regressão, e para comparabilidade com a literatura, que trata
    capacidade assistencial como regressão.

    **Rejeitada por medição** (D-37): apenas 1,119% dos pares persistentes mudam
    de quantidade entre duas competências, e prever zero dá RMSE igual ao desvio
    padrão do alvo. Fica implementada e sem uso.

    Args:
        particao: partição temporal, a mesma da tarefa primária.
        tabela: tabela de fato do alvo.
        col_item: coluna do item.
        col_quantidade: coluna numérica a prever, por exemplo `qt_existente`.
        recorte: prefixo de código IBGE; `None` é o país inteiro.
        pasta: raiz da camada primária.

    Returns:
        `TabelaTarefa` de tipo `regressao`, com um exemplo por par existente em
        `t` e o valor observado em `t+1` como alvo.
    """
    fatias: list[pd.DataFrame] = []
    with duckdb.connect() as con:
        for nome, grupo in particao.conjuntos.items():
            for transicao in grupo:
                raiz = _parquet(transicao.origem, TABELA_RAIZ, pasta)
                origem = _parquet(transicao.origem, tabela, pasta)
                destino = _parquet(transicao.destino, tabela, pasta)
                filtro = filtro_recorte_sql(recorte)
                query = f"""
                    WITH ativos AS (
                        SELECT DISTINCT "{COL_ENTIDADE}"
                        FROM read_parquet('{raiz}') WHERE {filtro}
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
                fatia[COL_CONJUNTO] = nome
                fatias.append(fatia)

    df = _compactar(pd.concat(fatias, ignore_index=True), [COL_ENTIDADE, col_item])
    return TabelaTarefa(
        df=df,
        nome=f"quantidade:{tabela}.{col_quantidade}",
        tipo="regressao",
        col_entidade=COL_ENTIDADE,
        col_item=col_item,
        col_rotulo=COL_ROTULO,
    )
