"""
Trilha 1: baselines sem estrutura relacional.

O cronograma original previa estes quatro modelos e nenhum foi feito. Eles são o
que autoriza qualquer afirmação sobre as GNNs: uma métrica de GNN isolada não
distingue aprendizado de inércia do fenômeno (D-11).

    persistencia            nada muda; escore constante
    popularidade_item       taxa histórica de aquisição do tipo de equipamento
    gbdt_geral              gradient boosting sobre features achatadas
    gbdt_ultimo_snapshot    idem, treinado só na transição mais recente do treino
    por_entidade            um modelo por estabelecimento

Nenhum deles vê a estrutura relacional ou a vizinhança geográfica. É esse o
ponto: a diferença entre eles e as trilhas 2 e 3 é a medida do valor da
estrutura.

Todos consomem a `TabelaTarefa` de src/tasks.py e a partição de src/splits.py,
sem recalcular nada — é o que garante que comparem os mesmos exemplos.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

from src.splits import ErroParticao, ParticaoTemporal
from src.tasks import COL_CONJUNTO, COL_ROTULO, TabelaTarefa

# Estabelecimento com menos exemplos que isso não sustenta um modelo próprio;
# cai para a previsão do modelo geral.
MINIMO_POR_ENTIDADE = 30

SEMENTE = 42


class ErroBaseline(RuntimeError):
    """Baseline impossível de treinar com os dados fornecidos."""


@dataclass
class Previsao:
    """
    Escores de um modelo sobre um conjunto, com a proveniência anexada.

    `entidades` guarda **códigos inteiros**, não os identificadores originais.
    Com dezenas de milhões de linhas, um vetor de `co_unidade` como objetos
    Python custa quase um gigabyte; como `int32`, custa quarenta vezes menos.
    `rotulos_entidade` é o índice que traduz código para `co_unidade` quando
    isso for necessário — use `nomes_das_entidades()`.
    """

    modelo: str
    conjunto: str
    escore: np.ndarray
    y: np.ndarray
    entidades: np.ndarray
    rotulos_entidade: np.ndarray | None = None
    metadados: dict = field(default_factory=dict)

    def nomes_das_entidades(self) -> np.ndarray:
        """
        Traduz os códigos de volta para `co_unidade`.

        Materializa o vetor de strings, então só chame quando de fato precisar
        dos identificadores — para inspecionar resultados, não para calcular
        métricas.
        """
        if self.rotulos_entidade is None:
            return self.entidades
        return np.asarray(self.rotulos_entidade)[self.entidades]

    def mascara_de_entidades(self, aceitos: "set | list | np.ndarray") -> np.ndarray:
        """
        Máscara booleana das linhas cujas entidades estão no conjunto dado.

        Existe para a comparação pareada entre trilhas exigida por D-15: ela
        precisa restringir todas as trilhas ao mesmo subconjunto de nós, e
        fazê-lo sem reconstruir o vetor de strings.
        """
        if self.rotulos_entidade is None:
            return np.isin(self.entidades, list(aceitos))
        codigos_aceitos = np.flatnonzero(
            np.isin(np.asarray(self.rotulos_entidade), list(aceitos))
        )
        return np.isin(self.entidades, codigos_aceitos)


def _entidades_de(tarefa: TabelaTarefa, mascara) -> tuple[np.ndarray, np.ndarray | None]:
    """
    Códigos de entidade de um recorte, com o índice para traduzi-los de volta.

    Mantém a codificação categórica da tabela em vez de materializar strings.
    """
    serie = tarefa.df.loc[mascara, tarefa.col_entidade]
    if isinstance(serie.dtype, pd.CategoricalDtype):
        return serie.cat.codes.to_numpy(), np.asarray(serie.cat.categories)
    codigos, rotulos = pd.factorize(serie, sort=False)
    return codigos, np.asarray(rotulos)


def _validar_particao(tarefa: TabelaTarefa, particao: ParticaoTemporal) -> None:
    """
    Confere que a tabela de tarefa foi montada sob a partição recebida.

    Sem esta checagem, treinar com uma partição e avaliar com outra passaria em
    silêncio e produziria um número sem significado.
    """
    rotulos = set(tarefa.df[COL_CONJUNTO].unique())
    esperados = set(particao.conjuntos)
    if rotulos != esperados:
        raise ErroBaseline(
            f"tarefa {tarefa.nome!r} tem conjuntos {sorted(rotulos)}, mas a "
            f"partição define {sorted(esperados)}. A tabela de tarefa precisa "
            "ter sido montada com esta mesma partição."
        )

    periodos = set(tarefa.df.loc[tarefa.df[COL_CONJUNTO] == "treino", "periodo_destino"])
    try:
        from src.splits import verificar_features_sem_vazamento

        verificar_features_sem_vazamento(particao, periodos)
    except ErroParticao as erro:
        raise ErroBaseline(str(erro)) from erro


# ---------------------------------------------------------------------------
# Baselines sem treino
# ---------------------------------------------------------------------------


def persistencia(tarefa: TabelaTarefa, conjunto: str = "teste") -> Previsao:
    """
    O piso absoluto: o estado em t+1 é igual ao de t, logo nada é adquirido.

    Como todos os candidatos da tarefa de aquisição são, por construção, pares
    ausentes em t, esta baseline prevê zero para tudo. O AP resultante é
    exatamente a prevalência, e a AUC-ROC é 0,5. Não é um modelo competitivo — é
    a régua que diz quanto do resultado de qualquer outro modelo é informação e
    quanto é o desbalanceamento da classe.
    """
    mascara = tarefa.df[COL_CONJUNTO] == conjunto
    codigos, rotulos = _entidades_de(tarefa, mascara)
    return Previsao(
        modelo="persistencia",
        conjunto=conjunto,
        escore=np.zeros(int(mascara.sum()), dtype=np.float32),
        y=tarefa.df.loc[mascara, COL_ROTULO].to_numpy(),
        entidades=codigos,
        rotulos_entidade=rotulos,
        metadados={"observacao": "prevê zero por construção; AP = prevalência"},
    )


def popularidade_item(
    tarefa: TabelaTarefa, particao: ParticaoTemporal, conjunto: str = "teste"
) -> Previsao:
    """
    Escore = taxa de aquisição histórica daquele tipo de item, estimada no treino.

    É a baseline trivial honesta para ranqueamento: alguns equipamentos são
    adquiridos com muito mais frequência que outros, e um modelo que só soubesse
    disso já ranquearia melhor que o azar. Bater a persistência é fácil; bater
    esta baseline é o que começa a exigir aprender algo sobre estabelecimentos.

    A taxa é estimada **apenas no treino**, com suavização de Laplace para não
    atribuir escore zero a item que nunca foi adquirido na janela de treino.
    """
    _validar_particao(tarefa, particao)
    if tarefa.col_item is None:
        raise ErroBaseline("popularidade_item exige tarefa com coluna de item")

    treino = tarefa.por_conjunto("treino")
    taxa = (
        treino.groupby(tarefa.col_item)[COL_ROTULO]
        .agg(["sum", "size"])
        .assign(taxa=lambda d: (d["sum"] + 1) / (d["size"] + 2))["taxa"]
    )
    base = float((treino[COL_ROTULO].sum() + 1) / (len(treino) + 2))

    mascara = tarefa.df[COL_CONJUNTO] == conjunto
    codigos, rotulos = _entidades_de(tarefa, mascara)
    itens = tarefa.df.loc[mascara, tarefa.col_item]
    return Previsao(
        modelo="popularidade_item",
        conjunto=conjunto,
        escore=itens.map(taxa).fillna(base).to_numpy(dtype=np.float32),
        y=tarefa.df.loc[mascara, COL_ROTULO].to_numpy(),
        entidades=codigos,
        rotulos_entidade=rotulos,
        metadados={"itens_estimados": int(len(taxa)), "taxa_base": base},
    )


# ---------------------------------------------------------------------------
# Baselines tabulares
# ---------------------------------------------------------------------------


def montar_features(
    tarefa: TabelaTarefa,
    atributos_entidade: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Achata a tarefa em features tabulares, sem relação alguma entre linhas.

    O conjunto mínimo é a identidade do item, a identidade da entidade e o
    período. `atributos_entidade` acrescenta colunas do estabelecimento — deve
    ser indexado por `co_unidade` e conter apenas informação disponível até o fim
    da janela de treino, cuja verificação é responsabilidade de quem monta.

    Não há agregado sobre a vizinhança nem contagem derivada de outras tabelas:
    incluí-los transformaria esta trilha numa versão pobre da trilha 2 e apagaria
    a diferença que o experimento quer medir.
    """
    colunas = [tarefa.col_entidade, "periodo_destino"]
    if tarefa.col_item:
        colunas.append(tarefa.col_item)

    features = tarefa.df[colunas].copy()
    if atributos_entidade is not None:
        features = features.merge(
            atributos_entidade,
            left_on=tarefa.col_entidade,
            right_index=True,
            how="left",
        )
    return features


def _codificar(
    treino: pd.DataFrame, avaliar: pd.DataFrame
) -> tuple[np.ndarray, np.ndarray]:
    """
    Codifica categóricas ajustando as categorias **apenas no treino**.

    Categoria inédita na avaliação vira -1 em vez de erro: um estabelecimento ou
    equipamento que só aparece no futuro é situação legítima, e abortar por causa
    dela seria pior que tratá-la como desconhecida.

    A implementação evita deliberadamente `OrdinalEncoder` sobre
    `.astype(str)`. Aquela combinação reconstruía o frame inteiro como objetos
    Python antes de codificar, o que em dezenas de milhões de linhas custa
    gigabytes de pico e foi o que estourou a memória. Aqui as categorias do
    treino viram um índice, e a avaliação é mapeada contra ele coluna a coluna,
    em `float32` — metade da memória do `float64` que o sklearn usaria.
    """
    colunas = list(treino.columns)
    x_treino = np.empty((len(treino), len(colunas)), dtype=np.float32)
    x_avaliar = np.empty((len(avaliar), len(colunas)), dtype=np.float32)

    for i, coluna in enumerate(colunas):
        serie_treino = treino[coluna]
        if pd.api.types.is_numeric_dtype(serie_treino) and not isinstance(
            serie_treino.dtype, pd.CategoricalDtype
        ):
            x_treino[:, i] = serie_treino.to_numpy(dtype=np.float32, na_value=-2)
            x_avaliar[:, i] = avaliar[coluna].to_numpy(dtype=np.float32, na_value=-2)
            continue

        categorias = pd.Categorical(serie_treino)
        x_treino[:, i] = categorias.codes
        # `categories=` reaproveita o índice do treino; valor ausente ou inédito
        # recebe código -1, que é exatamente a marca de desconhecido que se quer.
        x_avaliar[:, i] = pd.Categorical(
            avaliar[coluna], categories=categorias.categories
        ).codes

    return x_treino, x_avaliar


def gbdt(
    tarefa: TabelaTarefa,
    particao: ParticaoTemporal,
    features: pd.DataFrame | None = None,
    conjunto: str = "teste",
    apenas_ultimo_snapshot: bool = False,
    **kwargs,
) -> Previsao:
    """
    Gradient boosting sobre as features achatadas.

    Com `apenas_ultimo_snapshot=True`, treina só na transição mais recente do
    conjunto de treino. A comparação entre as duas variantes responde se a série
    histórica acrescenta algo ou se o estado presente basta — pergunta que o
    cronograma original fazia e que nunca foi respondida.
    """
    _validar_particao(tarefa, particao)
    features = features if features is not None else montar_features(tarefa)

    mascara_treino = tarefa.df[COL_CONJUNTO] == "treino"
    if apenas_ultimo_snapshot:
        ultimo = particao.treino[-1].destino
        mascara_treino &= tarefa.df["periodo_destino"] == ultimo
        if not mascara_treino.any():
            raise ErroBaseline(
                f"nenhum exemplo de treino na transição {ultimo}; a tabela de "
                "tarefa não cobre a última transição da janela de treino"
            )

    mascara_avaliar = tarefa.df[COL_CONJUNTO] == conjunto
    x_treino, x_avaliar = _codificar(features[mascara_treino], features[mascara_avaliar])
    y_treino = tarefa.df.loc[mascara_treino, COL_ROTULO].to_numpy()
    y_avaliar = tarefa.df.loc[mascara_avaliar, COL_ROTULO].to_numpy()

    regressao = tarefa.tipo == "regressao"
    Modelo = HistGradientBoostingRegressor if regressao else HistGradientBoostingClassifier
    modelo = Modelo(random_state=SEMENTE, **kwargs)
    modelo.fit(x_treino, y_treino)

    escore = (
        modelo.predict(x_avaliar)
        if regressao
        else modelo.predict_proba(x_avaliar)[:, 1]
    )

    codigos, rotulos = _entidades_de(tarefa, mascara_avaliar)
    return Previsao(
        modelo="gbdt_ultimo_snapshot" if apenas_ultimo_snapshot else "gbdt_geral",
        conjunto=conjunto,
        escore=escore.astype(np.float32),
        y=y_avaliar,
        entidades=codigos,
        rotulos_entidade=rotulos,
        metadados={
            "n_treino": int(mascara_treino.sum()),
            "features": list(features.columns),
        },
    )


def por_entidade(
    tarefa: TabelaTarefa,
    particao: ParticaoTemporal,
    features: pd.DataFrame | None = None,
    conjunto: str = "teste",
    minimo: int = MINIMO_POR_ENTIDADE,
) -> Previsao:
    """
    Um modelo por estabelecimento, com o modelo geral como rede de segurança.

    Mede quanta heterogeneidade existe entre estabelecimentos, ou seja, quanto se
    perde ao assumir um processo único para toda a rede. Estabelecimentos com
    menos de `minimo` exemplos de treino, ou sem as duas classes representadas,
    caem para a previsão do modelo geral — treinar num punhado de linhas de uma
    classe só produziria um modelo degenerado, não um resultado sobre
    heterogeneidade.
    """
    _validar_particao(tarefa, particao)
    features = features if features is not None else montar_features(tarefa)

    geral = gbdt(tarefa, particao, features, conjunto)
    escore = geral.escore.copy()

    mascara_treino = (tarefa.df[COL_CONJUNTO] == "treino").to_numpy()
    mascara_avaliar = (tarefa.df[COL_CONJUNTO] == conjunto).to_numpy()
    # Códigos inteiros em vez das strings: agrupar por string de 13 caracteres
    # em dezenas de milhões de linhas é caro em memória e em tempo.
    entidades = tarefa.codigos(tarefa.col_entidade)
    rotulos = tarefa.df[COL_ROTULO].to_numpy()

    indices_treino = np.flatnonzero(mascara_treino)
    indices_avaliar = np.flatnonzero(mascara_avaliar)

    # Índice invertido entidade -> posições, construído em uma passada.
    # A versão anterior fazia `entidades == entidade` dentro do laço, ou seja uma
    # varredura do vetor inteiro por entidade: com 136 mil estabelecimentos e
    # dezenas de milhões de linhas, isso é da ordem de 10^12 comparações.
    def agrupar(indices: np.ndarray) -> dict[int, np.ndarray]:
        ordem = indices[np.argsort(entidades[indices], kind="stable")]
        chaves = entidades[ordem]
        cortes = np.flatnonzero(np.diff(chaves)) + 1
        return dict(zip(chaves[np.r_[0, cortes]], np.split(ordem, cortes)))

    treino_por_entidade = agrupar(indices_treino)
    avaliar_por_entidade = agrupar(indices_avaliar)

    proprios = 0
    for entidade, alvo in avaliar_por_entidade.items():
        do_treino = treino_por_entidade.get(entidade)
        if do_treino is None or len(do_treino) < minimo:
            continue
        y_entidade = rotulos[do_treino]
        if y_entidade.min() == y_entidade.max():
            continue

        x_treino, x_alvo = _codificar(features.iloc[do_treino], features.iloc[alvo])
        modelo = HistGradientBoostingClassifier(random_state=SEMENTE)
        modelo.fit(x_treino, y_entidade)

        posicoes = np.searchsorted(indices_avaliar, alvo)
        escore[posicoes] = modelo.predict_proba(x_alvo)[:, 1]
        proprios += 1

    return Previsao(
        modelo="por_entidade",
        conjunto=conjunto,
        escore=escore,
        y=geral.y,
        entidades=geral.entidades,
        rotulos_entidade=geral.rotulos_entidade,
        metadados={
            "entidades_com_modelo_proprio": proprios,
            "entidades_avaliadas": len(avaliar_por_entidade),
            "minimo_exemplos": minimo,
        },
    )


def rodar_todas(
    tarefa: TabelaTarefa,
    particao: ParticaoTemporal,
    features: pd.DataFrame | None = None,
    conjunto: str = "teste",
) -> dict[str, Previsao]:
    """
    Roda as cinco baselines sobre o mesmo conjunto e devolve todas as previsões.

    Existe para que a regra de reporte de D-11 seja o caminho de menor esforço:
    a saída daqui alimenta `src.metrics.tabela_de_resultados` diretamente, com as
    baselines já ao lado de qualquer GNN que se queira acrescentar.
    """
    previsoes = [
        persistencia(tarefa, conjunto),
        popularidade_item(tarefa, particao, conjunto),
        gbdt(tarefa, particao, features, conjunto),
        gbdt(tarefa, particao, features, conjunto, apenas_ultimo_snapshot=True),
        por_entidade(tarefa, particao, features, conjunto),
    ]
    return {p.modelo: p for p in previsoes}
