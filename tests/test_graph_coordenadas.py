"""
Testes do corte de outlier de coordenada de src/ml/graph.py.

Existem por um modo de falha silencioso: a caixa robusta era medida sobre a
amostra inteira, e a escala do MAD cresce com o recorte. No recorte estadual ela
já não descartava nada, e no nacional descartaria menos ainda — um filtro
documentado como ativo que na prática era inerte. Ver D-17.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.ml.graph import (
    COL_ENTIDADE,
    COL_LATITUDE,
    COL_LONGITUDE,
    COL_MUNICIPIO,
    _descartar_fora_da_amostra,
)


def cidade(codigo: str, centro: tuple[float, float], n: int, semente: int) -> pd.DataFrame:
    """Nuvem compacta de estabelecimentos em torno de um centro."""
    rng = np.random.default_rng(semente)
    lat, lon = centro
    return pd.DataFrame(
        {
            COL_ENTIDADE: [f"{codigo}{i:04d}" for i in range(n)],
            COL_MUNICIPIO: codigo,
            COL_LATITUDE: rng.normal(lat, 0.02, n),
            COL_LONGITUDE: rng.normal(lon, 0.02, n),
        }
    )


def amostra_com_outlier() -> tuple[pd.DataFrame, str]:
    """Dois municípios distantes, e um ponto de um deles jogado no outro."""
    sp = cidade("355030", (-23.55, -46.63), 200, semente=1)
    ribeirao = cidade("354340", (-21.17, -47.81), 200, semente=2)

    intruso = sp.index[0]
    sp.loc[intruso, [COL_LATITUDE, COL_LONGITUDE]] = [-21.17, -47.81]
    return pd.concat([sp, ribeirao], ignore_index=True), sp.loc[intruso, COL_ENTIDADE]


def test_corte_por_municipio_descarta_o_ponto_deslocado():
    df, deslocado = amostra_com_outlier()

    mantidos = _descartar_fora_da_amostra(df, desvios=40.0)

    assert deslocado not in set(mantidos[COL_ENTIDADE])
    assert len(mantidos) == len(df) - 1


def test_sobre_a_amostra_inteira_o_mesmo_ponto_passa():
    """O comportamento anterior, preservado como controle: nada é descartado."""
    df, deslocado = amostra_com_outlier()

    mantidos = _descartar_fora_da_amostra(df, desvios=40.0, por_municipio=False)

    assert deslocado in set(mantidos[COL_ENTIDADE])


def test_municipio_pequeno_demais_passa_inteiro():
    """Sem pontos suficientes não há escala; descartar seria arbitrário."""
    df = cidade("350000", (-22.0, -47.0), 5, semente=3)
    df.loc[0, [COL_LATITUDE, COL_LONGITUDE]] = [-5.0, -60.0]

    assert len(_descartar_fora_da_amostra(df, desvios=40.0)) == len(df)


def test_sem_coluna_de_municipio_cai_para_a_amostra_inteira():
    df, _ = amostra_com_outlier()

    mantidos = _descartar_fora_da_amostra(df.drop(columns=[COL_MUNICIPIO]), desvios=40.0)

    assert len(mantidos) == len(df)


def test_colunas_e_unicidade_preservadas():
    df, _ = amostra_com_outlier()

    mantidos = _descartar_fora_da_amostra(df, desvios=40.0)

    assert list(mantidos.columns) == list(df.columns)
    assert mantidos[COL_ENTIDADE].is_unique
