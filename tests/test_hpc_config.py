"""
Testes das guardas do pipeline do servidor.

Rodam em CPU, nesta máquina, e são o que impede os dois pipelines de se
atropelarem: raiz de dados separada, recusa explícita de rodar sem GPU, e perfil
de máquina sempre disponível para o manifesto. Ver D-34.
"""

from __future__ import annotations

import pytest

from hpc.config import ambiente
from hpc.config.paths import ErroConfiguracao, camadas, raiz_de_dados
from src.config.paths import BASE_DIR


def test_raiz_fora_do_repositorio_e_aceita(tmp_path, monkeypatch):
    monkeypatch.setenv("IC_HPC_DATA", str(tmp_path / "ic"))
    assert raiz_de_dados() == (tmp_path / "ic").resolve()


def test_raiz_dentro_do_repositorio_e_recusada(monkeypatch):
    """
    A guarda central do isolamento.

    Se a raiz do servidor apontasse para `data/`, uma execução no cluster
    sobrescreveria a camada primária desta máquina, e a comparação entre as duas
    metades da matriz de D-34 passaria a comparar dado com ele mesmo.
    """
    monkeypatch.setenv("IC_HPC_DATA", str(BASE_DIR / "data"))
    with pytest.raises(ErroConfiguracao, match="dentro do repositório"):
        raiz_de_dados()


def test_raiz_igual_ao_repositorio_e_recusada(monkeypatch):
    monkeypatch.setenv("IC_HPC_DATA", str(BASE_DIR))
    with pytest.raises(ErroConfiguracao, match="dentro do repositório"):
        raiz_de_dados()


def test_camadas_seguem_a_convencao_numerada(tmp_path, monkeypatch):
    """
    A estrutura precisa espelhar a de src/config/paths.py, para que um rsync de
    uma camada entre as duas máquinas continue fazendo sentido.
    """
    monkeypatch.setenv("IC_HPC_DATA", str(tmp_path / "ic"))
    mapa = camadas(criar=True)
    assert mapa["raw"].name == "01_raw"
    assert mapa["intermediate"].name == "02_intermediate"
    assert mapa["primary"].name == "03_primary"
    assert mapa["feature"].name == "04_feature"
    assert mapa["grafos"].name == "05_grafos"
    assert all(p.exists() for p in mapa.values())


def test_camadas_nao_criam_sem_pedido(tmp_path, monkeypatch):
    monkeypatch.setenv("IC_HPC_DATA", str(tmp_path / "novo"))
    mapa = camadas(criar=False)
    assert not any(p.exists() for p in mapa.values())


def test_exigir_cuda_recusa_cpu_por_padrao(monkeypatch):
    """
    Sem escalonador para recusar um job mal dimensionado, a recusa mora no
    programa: cair em CPU em silêncio daria uma execução de dias e um número que
    pareceria comparável ao do servidor.
    """
    monkeypatch.setattr(
        ambiente, "perfil_maquina", lambda: _perfil_falso(cuda=False)
    )
    with pytest.raises(ambiente.ErroAmbiente, match="permitir-cpu"):
        ambiente.exigir_cuda()
    assert ambiente.exigir_cuda(permitir_cpu=True) == "cpu"


def test_exigir_cuda_aceita_gpu(monkeypatch):
    monkeypatch.setattr(ambiente, "perfil_maquina", lambda: _perfil_falso(cuda=True))
    assert ambiente.exigir_cuda() == "cuda"


def test_exigir_memoria_recusa_maquina_pequena(monkeypatch):
    monkeypatch.setattr(
        ambiente, "perfil_maquina", lambda: _perfil_falso(cuda=True, ram=9.0)
    )
    with pytest.raises(ambiente.ErroAmbiente, match="ao menos"):
        ambiente.exigir_memoria(64, "a tarefa nacional")
    ambiente.exigir_memoria(4, "algo pequeno")


def test_perfil_sempre_responde():
    """O perfil vai para o manifesto do modelo; não pode levantar."""
    perfil = ambiente.perfil_maquina()
    assert perfil.host
    assert perfil.cpus >= 1
    assert isinstance(perfil.cuda_disponivel, bool)
    assert "host" in perfil.resumo()
    assert perfil.como_dict()["plataforma"]


def test_estimativa_de_batch_completo_usa_a_vram(monkeypatch):
    """
    A wiki do IME não documenta a VRAM das GPUs, então a escolha entre batch
    completo e amostragem de vizinhança é medida, não assumida.
    """
    monkeypatch.setattr(
        ambiente, "perfil_maquina", lambda: _perfil_falso(cuda=True, vram=48.0)
    )
    assert ambiente.cabe_em_batch_completo(arestas=30_000_000, nos=700_000)
    assert not ambiente.cabe_em_batch_completo(arestas=3_000_000_000, nos=700_000)

    monkeypatch.setattr(ambiente, "perfil_maquina", lambda: _perfil_falso(cuda=False))
    assert not ambiente.cabe_em_batch_completo(arestas=10, nos=10)


def _perfil_falso(cuda: bool, ram: float = 440.0, vram: float = 48.0):
    return ambiente.Perfil(
        host="brucutuvii-falso",
        plataforma="Linux-teste",
        cpus=32,
        ram_gb=ram,
        disco_livre_gb=1000.0,
        raiz_de_dados="/var/fasttmp/teste/ic",
        cuda_disponivel=cuda,
        versao_cuda="12.4" if cuda else None,
        gpus=(
            [ambiente.GPU(indice=0, nome="RTX A6000", vram_gb=vram, capacidade="8.6")]
            if cuda
            else []
        ),
    )
