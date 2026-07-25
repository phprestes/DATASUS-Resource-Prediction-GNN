"""
Testes de src/metrics.py.

Concentram-se nos casos em que uma métrica pode enganar: desbalanceamento,
conjunto sem positivo, e empate de escore. Os três aparecem de verdade na
tarefa de aquisição, e nos três o comportamento errado produz número plausível
em vez de erro.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.metrics import (
    average_precision,
    auc_roc,
    avaliar_classificacao,
    map_at_k,
    mae,
    rmse,
    tabela_de_resultados,
)


def test_ap_de_escore_constante_e_a_prevalencia():
    """
    O piso da métrica principal.

    A baseline de persistência prevê escore constante, e o AP resultante tem que
    ser exatamente a prevalência. É esse valor que separa "o modelo aprendeu
    algo" de "a classe é rara".
    """
    y = np.array([0, 0, 0, 1, 0, 0, 1, 0, 0, 0])
    assert average_precision(y, np.zeros(len(y))) == pytest.approx(y.mean())


def test_ap_de_ranking_perfeito_e_um():
    y = np.array([1, 1, 0, 0, 0])
    assert average_precision(y, np.array([0.9, 0.8, 0.3, 0.2, 0.1])) == pytest.approx(1.0)


def test_metricas_de_classificacao_sem_positivo_dao_nan():
    """
    Indefinido tem que sair NaN, não zero.

    Zero seria lido como "modelo péssimo"; NaN diz "não há o que medir aqui" —
    situação real quando uma transição não tem nenhuma aquisição.
    """
    y = np.zeros(5)
    escore = np.array([0.1, 0.9, 0.5, 0.3, 0.7])
    assert np.isnan(average_precision(y, escore))
    assert np.isnan(auc_roc(y, escore))


def test_auc_soa_respeitavel_onde_a_precisao_ainda_e_ruim():
    """
    O motivo de AP ser a métrica principal, em números.

    A escala da AUC-ROC não depende da prevalência: 0,5 é azar e 1,0 é perfeito,
    sempre. Então uma AUC de 0,63 soa razoável em qualquer contexto. Sob
    prevalência de 1%, o mesmo modelo tem AP de 0,12 — ou seja, olhar o topo do
    ranking dele ainda erra a grande maioria das vezes. Reportar apenas AUC
    convidaria o leitor a concluir que o modelo é utilizável.
    """
    rng = np.random.default_rng(0)
    y = np.zeros(2000)
    y[:20] = 1  # prevalência de 1%
    escore = rng.random(2000)
    escore[:20] += 0.12  # positivos apenas um pouco melhor ranqueados

    assert auc_roc(y, escore) > 0.6
    assert average_precision(y, escore) < 0.2


def test_map_desempata_aleatoriamente_e_nao_pela_ordem_de_entrada():
    """
    Escore constante não pode herdar a ordenação da tabela como se fosse acerto.

    Aqui os positivos estão todos no começo do array. Com desempate pela ordem de
    entrada, o MAP@2 sairia 1,0 — a persistência pareceria um ranqueador
    perfeito. Com desempate aleatório, fica bem abaixo disso.
    """
    entidades = np.repeat(["U1", "U2", "U3", "U4"], 10)
    y = np.tile(np.array([1, 1] + [0] * 8), 4)
    escore = np.zeros(len(y))

    assert map_at_k(entidades, y, escore, k=2) < 0.6


def test_map_de_ranking_perfeito_e_um():
    entidades = np.repeat(["U1", "U2"], 5)
    y = np.array([1, 1, 0, 0, 0, 1, 0, 0, 0, 0])
    escore = np.array([0.9, 0.8, 0.1, 0.1, 0.1, 0.9, 0.1, 0.1, 0.1, 0.1])

    assert map_at_k(entidades, y, escore, k=5) == pytest.approx(1.0)


def test_map_ignora_entidade_sem_positivo():
    """Entidade sem positivo não tem acerto possível; incluí-la só dilui a média."""
    entidades = np.array(["U1"] * 4 + ["U2"] * 4)
    y = np.array([1, 0, 0, 0, 0, 0, 0, 0])
    escore = np.array([0.9, 0.1, 0.1, 0.1, 0.5, 0.4, 0.3, 0.2])

    assert map_at_k(entidades, y, escore, k=2) == pytest.approx(1.0)


def test_map_alcanca_um_com_mais_positivos_que_k():
    """
    O divisor é min(k, positivos), então um topo-k inteiro de acertos vale 1,0.

    Sem isso, uma entidade com 20 positivos nunca passaria de 0,5 no MAP@10, e a
    métrica puniria o modelo por um limite que ela mesma impõe.
    """
    entidades = np.array(["U1"] * 6)
    y = np.array([1, 1, 1, 1, 0, 0])
    escore = np.array([0.9, 0.8, 0.7, 0.6, 0.1, 0.1])

    assert map_at_k(entidades, y, escore, k=2) == pytest.approx(1.0)


def test_metricas_de_regressao():
    y = np.array([1.0, 2.0, 3.0])
    previsto = np.array([1.0, 2.0, 5.0])
    assert rmse(y, previsto) == pytest.approx(np.sqrt(4 / 3))
    assert mae(y, previsto) == pytest.approx(2 / 3)


def test_avaliar_classificacao_traz_prevalencia_ao_lado():
    """A prevalência tem que vir junto: sem ela o AP não é interpretável."""
    y = np.array([0, 1, 0, 0])
    saida = avaliar_classificacao(y, np.array([0.1, 0.9, 0.2, 0.3]), y * 0 + 1)

    assert saida["n"] == 4
    assert saida["positivos"] == 1
    assert saida["prevalencia"] == pytest.approx(0.25)
    assert "average_precision" in saida and "map@10" in saida


def test_tabela_de_resultados_ordena_pela_metrica_principal():
    tabela = tabela_de_resultados(
        {
            "ruim": {"average_precision": 0.1, "auc_roc": 0.5},
            "bom": {"average_precision": 0.7, "auc_roc": 0.9},
        }
    )
    assert list(tabela.index) == ["bom", "ruim"]


def test_tabela_de_resultados_inverte_ordem_para_regressao():
    """Em RMSE, menor é melhor — a ordenação tem que virar."""
    tabela = tabela_de_resultados(
        {"ruim": {"rmse": 9.0}, "bom": {"rmse": 1.0}}
    )
    assert list(tabela.index) == ["bom", "ruim"]
