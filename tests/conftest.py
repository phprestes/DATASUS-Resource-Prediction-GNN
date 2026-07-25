"""Fixtures compartilhadas: snapshots Parquet sintéticos, sem depender de download."""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

# Mesmo schema de rlEstabEquipamento na camada primária, reduzido às colunas
# declaradas em docs/01-selecao-tabelas.md.
SCHEMA_EQUIPAMENTO = pa.schema(
    [
        ("co_unidade", pa.string()),
        ("co_equipamento", pa.string()),
        ("co_tipo_equipamento", pa.string()),
        ("tp_sus", pa.string()),
        ("qt_existente", pa.int64()),
        ("qt_uso", pa.int64()),
        ("to_chardt_atualizacaoddmmyyyy", pa.string()),
    ]
)


def equipamento(
    unidade: str,
    equipamento: str,
    *,
    tipo: str = "1",
    sus: str = "1",
    existente: int = 1,
    uso: int = 1,
    atualizacao: str = "01/01/2017",
) -> dict:
    return {
        "co_unidade": unidade,
        "co_equipamento": equipamento,
        "co_tipo_equipamento": tipo,
        "tp_sus": sus,
        "qt_existente": existente,
        "qt_uso": uso,
        "to_chardt_atualizacaoddmmyyyy": atualizacao,
    }


@pytest.fixture
def camada_primaria(tmp_path: Path):
    """
    Fábrica de snapshots na camada primária.

    Devolve `(raiz, escrever)`, onde `escrever(periodo, linhas, tabela=...)`
    materializa um Parquet no layout que src/changes.py espera:
    `{raiz}/{periodo}/{tabela}.parquet`.
    """
    raiz = tmp_path / "03_primary"

    def escrever(
        periodo: str,
        linhas: list[dict],
        tabela: str = "rlEstabEquipamento",
        schema: pa.Schema = SCHEMA_EQUIPAMENTO,
    ) -> Path:
        pasta = raiz / periodo
        pasta.mkdir(parents=True, exist_ok=True)
        destino = pasta / f"{tabela}.parquet"
        pq.write_table(pa.Table.from_pylist(linhas, schema=schema), destino)
        return destino

    return raiz, escrever
