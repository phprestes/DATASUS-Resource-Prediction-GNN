"""
Tabela de tarefa do servidor: a mesma definição, sem subamostrar o treino.

A definição do rótulo é a de `src.ml.tasks` e não muda — mudá-la tornaria as
metades da matriz incomparáveis. O que muda é o que a máquina permite:

| | notebook (9 GB) | servidor (440 GB) |
|---|---|---|
| Negativos de treino | 200 por positivo | **todos** |
| Escopo | estado de São Paulo | **país** |
| Pares, série de dez snapshots | 40,8 M | **375 M** |
| Teto do DuckDB | 2 GB | um quinto da RAM |

`negativos_por_positivo=None` é o default aqui, e o custo é conhecido: 375 milhões
de linhas contra 40,8 milhões, ou cerca de 3,2 GB com a codificação categórica
compartilhada de D-23. A compactação continua valendo — ela não custa informação,
só evita materializar `co_unidade` como string.

No modo compatível, a subamostragem de 200:1 volta, porque replicar a limitação é
justamente o ponto daquele modo.
"""

from __future__ import annotations

from pathlib import Path

from hpc.config.ambiente import exigir_memoria, perfil_maquina
from hpc.config.paths import primary_folder
from src.ml.splits import ParticaoTemporal
from src.ml.tasks import COL_EQUIPAMENTO, TABELA_EQUIPAMENTO, TabelaTarefa
from src.ml.tasks import tarefa_aquisicao as _tarefa_aquisicao_local

# RAM mínima para construir a tabela aqui. Medido por extrapolação: 375 M linhas
# na codificação compacta são ~3,2 GB, e o pico de construção é da ordem de dez
# vezes isso entre o DuckDB e o pandas.
RAM_MINIMA_GB = 64.0


def teto_duckdb() -> str:
    """Um quinto da RAM, com piso de 4 GB. Ver `tarefa_aquisicao`."""
    ram = perfil_maquina().ram_gb
    if ram != ram:  # NaN: /proc/meminfo indisponível
        ram = 16.0
    return f"{max(4, int(ram // 5))}GB"


def tarefa_aquisicao(
    particao: ParticaoTemporal,
    recorte: str | None = None,
    modo: str = "completo",
    tabela: str = TABELA_EQUIPAMENTO,
    col_item: str = COL_EQUIPAMENTO,
    pasta: Path | None = None,
    semente: int = 42,
    permitir_maquina_pequena: bool = False,
) -> TabelaTarefa:
    """
    Monta a tarefa na raiz do servidor.

    Args:
        particao: partição temporal, a mesma dos dois pipelines.
        recorte: prefixo de código IBGE. `None` é o país inteiro, que é o ponto
            de rodar aqui.
        modo: `"completo"` usa todos os negativos; `"compativel"` restaura os
            200 por positivo do notebook, para a célula que mantém a técnica
            constante (D-34).
        tabela: tabela de fato do alvo.
        col_item: coluna do item.
        pasta: camada primária. `None` usa a raiz do servidor.
        semente: semente da subamostragem, quando houver.
        permitir_maquina_pequena: ignora a guarda de RAM. Só para dado sintético.

    Returns:
        `TabelaTarefa` no mesmo formato do pipeline local — a definição do rótulo
        é a de `src.ml.tasks` e não muda, senão as metades da matriz ficam
        incomparáveis.

    Raises:
        ValueError: `modo` fora de `compativel` e `completo`.
        RuntimeError: máquina com menos de 64 GB de RAM.
    """
    if modo not in ("compativel", "completo"):
        raise ValueError(f"modo deve ser 'compativel' ou 'completo'; recebido {modo!r}")

    exigir_memoria(
        RAM_MINIMA_GB,
        f"a tabela de tarefa do servidor (recorte {recorte or 'nacional'})",
        permitir_maquina_pequena=permitir_maquina_pequena,
    )

    negativos = 200 if modo == "compativel" else None
    return _tarefa_aquisicao_local(
        particao,
        tabela=tabela,
        col_item=col_item,
        recorte=recorte,
        pasta=pasta or primary_folder(),
        negativos_por_positivo=negativos,
        semente=semente,
        limite_duckdb=teto_duckdb(),
    )
