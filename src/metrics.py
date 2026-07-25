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
from sklearn.metrics import (
    average_precision_score,
    mean_absolute_error,
    roc_auc_score,
)


def average_precision(y: np.ndarray, escore: np.ndarray) -> float:
    """
    AP. Linha de base é a prevalência, não 0,5.

    Sem positivo algum a métrica é indefinida — devolve NaN em vez de zero, que
    seria lido como "modelo ruim" em vez de "conjunto sem sinal a medir".
    """
    y = np.asarray(y)
    if y.sum() == 0 or y.sum() == len(y):
        return float("nan")
    return float(average_precision_score(y, escore))


def auc_roc(y: np.ndarray, escore: np.ndarray) -> float:
    y = np.asarray(y)
    if y.sum() == 0 or y.sum() == len(y):
        return float("nan")
    return float(roc_auc_score(y, escore))


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
    """
    ruido = np.random.default_rng(semente).random(len(escore))
    df = pd.DataFrame(
        {
            "entidade": entidades,
            "y": np.asarray(y),
            "escore": escore,
            "desempate": ruido,
        }
    ).sort_values(["escore", "desempate"], ascending=False)
    precisoes: list[float] = []

    for _, grupo in df.groupby("entidade", sort=False):
        if grupo["y"].sum() == 0:
            continue
        # O DataFrame já vem ordenado por (escore, desempate), então head(k) é o
        # topo-k com empates desfeitos ao azar.
        acertos = grupo.head(k)["y"].to_numpy()
        if acertos.sum() == 0:
            precisoes.append(0.0)
            continue
        posicoes = np.arange(1, len(acertos) + 1)
        precisao_em_i = np.cumsum(acertos) / posicoes
        # Divide pelo mínimo entre k e o total de positivos da entidade: é o
        # máximo de acertos alcançável no topo-k, então a métrica chega a 1,0
        # quando o ranking é perfeito, mesmo que haja mais positivos que k.
        divisor = min(k, int(grupo["y"].sum()))
        precisoes.append(float((precisao_em_i * acertos).sum() / divisor))

    return float(np.mean(precisoes)) if precisoes else float("nan")


def rmse(y: np.ndarray, previsto: np.ndarray) -> float:
    y, previsto = np.asarray(y, dtype=float), np.asarray(previsto, dtype=float)
    return float(np.sqrt(np.mean((y - previsto) ** 2)))


def mae(y: np.ndarray, previsto: np.ndarray) -> float:
    return float(mean_absolute_error(y, previsto))


def avaliar_classificacao(
    y: np.ndarray, escore: np.ndarray, entidades: np.ndarray | None = None, k: int = 10
) -> dict[str, float]:
    """Bloco padrão de métricas da tarefa primária, com a prevalência ao lado."""
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
    """
    df = pd.DataFrame(resultados).T
    principal = "average_precision" if "average_precision" in df.columns else "rmse"
    crescente = principal == "rmse"
    return df.sort_values(principal, ascending=crescente)
