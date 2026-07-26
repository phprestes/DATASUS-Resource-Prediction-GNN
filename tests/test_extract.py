"""
Testes da amostra temporal canônica.

Existem porque a série cresce: 202601 entrou depois de nove competências (D-29),
e todo módulo que precisava saber quantos snapshots há passou a derivar de
`PERIODOS_ANUAIS` em vez de repetir um literal. Se esta constante quebrar a
forma, o que quebra depois é a partição temporal — silenciosamente.
"""

from __future__ import annotations

import re

from src.etl.extract import ANO_FINAL, ANO_INICIAL, PERIODOS_ANUAIS


def test_serie_e_janeiro_de_cada_ano_sem_furo():
    assert PERIODOS_ANUAIS == [f"{ano}01" for ano in range(ANO_INICIAL, ANO_FINAL + 1)]
    assert all(re.fullmatch(r"\d{4}01", p) for p in PERIODOS_ANUAIS)
    assert PERIODOS_ANUAIS == sorted(PERIODOS_ANUAIS)
    assert len(set(PERIODOS_ANUAIS)) == len(PERIODOS_ANUAIS)


def test_serie_cobre_o_intervalo_declarado():
    assert PERIODOS_ANUAIS[0] == f"{ANO_INICIAL}01"
    assert PERIODOS_ANUAIS[-1] == f"{ANO_FINAL}01"
    assert len(PERIODOS_ANUAIS) == ANO_FINAL - ANO_INICIAL + 1


def test_serie_sustenta_a_particao_canonica():
    """
    Uma transição de teste, duas de validação e ao menos uma de treino.

    É o mínimo que `src/ml/splits.py` aceita. Encurtar a amostra abaixo disso
    quebraria a partição, e o erro apareceria longe daqui.
    """
    from src.ml.splits import particionar

    particao = particionar(list(PERIODOS_ANUAIS))
    assert len(particao.teste) == 1
    assert len(particao.validacao) == 2
    assert len(particao.treino) == len(PERIODOS_ANUAIS) - 4
    assert particao.teste[0].destino == PERIODOS_ANUAIS[-1]
