"""
Camada 05: os grafos por transição, materializados uma vez.

Montar o grafo é o estágio mais caro da preparação — no recorte nacional são nove
grafos, cada um lendo dezenas de tabelas de fato —, e as quatro células da matriz
de D-34 reusam os mesmos grafos por escopo e modo. Materializar evita remontar a
cada execução.

Uso:
    python -m hpc.etl.grafo_store --recorte 35 --modo completo
    python -m hpc.etl.grafo_store --recorte "" --modo compativel   # país
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from hpc.config.paths import grafos_folder, primary_folder
from hpc.ml.grafo_temporal import (
    colunas_para_grafo_completo,
    montar,
    salvar,
    verificar_sem_vazamento,
)
from src.etl.changes import periodos_disponiveis, transicoes
from src.ml.graph import COL_ENTIDADE, TABELA_RAIZ, colunas_minimas_para_grafo, montar_db
from src.ml.splits import particionar


def nome_do_conjunto(recorte: str | None, modo: str) -> str:
    """Escopo e modo no nome: os grafos do modo compatível não são os do completo."""
    return f"{recorte or 'pais'}-{modo}"


def materializar(
    recorte: str | None,
    modo: str = "completo",
    pasta_primaria: Path | None = None,
    destino: Path | None = None,
    verboso: bool = True,
    permitir_maquina_pequena: bool = False,
) -> Path:
    pasta_primaria = pasta_primaria or primary_folder()
    destino = destino or grafos_folder(criar=True) / nome_do_conjunto(recorte, modo)

    periodos = periodos_disponiveis(pasta_primaria)
    particao = particionar(periodos)
    todas = transicoes(periodos)

    completo = modo == "completo"
    colunas = colunas_para_grafo_completo() if completo else colunas_minimas_para_grafo()
    if verboso:
        print(
            f"modo {modo} | {len(colunas)} tabelas | "
            f"{sum(len(v) for v in colunas.values())} colunas projetadas",
            flush=True,
        )

    t0 = time.time()
    db = montar_db(recorte=recorte, pasta=pasta_primaria, colunas=colunas)
    unidades = sorted(
        set(db.table_dict[TABELA_RAIZ].df[COL_ENTIDADE].to_pylist())
    )
    if verboso:
        print(
            f"Database em {time.time() - t0:.0f}s: {len(db.table_dict)} tabelas, "
            f"{len(unidades):,} estabelecimentos",
            flush=True,
        )

    if completo:
        grafos = montar(
            db, unidades, todas, com_atributos=True, min_arestas=0,
            permitir_maquina_pequena=permitir_maquina_pequena,
        )
    else:
        # No modo compatível o grafo é único e cortado antes de todos os rótulos,
        # como no notebook: é a limitação de D-25 sendo replicada de propósito.
        corte = particao.antes_de_todos_os_rotulos
        so_o_corte = [t for t in todas if t.origem == corte]
        grafos = montar(
            db, unidades, so_o_corte, com_atributos=False, min_arestas=100,
            permitir_maquina_pequena=permitir_maquina_pequena,
        )
        for transicao in todas:
            grafos.por_origem.setdefault(transicao.origem, grafos.por_origem[corte])

    if completo:
        verificar_sem_vazamento(grafos, todas)

    caminho = salvar(grafos, destino)
    if verboso:
        print(f"grafos em {caminho}", flush=True)
    return caminho


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--recorte", default="", help="prefixo IBGE; vazio = país")
    ap.add_argument("--modo", choices=["compativel", "completo"], default="completo")
    ap.add_argument("--pasta-primaria", type=Path, default=None)
    ap.add_argument("--destino", type=Path, default=None)
    ap.add_argument("--permitir-cpu", action="store_true",
                    help="aceito por simetria com o experimento; a montagem não usa GPU")
    ap.add_argument("--permitir-maquina-pequena", action="store_true",
                    help="ignora a guarda de RAM; só para dado sintético")
    args = ap.parse_args()

    materializar(
        recorte=args.recorte or None,
        modo=args.modo,
        pasta_primaria=args.pasta_primaria,
        destino=args.destino,
        permitir_maquina_pequena=args.permitir_maquina_pequena,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
