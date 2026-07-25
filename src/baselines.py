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
from sklearn.preprocessing import OrdinalEncoder

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
    """Escores de um modelo sobre um conjunto, com a proveniência anexada."""

    modelo: str
    conjunto: str
    escore: np.ndarray
    y: np.ndarray
    entidades: np.ndarray
    metadados: dict = field(default_factory=dict)


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
    df = tarefa.por_conjunto(conjunto)
    return Previsao(
        modelo="persistencia",
        conjunto=conjunto,
        escore=np.zeros(len(df)),
        y=df[COL_ROTULO].to_numpy(),
        entidades=df[tarefa.col_entidade].to_numpy(),
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

    df = tarefa.por_conjunto(conjunto)
    return Previsao(
        modelo="popularidade_item",
        conjunto=conjunto,
        escore=df[tarefa.col_item].map(taxa).fillna(base).to_numpy(),
        y=df[COL_ROTULO].to_numpy(),
        entidades=df[tarefa.col_entidade].to_numpy(),
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
    Codifica categóricas ajustando o encoder **apenas no treino**.

    Categoria inédita na avaliação vira -1 em vez de erro: um estabelecimento ou
    equipamento que só aparece no futuro é situação legítima, e abortar por causa
    dela seria pior que tratá-la como desconhecida.
    """
    codificador = OrdinalEncoder(
        handle_unknown="use_encoded_value", unknown_value=-1, encoded_missing_value=-2
    )
    colunas = list(treino.columns)
    return (
        codificador.fit_transform(treino[colunas].astype(str)),
        codificador.transform(avaliar[colunas].astype(str)),
    )


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

    return Previsao(
        modelo="gbdt_ultimo_snapshot" if apenas_ultimo_snapshot else "gbdt_geral",
        conjunto=conjunto,
        escore=escore,
        y=y_avaliar,
        entidades=tarefa.df.loc[mascara_avaliar, tarefa.col_entidade].to_numpy(),
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
    entidades = tarefa.df[tarefa.col_entidade].to_numpy()
    rotulos = tarefa.df[COL_ROTULO].to_numpy()

    indices_avaliar = np.flatnonzero(mascara_avaliar)
    proprios = 0

    for entidade in np.unique(entidades[mascara_avaliar]):
        do_treino = np.flatnonzero(mascara_treino & (entidades == entidade))
        if len(do_treino) < minimo or len(np.unique(rotulos[do_treino])) < 2:
            continue

        alvo = np.flatnonzero(mascara_avaliar & (entidades == entidade))
        x_treino, x_alvo = _codificar(
            features.iloc[do_treino], features.iloc[alvo]
        )
        modelo = HistGradientBoostingClassifier(random_state=SEMENTE)
        modelo.fit(x_treino, rotulos[do_treino])

        posicoes = np.searchsorted(indices_avaliar, alvo)
        escore[posicoes] = modelo.predict_proba(x_alvo)[:, 1]
        proprios += 1

    return Previsao(
        modelo="por_entidade",
        conjunto=conjunto,
        escore=escore,
        y=geral.y,
        entidades=geral.entidades,
        metadados={
            "entidades_com_modelo_proprio": proprios,
            "entidades_avaliadas": int(len(np.unique(entidades[mascara_avaliar]))),
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
