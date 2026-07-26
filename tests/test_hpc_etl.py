"""
Testes do ETL do servidor, na parte que roda sem dado real.

O que importa aqui é o isolamento e a conferência: o ETL do servidor precisa
escrever na raiz dele, e precisa saber dizer se produziu a **mesma** camada
primária que o do notebook. Sem essa segunda garantia, a matriz de D-34 poderia
estar comparando dado em vez de técnica.
"""

from __future__ import annotations

import duckdb
import pytest

from hpc.etl import pipeline


@pytest.fixture()
def raiz(tmp_path, monkeypatch):
    monkeypatch.setenv("IC_HPC_DATA", str(tmp_path / "ic"))
    return tmp_path


def _parquet_com(caminho, linhas: int) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(
        f"COPY (SELECT i AS co_unidade FROM range({linhas}) t(i)) "
        f"TO '{caminho}' (FORMAT 'parquet')"
    )
    con.close()


def test_competencia_sem_zip_nao_derruba_a_execucao(raiz):
    """
    Uma competência que falha não pode levar as outras oito com ela: sem
    escalonador, reiniciar o ETL inteiro por causa de um ZIP truncado custa horas.
    """
    resultado = pipeline.rodar(periodos=["209901"], pular_download=True)
    assert resultado["209901"] == 0


def test_escreve_na_raiz_do_servidor_e_nao_no_repositorio(raiz, monkeypatch):
    from src.config.paths import PRIMARY_FOLDER

    antes = set(PRIMARY_FOLDER.glob("*")) if PRIMARY_FOLDER.exists() else set()
    pipeline.rodar(periodos=["209901"], pular_download=True)
    depois = set(PRIMARY_FOLDER.glob("*")) if PRIMARY_FOLDER.exists() else set()
    assert antes == depois
    assert (raiz / "ic" / "03_primary").exists()


def test_competencia_ja_convertida_e_pulada(raiz):
    """Retomabilidade: o processo pode ser morto em 168 h e recomeçar de onde parou."""
    from hpc.config.paths import camadas

    mapa = camadas(criar=True)
    _parquet_com(mapa["primary"] / "202601" / "tbEstabelecimento.parquet", 10)
    resultado = pipeline.rodar(periodos=["202601"], pular_download=True)
    assert resultado["202601"] == 1


def test_conferencia_aprova_camadas_iguais(raiz, tmp_path):
    from hpc.config.paths import camadas

    mapa = camadas(criar=True)
    outra = tmp_path / "referencia"
    for destino in (mapa["primary"], outra):
        _parquet_com(destino / "202601" / "rlEstabEquipamento.parquet", 1_000)
    assert pipeline.conferir_contra(outra, periodos=["202601"]) == 0


def test_conferencia_denuncia_contagem_diferente(raiz, tmp_path):
    """
    A verificação que separa "mais rápido" de "produz outra coisa".
    """
    from hpc.config.paths import camadas

    mapa = camadas(criar=True)
    outra = tmp_path / "referencia"
    _parquet_com(mapa["primary"] / "202601" / "rlEstabEquipamento.parquet", 1_000)
    _parquet_com(outra / "202601" / "rlEstabEquipamento.parquet", 999)
    assert pipeline.conferir_contra(outra, periodos=["202601"]) == 1


def test_conferencia_denuncia_tabela_faltando(raiz, tmp_path):
    from hpc.config.paths import camadas

    mapa = camadas(criar=True)
    outra = tmp_path / "referencia"
    _parquet_com(mapa["primary"] / "202601" / "rlEstabEquipamento.parquet", 10)
    (outra / "202601").mkdir(parents=True)
    assert pipeline.conferir_contra(outra, periodos=["202601"]) == 1
