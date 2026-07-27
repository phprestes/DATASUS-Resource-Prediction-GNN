"""
A tabela de tarefa precisa sair em ordem canônica, sempre a mesma.

Existe por causa de um bug medido, não por precaução. O `SELECT` final de
`_candidatos_da_transicao` fazia um `LEFT JOIN` sem `ORDER BY`, e o hash join
paralelo do DuckDB devolve linhas em ordem arbitrária. A composição da tabela era
idêntica entre execuções; a ordem, não.

O treino sorteia o minilote por **índice** (`torch.randint` com gerador de semente
fixa). Mesmos índices sobre ordens diferentes selecionam linhas diferentes, então
duas execuções com a mesma semente divergiam já na primeira época. Medido: melhor
época 10 contra 99, MAP@10 0,189 contra 0,300. Ver D-42.

O LightGBM das baselines tem o mesmo problema pelo mesmo motivo — treina na ordem
em que as linhas chegam.
"""

from __future__ import annotations

import pandas as pd
import pyarrow as pa
import pytest

from src.etl.changes import Transicao
from src.ml.splits import ParticaoTemporal
from src.ml.tasks import COL_ROTULO, tarefa_aquisicao
from tests.conftest import equipamento

SCHEMA_RAIZ = pa.schema(
    [
        ("co_unidade", pa.string()),
        ("co_municipio_gestor", pa.string()),
        ("nu_latitude", pa.float64()),
        ("nu_longitude", pa.float64()),
    ]
)

PERIODOS = ["201701", "201801", "201901", "202001"]


def _estabelecimento(unidade: str) -> dict:
    return {
        "co_unidade": unidade,
        "co_municipio_gestor": "355030",
        "nu_latitude": -23.5,
        "nu_longitude": -46.6,
    }


@pytest.fixture
def cenario(camada_primaria):
    """
    Camada primária pequena mas larga o bastante para o DuckDB paralelizar.

    Com poucas dezenas de linhas o executor não divide o trabalho e a ordem sai
    estável por acidente, o que faria o teste passar sem medir nada. Duzentos
    estabelecimentos por 25 itens dão 5.000 candidatos por transição, suficiente
    para o hash join ser paralelo.
    """
    raiz, escrever = camada_primaria
    unidades = [f"{7000000 + i}" for i in range(200)]
    itens = [f"{i:02d}" for i in range(1, 26)]

    for k, periodo in enumerate(PERIODOS):
        escrever(periodo, [_estabelecimento(u) for u in unidades],
                 tabela="tbEstabelecimento", schema=SCHEMA_RAIZ)
        # Cada competência acrescenta um item a cada unidade, o que gera
        # aquisição em toda transição.
        linhas = [
            equipamento(u, itens[(i + j) % len(itens)])
            for i, u in enumerate(unidades)
            for j in range(k + 1)
        ]
        escrever(periodo, linhas)
    return raiz


def _particao() -> ParticaoTemporal:
    t = [Transicao(PERIODOS[i], PERIODOS[i + 1]) for i in range(len(PERIODOS) - 1)]
    return ParticaoTemporal(treino=(t[0],), validacao=(t[1],), teste=(t[2],))


def _assinatura(df: pd.DataFrame, col_entidade: str, col_item: str) -> str:
    """Hash que depende da ordem das linhas, não só do conteúdo."""
    chave = (
        df[col_entidade].astype(str)
        + "|"
        + df[col_item].astype(str)
        + "|"
        + df[COL_ROTULO].astype(str)
    )
    return pd.util.hash_pandas_object(chave, index=False).sum().astype(str)


def test_tabela_de_tarefa_sai_na_mesma_ordem_em_toda_construcao(cenario):
    """Duas construções idênticas devem produzir a mesma sequência de linhas."""
    particao = _particao()
    primeira = tarefa_aquisicao(
        particao, recorte="355030", pasta=cenario, negativos_por_positivo=None
    )
    segunda = tarefa_aquisicao(
        particao, recorte="355030", pasta=cenario, negativos_por_positivo=None
    )

    assert len(primeira.df) == len(segunda.df)
    assert _assinatura(primeira.df, primeira.col_entidade, primeira.col_item) == (
        _assinatura(segunda.df, segunda.col_entidade, segunda.col_item)
    ), (
        "a tabela de tarefa saiu em ordem diferente entre duas construções; o "
        "minilote de treino é sorteado por índice, então isso torna o treino "
        "irreprodutível (D-42)"
    )


def test_ordem_e_canonica_por_periodo_entidade_e_item(cenario):
    """
    Não basta ser estável: precisa ser previsível.

    Ordem canônica é `(periodo_destino, entidade, item)`. Ordenar por qualquer
    coisa derivada do plano de execução seria estável hoje e mudaria com uma
    versão nova do DuckDB.
    """
    tarefa = tarefa_aquisicao(
        _particao(), recorte="355030", pasta=cenario, negativos_por_positivo=None
    )
    chaves = ["periodo_destino", tarefa.col_entidade, tarefa.col_item]
    # Comparar como texto: as colunas de entidade e item são `category`, e
    # ordenar uma categórica usa a ordem das categorias, não a da string. O
    # `ORDER BY` do DuckDB ordena a string, então é nessa escala que os dois
    # têm de bater.
    como_texto = tarefa.df[chaves].astype(str).reset_index(drop=True)
    esperado = como_texto.sort_values(chaves, kind="mergesort").reset_index(drop=True)
    pd.testing.assert_frame_equal(como_texto, esperado)
