"""
Camadas de dados do pipeline do servidor, sob uma raiz própria.

A raiz sai de `IC_HPC_DATA`. O default é `/var/fasttmp/$USER/ic`, que é o SSD
recomendado pela wiki do IME para dado temporário — a camada intermediária do
recorte nacional é o estágio mais pesado do ETL e é justamente o que mais se
beneficia de disco rápido.

**Por que a raiz não pode cair dentro do repositório.** Os dois pipelines existem
para rodar em máquinas diferentes sem interferir. Se a raiz do servidor apontasse
para `data/`, uma execução no cluster sobrescreveria a camada primária do
notebook, e a comparação entre as duas metades da matriz (D-34) passaria a
comparar dado com ele mesmo. `raiz_de_dados()` recusa esse caminho.

A estrutura numerada é a mesma de `src/config/paths.py` de propósito: um `rsync`
de uma camada entre as duas máquinas continua fazendo sentido.
"""

from __future__ import annotations

import os
from pathlib import Path

from src.config.paths import BASE_DIR, MODELS_DIR, SELECAO_TABELAS  # noqa: F401

VARIAVEL_RAIZ = "IC_HPC_DATA"


class ErroConfiguracao(RuntimeError):
    """Raiz de dados ausente, inválida ou colidindo com a do repositório."""


def _default() -> Path:
    usuario = os.environ.get("USER") or os.environ.get("LOGNAME") or "ic"
    return Path("/var/fasttmp") / usuario / "ic"


def raiz_de_dados(criar: bool = False) -> Path:
    """
    Raiz das camadas de dados do servidor.

    `criar=True` materializa o diretório — use nos estágios que escrevem, não em
    quem só consulta o caminho.
    """
    bruta = os.environ.get(VARIAVEL_RAIZ)
    raiz = Path(bruta).expanduser().resolve() if bruta else _default()

    dentro_do_repo = raiz == BASE_DIR or BASE_DIR in raiz.parents
    if dentro_do_repo:
        raise ErroConfiguracao(
            f"{VARIAVEL_RAIZ}={raiz} está dentro do repositório ({BASE_DIR}). "
            "Os dois pipelines precisam de camadas separadas: apontar o do "
            "servidor para data/ sobrescreveria a camada primária desta máquina e "
            "invalidaria a comparação entre eles (D-34). Escolha um caminho fora "
            "do repositório, como /var/fasttmp/$USER/ic."
        )

    if criar:
        raiz.mkdir(parents=True, exist_ok=True)
    return raiz


def camadas(criar: bool = False) -> dict[str, Path]:
    """As quatro camadas mais o diretório de descompactação e o de grafos."""
    raiz = raiz_de_dados(criar=criar)
    mapa = {
        "raw": raiz / "01_raw",
        "intermediate": raiz / "02_intermediate",
        "primary": raiz / "03_primary",
        "feature": raiz / "04_feature",
        "grafos": raiz / "05_grafos",
        "temp": raiz / "temp_extract",
    }
    if criar:
        for caminho in mapa.values():
            caminho.mkdir(parents=True, exist_ok=True)
    return mapa


# Açúcar para quem só precisa de um caminho, no formato do resto do projeto.
def raw_folder(criar: bool = False) -> Path:
    return camadas(criar)["raw"]


def intermediate_folder(criar: bool = False) -> Path:
    return camadas(criar)["intermediate"]


def primary_folder(criar: bool = False) -> Path:
    return camadas(criar)["primary"]


def feature_folder(criar: bool = False) -> Path:
    return camadas(criar)["feature"]


def grafos_folder(criar: bool = False) -> Path:
    """
    Tensores de grafo por transição, materializados uma vez (`hpc/etl/grafo_store`).

    É camada derivada e descartável, mas caro de recomputar: no recorte nacional
    são nove grafos, e remontá-los a cada execução dominaria o tempo de treino.
    """
    return camadas(criar)["grafos"]


def temp_folder(criar: bool = False) -> Path:
    return camadas(criar)["temp"]
