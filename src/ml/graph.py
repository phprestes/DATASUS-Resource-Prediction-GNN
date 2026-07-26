"""
Montagem dos grafos: relacional (trilha 2) e geográfico (trilha 3).

Evolui o antigo `src/dataset.py`. Três mudanças de fundo:

1. **Eixo temporal honesto.** O `time_col` é a data do snapshot, 1º de janeiro
   da competência, e não `to_chardt_atualizacaoddmmyyyy`, que é censurada à
   direita. Uma linha no snapshot de 01/2021 significa "este fato valia em
   01/2021" — a semântica que um grafo temporal precisa. Ver D-08.
2. **Schema vem do doc.** `CNES_PKEY` e `CNES_FKEY` são derivados de
   docs/01-selecao-tabelas.md, cuja validação recusa chave estrangeira
   pendurada — o bug D-14, que fazia o grafo referenciar tabela ausente.
3. **Falha em vez de sumir.** A versão anterior engolia exceção por tabela com
   `except Exception: print; continue`, então uma tabela quebrada
   desaparecia do grafo sem que ninguém notasse. Agora o padrão é levantar; o
   modo tolerante é explícito.

As tabelas são construídas com `pyarrow.Table`, não `pandas.DataFrame`. É
deliberado — o filtro por município é empurrado para dentro do scan Parquet — e
é armadilha para código consumidor que assume pandas. Ver `Tabela.df` abaixo.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.dataset as ds
from relbench.base import Database, Dataset, Table

from src.config.paths import PRIMARY_FOLDER
from src.config.schema import CNES_FKEY, CNES_PKEY, CNES_USEFUL_COLUMNS

TABELA_RAIZ = "tbEstabelecimento"
COL_ENTIDADE = "co_unidade"
COL_MUNICIPIO = "co_municipio_gestor"
COL_TEMPO = "timestamp"

# Recortes espaciais. O código do IBGE é hierárquico: os dois primeiros dígitos
# são a UF, os demais o município. Um recorte é portanto um prefixo, e o
# município é só o caso em que o prefixo tem o código inteiro.
MUNICIPIO_SAO_PAULO = "355030"
ESTADO_SAO_PAULO = "35"

# Recorte padrão do projeto. Passou de município para estado em D-21: o estado dá
# 2,9 vezes mais eventos de aquisição, 645 municípios em vez de um — o que
# habilita a população do IBGE — e cobertura de coordenada de 85,7% contra 75%.
RECORTE_PADRAO = ESTADO_SAO_PAULO

COL_LATITUDE = "nu_latitude"
COL_LONGITUDE = "nu_longitude"

RAIO_TERRA_KM = 6371.0


class ErroGrafo(RuntimeError):
    """Grafo impossível de montar a partir da camada primária."""


def filtro_recorte_sql(recorte: str | None, coluna: str = COL_MUNICIPIO) -> str:
    """
    Cláusula SQL do recorte espacial, para uso em DuckDB.

    O código de município do IBGE é hierárquico, então um prefixo é um recorte:
    `'35'` é o estado de São Paulo, `'355030'` é o município da capital, `None` é
    o país. Não há caso especial — o município é apenas o prefixo completo.

    Devolve `'1 = 1'` para recorte nulo, para que a cláusula possa ser
    interpolada sem ramificar no chamador.
    """
    if recorte is None:
        return "1 = 1"
    if not recorte.isdigit():
        raise ValueError(
            f"recorte deve ser um prefixo numérico de código IBGE; recebido {recorte!r}"
        )
    return f"\"{coluna}\" LIKE '{recorte}%'"


def filtro_recorte_arrow(recorte: str | None):
    """
    Mesma semântica de `filtro_recorte_sql`, como expressão pyarrow.

    Existe separada porque o filtro da tabela raiz é empurrado para dentro do
    scan Parquet, e ali a linguagem é a de expressões do pyarrow, não SQL.
    """
    if recorte is None:
        return None
    if not recorte.isdigit():
        raise ValueError(
            f"recorte deve ser um prefixo numérico de código IBGE; recebido {recorte!r}"
        )
    campo = pc.field(COL_MUNICIPIO)
    if len(recorte) >= 6:
        return pc.equal(campo, recorte)
    return pc.starts_with(campo, recorte)


def data_do_periodo(periodo: str) -> pd.Timestamp:
    """
    Converte a competência YYYYMM na data do snapshot.

    O ZIP de competência 202501 é o estado do banco em janeiro de 2025, então o
    instante do snapshot é 2025-01-01. Exato e uniforme para todas as linhas do
    arquivo, ao contrário da coluna de atualização.
    """
    if len(periodo) != 6 or not periodo.isdigit():
        raise ValueError(f"competência deve ser YYYYMM; recebido {periodo!r}")
    return pd.Timestamp(year=int(periodo[:4]), month=int(periodo[4:]), day=1)


def _marcos_da_particao(pasta: Path) -> tuple[pd.Timestamp, pd.Timestamp]:
    """
    Datas em que validação e teste começam, lidas da camada primária.

    O RelBench pede `val_timestamp` e `test_timestamp` como atributos do
    `Dataset`, e `src/ml/splits.py` já decide a divisão a partir das transições
    existentes. Derivar daqui é o que mantém as duas coisas coerentes quando a
    série cresce — foi o motivo de as datas deixarem de ser literais.

    Importado dentro da função porque `src.ml.splits` importa `src.etl.changes`, que
    importa este módulo indiretamente pela camada de caminhos.
    """
    from src.etl.changes import periodos_disponiveis
    from src.ml.splits import particionar

    periodos = periodos_disponiveis(pasta)
    particao = particionar(periodos)
    return (
        data_do_periodo(particao.validacao[0].destino),
        data_do_periodo(particao.teste[0].destino),
    )


def periodos_com_tabela(
    tabela: str, pasta: Path = PRIMARY_FOLDER
) -> dict[str, Path]:
    """Competências que têm Parquet desta tabela, em ordem cronológica."""
    encontrados = {
        p.parent.name: p for p in sorted(pasta.glob(f"*/{tabela}.parquet"))
    }
    return dict(sorted(encontrados.items()))


def _empilhar(
    tabela: str,
    arquivos: dict[str, Path],
    filtro_unidades: set[str] | None,
    colunas_pedidas: list[str] | None = None,
) -> pa.Table:
    """
    Lê os snapshots de uma tabela e os empilha com a coluna de tempo.

    O filtro por unidade é aplicado dentro do scan, não depois: sem isso, montar
    o subgrafo de um recorte exige carregar o país inteiro na memória para
    descartar quase tudo em seguida.

    `colunas_pedidas` restringe a projeção. Importa: `tbDadosProfissionalSus` tem
    48 milhões de linhas e `tbCargaHorariaSus` 10 milhões no estado, e carregar
    todas as suas colunas quando o grafo só usa duas foi o que levou o processo a
    5,3 GB.
    """
    fatias: list[pa.Table] = []
    colunas_declaradas = colunas_pedidas or CNES_USEFUL_COLUMNS[tabela]

    for periodo, caminho in arquivos.items():
        dataset = ds.dataset(str(caminho), format="parquet")
        disponiveis = set(dataset.schema.names)
        colunas = [c for c in colunas_declaradas if c in disponiveis]
        if not colunas:
            continue

        filtro = None
        if filtro_unidades is not None and COL_ENTIDADE in disponiveis:
            filtro = pc.field(COL_ENTIDADE).isin(filtro_unidades)

        fatia = dataset.to_table(columns=colunas, filter=filtro)
        fatia = fatia.append_column(
            COL_TEMPO,
            pa.array([data_do_periodo(periodo)] * fatia.num_rows, type=pa.timestamp("ns")),
        )
        fatias.append(fatia)

    if not fatias:
        return pa.table({})
    return pa.concat_tables(fatias, promote_options="permissive")


def colunas_minimas_para_grafo() -> dict[str, list[str]]:
    """
    Projeção mínima que a montagem do grafo precisa de cada tabela.

    A tabela raiz entra inteira, porque dela saem as features de nó e as
    coordenadas. As filhas entram com apenas duas colunas: a chave do
    estabelecimento e a coluna que define o vocabulário de categorias — que é o
    que vira aresta.

    Sem essa restrição, `montar_db` no estado carrega 76 milhões de linhas com
    todas as colunas e chega a 5,3 GB, num ambiente de 9 GB. Com ela, carrega o
    que o grafo de fato usa.
    """
    from src.ml.gnn import escolher_categoria

    colunas = {TABELA_RAIZ: list(CNES_USEFUL_COLUMNS[TABELA_RAIZ])}
    for tabela in CNES_USEFUL_COLUMNS:
        if tabela == TABELA_RAIZ:
            continue
        if COL_ENTIDADE not in CNES_FKEY.get(tabela, {}):
            continue
        categoria = escolher_categoria(tabela)
        if categoria is None:
            continue
        colunas[tabela] = [COL_ENTIDADE, categoria]
    return colunas


def montar_db(
    recorte: str | None = RECORTE_PADRAO,
    pasta: Path = PRIMARY_FOLDER,
    tolerar_falhas: bool = False,
    colunas: dict[str, list[str]] | None = None,
) -> Database:
    """
    Monta o `Database` do RelBench empilhando os snapshots da camada primária.

    `recorte` é o principal controle de custo: um prefixo de código IBGE — `'35'`
    para o estado de São Paulo, `'355030'` para a capital, `None` para o país.
    Filtra a tabela raiz e empurra o conjunto de `co_unidade` resultante como
    predicado no scan de cada tabela filha.

    `tolerar_falhas=True` registra e segue adiante quando uma tabela filha não
    pode ser lida. O default é falhar: uma tabela que desaparece em silêncio do
    grafo é pior que um erro, porque o experimento roda e o resultado engana.

    `colunas` restringe a projeção por tabela, sobrescrevendo
    `CNES_USEFUL_COLUMNS`. Use `colunas_minimas_para_grafo()` quando o destino
    for a montagem do grafo: no recorte estadual isso é a diferença entre 5,3 GB
    e caber na máquina. Tabelas ausentes do dicionário são omitidas do Database.
    """
    arquivos_raiz = periodos_com_tabela(TABELA_RAIZ, pasta)
    if not arquivos_raiz:
        raise ErroGrafo(
            f"nenhum {TABELA_RAIZ}.parquet encontrado em {pasta}. "
            "Rode o ETL antes: python -m src.etl.extract && python -m src.etl.to_sql "
            "&& python -m src.etl.to_parquet"
        )

    raiz = _empilhar(
        TABELA_RAIZ, arquivos_raiz, None, colunas.get(TABELA_RAIZ) if colunas else None
    )
    filtro = filtro_recorte_arrow(recorte)
    if filtro is not None:
        raiz = raiz.filter(filtro)
        if raiz.num_rows == 0:
            raise ErroGrafo(
                f"nenhum estabelecimento com {COL_MUNICIPIO} começando em "
                f"{recorte!r}. Confira o prefixo do código IBGE."
            )
    unidades = set(raiz.column(COL_ENTIDADE).to_pylist()) if recorte else None

    # Primeiro passo: materializa os dados de cada tabela. As chaves
    # estrangeiras só podem ser resolvidas depois que se sabe quais tabelas de
    # fato entraram — uma tabela filha vazia é omitida, e apontar para ela
    # recriaria a referência pendurada de D-14.
    dados_por_tabela: dict[str, pa.Table] = {TABELA_RAIZ: raiz}

    tabelas_alvo = sorted(colunas) if colunas else sorted(CNES_USEFUL_COLUMNS)
    for nome in tabelas_alvo:
        if nome == TABELA_RAIZ:
            continue
        arquivos = periodos_com_tabela(nome, pasta)
        if not arquivos:
            continue
        try:
            dados = _empilhar(
                nome, arquivos, unidades, colunas.get(nome) if colunas else None
            )
        except Exception as erro:
            if not tolerar_falhas:
                raise ErroGrafo(f"falha ao empilhar {nome}: {erro}") from erro
            print(f"[AVISO] {nome} ignorada: {erro}")
            continue

        if dados.num_rows:
            dados_por_tabela[nome] = dados

    # Segundo passo: monta as Table já sabendo o conjunto final de destinos.
    tabelas: dict[str, Table] = {}
    for nome, dados in dados_por_tabela.items():
        presentes = set(dados.column_names)
        fkeys = {
            coluna: destino
            for coluna, destino in CNES_FKEY.get(nome, {}).items()
            if coluna in presentes and destino in dados_por_tabela and destino != nome
        }
        pkey = CNES_PKEY.get(nome) if nome != TABELA_RAIZ else COL_ENTIDADE
        tabelas[nome] = Table(
            df=dados,
            pkey_col=pkey if pkey in presentes else None,
            fkey_col_to_pkey_table=fkeys,
            time_col=COL_TEMPO,
        )

    return Database(tabelas)


class CNESDataset(Dataset):
    """
    Dataset RelBench do CNES, ancorado num recorte territorial.

    O recorte é atributo da instância e não parâmetro de `make_db`, porque o
    RelBench chama `make_db` sem argumentos ao materializar o cache — a versão
    anterior expunha `make_db(municipio_id=...)`, que o framework nunca chamava
    com o argumento, então o grafo cacheado saía nacional.
    """

    name = "cnes-dataset"

    def __init__(
        self,
        recorte: str | None = RECORTE_PADRAO,
        val_timestamp: pd.Timestamp | None = None,
        test_timestamp: pd.Timestamp | None = None,
        pasta: Path = PRIMARY_FOLDER,
        **kwargs,
    ) -> None:
        self.recorte = recorte
        self.pasta = pasta
        # Derivados da partição de src/ml/splits.py sobre os snapshots que existem
        # na camada primária, não fixados no código: acrescentar uma competência
        # move validação e teste um ano adiante, e uma data cravada aqui deixaria
        # o RelBench avaliando num período que a partição chama de treino.
        padrao_val, padrao_teste = _marcos_da_particao(pasta)
        self.val_timestamp = val_timestamp or padrao_val
        self.test_timestamp = test_timestamp or padrao_teste
        super().__init__(**kwargs)

    def make_db(self) -> Database:
        return montar_db(self.recorte, self.pasta)


# ---------------------------------------------------------------------------
# Trilha 3: grafo geográfico
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GrafoGeografico:
    """
    Estabelecimentos como nós, proximidade física como aresta.

    `unidades` é a lista de `co_unidade` na ordem dos índices de `arestas`.
    `arestas` tem forma (2, E), no formato que o PyTorch Geometric espera.
    `distancias_km` acompanha `arestas` na mesma ordem.
    """

    unidades: list[str]
    arestas: "pa.Table"
    coordenadas: pd.DataFrame
    k: int
    raio_km: float | None

    @property
    def n_nos(self) -> int:
        return len(self.unidades)

    @property
    def n_arestas(self) -> int:
        return self.arestas.num_rows


def _descartar_fora_da_amostra(df: pd.DataFrame, desvios: float) -> pd.DataFrame:
    """
    Descarta coordenada distante do corpo da amostra.

    A caixa do Brasil não basta. Medido em São Paulo, 1,2% das coordenadas
    existentes caem fora do município, chegando a 197 km do centro numa cidade de
    cerca de 35 km de largura — passam pela caixa nacional e mesmo assim são
    lixo. Ver D-17.

    O corte é relativo à própria amostra, não a uma caixa fixa: usa a mediana
    como centro e o desvio absoluto mediano (MAD) como escala, ambos robustos aos
    outliers que se quer remover. Uma caixa fixa por município exigiria uma
    tabela de caixas e quebraria ao trocar o recorte espacial.

    O default de `desvios` foi calibrado contra o comportamento de uma caixa
    desenhada à mão em torno do município de São Paulo, que retinha 98,8% das
    coordenadas. Em 202201, sobre 15.412 pontos:

        desvios=20  retém 94,03%  raio máximo 21,3 km
        desvios=40  retém 98,68%  raio máximo 39,2 km   <- default
        desvios=80  retém 99,40%  raio máximo 76,3 km

    O MAD é pequeno porque os estabelecimentos se concentram no centro, e é por
    isso que o múltiplo precisa ser grande — 10 desvios descartaria 19% de
    pontos legítimos.
    """
    if len(df) < 10:
        return df

    centro = df[[COL_LATITUDE, COL_LONGITUDE]].median()
    desvio_absoluto = (df[[COL_LATITUDE, COL_LONGITUDE]] - centro).abs()
    mad = desvio_absoluto.median()
    # MAD zero acontece quando quase tudo está no mesmo ponto; aí não há escala
    # para comparar e o corte é abandonado em vez de descartar tudo.
    if (mad <= 0).any():
        return df

    dentro = (desvio_absoluto <= desvios * mad).all(axis=1)
    return df[dentro]


def coordenadas_por_unidade(
    db: Database,
    periodo_referencia: str | None = None,
    politica: str = "mais_antiga",
    desvios: float = 40.0,
) -> pd.DataFrame:
    """
    Extrai uma coordenada por estabelecimento, tratada como invariante no tempo.

    A posição é invariante por decisão, não por descuido: a cobertura de
    `nu_latitude` em São Paulo vai de 0,45% em 2017 a 57,5% em 2022, então
    exigir a coordenada do próprio período deixaria a janela de treino sem nós
    posicionáveis. Ver D-15, que registra a medição e o custo dessa escolha.

    `politica='mais_antiga'` é o default e toma a primeira observação válida da
    série. É deliberadamente diferente de tomar a mais recente: as duas usam
    informação posterior ao período modelado, mas a mais antiga minimiza a
    distância entre o dado usado e o período em questão. `'mais_recente'`
    existe para quem quiser a coordenada mais provavelmente correta, aceitando
    olhar mais adiante.

    `periodo_referencia` corta a série antes de escolher, o que permite montar o
    grafo sem enxergar nada além de uma data — útil para verificar quanto o
    resultado depende da suposição de invariância.

    `desvios` controla o corte de outlier relativo à amostra, em múltiplos do
    desvio absoluto mediano. Ver `_descartar_fora_da_amostra` e D-17.

    Linhas sem coordenada utilizável são descartadas. Contar o descarte é
    responsabilidade do chamador, e reportá-lo ao lado da métrica é obrigação
    de D-15.
    """
    if politica not in ("mais_antiga", "mais_recente"):
        raise ValueError(
            f"politica deve ser 'mais_antiga' ou 'mais_recente'; recebido {politica!r}"
        )
    raiz = db.table_dict[TABELA_RAIZ].df
    colunas = [COL_ENTIDADE, COL_LATITUDE, COL_LONGITUDE, COL_TEMPO]
    faltando = [c for c in colunas if c not in raiz.column_names]
    if faltando:
        raise ErroGrafo(
            f"{TABELA_RAIZ} não tem as colunas {faltando}; a trilha geográfica "
            "depende delas. Confira docs/01-selecao-tabelas.md."
        )

    df = raiz.select(colunas).to_pandas()
    if periodo_referencia:
        df = df[df[COL_TEMPO] <= data_do_periodo(periodo_referencia)]

    df = df.dropna(subset=[COL_LATITUDE, COL_LONGITUDE])
    # Sentinela do CNES: coordenada zerada é ausência, não a ilha de Null.
    df = df[(df[COL_LATITUDE] != 0) | (df[COL_LONGITUDE] != 0)]
    # Caixa do Brasil: descarta erro grosseiro de sinal ou de campo trocado.
    df = df[df[COL_LATITUDE].between(-34.0, 6.0) & df[COL_LONGITUDE].between(-74.0, -34.0)]
    df = _descartar_fora_da_amostra(df, desvios)

    agrupado = df.sort_values(COL_TEMPO).groupby(COL_ENTIDADE, as_index=False)
    escolhido = agrupado.first() if politica == "mais_antiga" else agrupado.last()
    return escolhido.drop(columns=[COL_TEMPO]).reset_index(drop=True)


def montar_grafo_geografico(
    db: Database,
    k: int = 10,
    raio_km: float | None = None,
    periodo_referencia: str | None = None,
    politica_coordenada: str = "mais_antiga",
) -> GrafoGeografico:
    """
    Liga cada estabelecimento aos `k` mais próximos, opcionalmente cortando por raio.

    Usa distância de grande círculo (haversine), não euclidiana sobre graus:
    um grau de longitude vale cerca de 96 km na latitude de São Paulo e 111 km
    de latitude, então tratar graus como plano distorce a vizinhança.

    O grafo é tornado simétrico: se A está entre os k vizinhos de B mas B não
    está entre os de A, a aresta existe nos dois sentidos. Vizinhança física é
    uma relação simétrica, e um kNN cru não é.
    """
    from sklearn.neighbors import BallTree

    coords = coordenadas_por_unidade(db, periodo_referencia, politica_coordenada)
    if len(coords) < 2:
        raise ErroGrafo(
            f"apenas {len(coords)} estabelecimentos com coordenada válida; "
            "a trilha geográfica precisa de ao menos dois"
        )

    k_efetivo = min(k, len(coords) - 1)
    radianos = np.radians(coords[[COL_LATITUDE, COL_LONGITUDE]].to_numpy())
    arvore = BallTree(radianos, metric="haversine")
    distancias, vizinhos = arvore.query(radianos, k=k_efetivo + 1)

    # A primeira coluna é o próprio nó, a distância zero. Descartada.
    distancias, vizinhos = distancias[:, 1:] * RAIO_TERRA_KM, vizinhos[:, 1:]

    origem = np.repeat(np.arange(len(coords)), k_efetivo)
    destino = vizinhos.ravel()
    dist = distancias.ravel()

    if raio_km is not None:
        dentro = dist <= raio_km
        origem, destino, dist = origem[dentro], destino[dentro], dist[dentro]

    # Simetrização, com deduplicação do par não ordenado.
    pares = np.concatenate(
        [np.stack([origem, destino]), np.stack([destino, origem])], axis=1
    )
    todas_dist = np.concatenate([dist, dist])
    chave = pares[0] * len(coords) + pares[1]
    _, primeiro = np.unique(chave, return_index=True)
    pares, todas_dist = pares[:, primeiro], todas_dist[primeiro]

    arestas = pa.table(
        {
            "origem": pares[0],
            "destino": pares[1],
            "distancia_km": todas_dist,
        }
    )
    return GrafoGeografico(
        unidades=coords[COL_ENTIDADE].tolist(),
        arestas=arestas,
        coordenadas=coords,
        k=k_efetivo,
        raio_km=raio_km,
    )
