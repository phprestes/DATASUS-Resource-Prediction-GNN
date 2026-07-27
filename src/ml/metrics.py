"""
Métricas, compartilhadas pelas três trilhas para que os números sejam comparáveis.

A escolha da métrica principal não é neutra. A tarefa de aquisição é fortemente
desbalanceada — a esmagadora maioria dos pares (estabelecimento, equipamento)
não sofre aquisição num intervalo de um ano — e sob esse regime a AUC-ROC é
otimista: ela pondera igualmente os erros nas duas classes, então um modelo que
acerta a classe majoritária ganha AUC alta sem ter aprendido nada sobre a
minoritária, que é a de interesse.

Daí **average precision** ser a principal. Ela resume a curva
precisão-revocação, cuja linha de base é a prevalência, e não 0,5.

Ver docs/02-metodologia.md, seção 6.2.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import rankdata
from sklearn.metrics import average_precision_score, mean_absolute_error


def average_precision(y: np.ndarray, escore: np.ndarray) -> float:
    """
    AP. Linha de base é a prevalência, não 0,5.

    Sem positivo algum a métrica é indefinida — devolve NaN em vez de zero, que
    seria lido como "modelo ruim" em vez de "conjunto sem sinal a medir".

    Args:
        y: rótulos binários, 0 ou 1.
        escore: escore contínuo, maior significando mais provável.

    Returns:
        AP entre 0 e 1, ou NaN quando `y` é constante.
    """
    y = np.asarray(y)
    if y.sum() == 0 or y.sum() == len(y):
        return float("nan")
    return float(average_precision_score(y, escore))


def auc_roc(y: np.ndarray, escore: np.ndarray) -> float:
    """
    AUC-ROC pela estatística de postos de Mann-Whitney.

    Matematicamente idêntica ao `roc_auc_score` do sklearn, incluindo o
    tratamento de empates por posto médio, mas sem o caminho de
    `label_binarize`, que constrói uma matriz esparsa e a densifica para
    (n, 2) `int64`. Com 11,7 milhões de exemplos de teste isso são centenas de
    megabytes alocados para calcular um único número, e foi o que estourou a
    memória no recorte estadual.

    A identidade usada: a AUC é a probabilidade de um positivo sorteado ao acaso
    receber escore maior que um negativo sorteado ao acaso, que é exatamente a
    soma dos postos dos positivos, descontada a soma mínima possível, dividida
    pelo número de pares.

    Args:
        y: rótulos binários, 0 ou 1.
        escore: escore contínuo, maior significando mais provável.

    Returns:
        AUC entre 0 e 1, ou NaN quando `y` é constante. Escore constante devolve
        exatamente 0,5.
    """
    y = np.asarray(y)
    n_pos = int(y.sum())
    n_neg = len(y) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")

    postos = rankdata(escore)
    soma_positivos = float(postos[y == 1].sum())
    return (soma_positivos - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def map_at_k(
    entidades: np.ndarray,
    y: np.ndarray,
    escore: np.ndarray,
    k: int = 10,
    semente: int = 42,
) -> float:
    """
    Precisão média nos k primeiros, por entidade, e então a média entre entidades.

    É a métrica que reflete o uso pretendido: a saída do modelo é uma lista de
    onde olhar primeiro em cada estabelecimento, então o que importa é a ordem
    dentro de cada estabelecimento, não a ordem global. Entidades sem nenhum
    positivo são excluídas, porque para elas não existe acerto possível e
    incluí-las apenas dilui a média com zeros.

    **Empates são desfeitos aleatoriamente**, com semente fixa. Sem isso, um
    modelo de escore constante — a baseline de persistência — seria ranqueado
    pela ordem de entrada das linhas, e herdaria qualquer ordenação acidental da
    tabela como se fosse capacidade preditiva. Com desempate aleatório, escore
    constante recebe o MAP de um ranking ao azar, que é o que ele merece.

    Args:
        entidades: identificador da entidade de cada linha; o agrupamento é feito
            por ele. Aceita códigos inteiros, que custam bem menos que strings.
        y: rótulos binários, 0 ou 1.
        escore: escore contínuo, maior significando mais provável.
        k: tamanho do topo considerado em cada entidade.
        semente: semente do desempate aleatório.

    Returns:
        Média das precisões médias no topo-k entre as entidades que têm ao menos
        um positivo, ou NaN se nenhuma tem.
    """
    y = np.asarray(y, dtype=np.int8)
    # Códigos inteiros: agrupar por string de 13 caracteres em dezenas de milhões
    # de linhas custa memória e tempo desnecessários. `int32` cobre bem mais
    # entidades do que existem no país e custa metade do `int64` que o
    # `factorize` devolve.
    codigos = np.asarray(pd.factorize(entidades, sort=False)[0], dtype=np.int32)
    ruido = np.random.default_rng(semente).random(len(y)).astype(np.float32)
    # Negar o escore em float32 evita a cópia em float64 que `-escore` faria
    # sobre um vetor já em precisão dupla.
    escore_invertido = np.negative(escore, dtype=np.float32)

    # Uma única ordenação lexicográfica em vez de um DataFrame intermediário:
    # entidade crescente, escore decrescente, empate desfeito ao azar. Com 11
    # milhões de linhas, montar o DataFrame de quatro colunas e ordená-lo
    # custava mais de um gigabyte de pico.
    ordem = np.lexsort((ruido, escore_invertido, codigos))
    del ruido, escore_invertido

    chaves = codigos[ordem]
    acertos_ordenados = y[ordem]
    del ordem, codigos

    cortes = np.flatnonzero(np.diff(chaves)) + 1
    del chaves
    precisoes: list[float] = []

    for bloco in np.split(acertos_ordenados, cortes):
        positivos = int(bloco.sum())
        if positivos == 0:
            continue
        topo = bloco[:k]
        if topo.sum() == 0:
            precisoes.append(0.0)
            continue
        precisao_em_i = np.cumsum(topo) / np.arange(1, len(topo) + 1)
        # Divide pelo mínimo entre k e o total de positivos da entidade: é o
        # máximo de acertos alcançável no topo-k, então a métrica chega a 1,0
        # quando o ranking é perfeito, mesmo que haja mais positivos que k.
        precisoes.append(float((precisao_em_i * topo).sum() / min(k, positivos)))

    return float(np.mean(precisoes)) if precisoes else float("nan")


def rmse(y: np.ndarray, previsto: np.ndarray) -> float:
    """
    Raiz do erro quadrático médio, da tarefa secundária de quantidade.

    Args:
        y: valores observados.
        previsto: valores previstos, mesmo comprimento de `y`.

    Returns:
        RMSE na unidade de `y`.
    """
    y, previsto = np.asarray(y, dtype=float), np.asarray(previsto, dtype=float)
    return float(np.sqrt(np.mean((y - previsto) ** 2)))


def mae(y: np.ndarray, previsto: np.ndarray) -> float:
    """
    Erro absoluto médio, menos sensível a outlier que o RMSE.

    Args:
        y: valores observados.
        previsto: valores previstos, mesmo comprimento de `y`.

    Returns:
        MAE na unidade de `y`.
    """
    return float(mean_absolute_error(y, previsto))


def avaliar_classificacao(
    y: np.ndarray, escore: np.ndarray, entidades: np.ndarray | None = None, k: int = 10
) -> dict[str, float]:
    """
    Bloco padrão de métricas da tarefa primária, com a prevalência ao lado.

    A prevalência entra junto porque é a linha de base do AP: sem ela, um AP de
    0,01 não é interpretável.

    Args:
        y: rótulos binários, 0 ou 1.
        escore: escore contínuo, maior significando mais provável.
        entidades: identificador da entidade de cada linha. Se `None`, o MAP@k é
            omitido do resultado.
        k: tamanho do topo do MAP@k.

    Returns:
        Mapa com `n`, `positivos`, `prevalencia`, `average_precision`, `auc_roc`
        e, quando `entidades` é dado, `map@{k}`.
    """
    y = np.asarray(y)
    resultado = {
        "n": int(len(y)),
        "positivos": int(y.sum()),
        "prevalencia": float(y.mean()) if len(y) else float("nan"),
        "average_precision": average_precision(y, escore),
        "auc_roc": auc_roc(y, escore),
    }
    if entidades is not None:
        resultado[f"map@{k}"] = map_at_k(entidades, y, escore, k)
    return resultado


def avaliar_regressao(y: np.ndarray, previsto: np.ndarray) -> dict[str, float]:
    """
    Bloco padrão de métricas da tarefa secundária de quantidade.

    Args:
        y: valores observados.
        previsto: valores previstos, mesmo comprimento de `y`.

    Returns:
        Mapa com `n`, `rmse` e `mae`.
    """
    return {
        "n": int(len(y)),
        "rmse": rmse(y, previsto),
        "mae": mae(y, previsto),
    }


def tabela_de_resultados(resultados: dict[str, dict[str, float]]) -> pd.DataFrame:
    """
    Consolida {nome_do_modelo: métricas} numa tabela ordenada pela principal.

    Existe para tornar mecânico o cumprimento da regra de reporte: nenhum
    resultado de GNN aparece sem as baselines na mesma tabela (D-11). Passe
    todos os modelos de uma vez em vez de imprimir um por um.

    Args:
        resultados: mapa `{nome_do_modelo: métricas}`, com as métricas no formato
            devolvido por `avaliar_classificacao` ou `avaliar_regressao`.

    Returns:
        DataFrame com um modelo por linha, ordenado por `average_precision`
        decrescente — ou por `rmse` crescente, se for tarefa de regressão.
    """
    df = pd.DataFrame(resultados).T
    principal = "average_precision" if "average_precision" in df.columns else "rmse"
    crescente = principal == "rmse"
    return df.sort_values(principal, ascending=crescente)
