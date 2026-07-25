"""
Orquestrador do ETL, competência por competência.

Existe por uma razão material: rodar os estágios em série sobre a série inteira
não cabe em disco. Cada ZIP descompacta para cerca de 1,5 GB de CSV, e o DuckDB
intermediário fica na mesma ordem de grandeza — nove competências pedem algo
como 15 a 20 GB só de camada 02, que é descartável.

A camada que interessa guardar é a 03_primary: só as colunas declaradas em
docs/01-selecao-tabelas.md, tipadas e comprimidas, uma ordem de grandeza menor.

Então o fluxo aqui é, para cada competência: carrega o DuckDB, converte para
Parquet, e **apaga o DuckDB**. O pico de disco passa a ser uma competência em
vez de nove. Com `--manter-intermediario` o comportamento antigo volta, útil
quando se quer consultar o DuckDB direto numa análise exploratória.

Uso:
    python -m src.pipeline                      # série canônica completa
    python -m src.pipeline --periodos 202401 202501
    python -m src.pipeline --manter-intermediario
    python -m src.pipeline --pular-download     # se os ZIP já estão em disco
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from src.extract import PERIODOS_ANUAIS, download_cnes_zips
from src.paths import (
    CHANGES_FOLDER,
    INTERMEDIATE_FOLDER,
    PRIMARY_FOLDER,
    RAW_FOLDER,
)
from src.to_parquet import clean_cnes_data
from src.to_sql import process_cnes_zip

# Margem mínima de disco antes de começar uma competência. Abaixo disso, para
# com mensagem clara em vez de morrer no meio de uma escrita.
MARGEM_DISCO_GB = 6.0


def espaco_livre_gb(caminho: Path) -> float:
    return shutil.disk_usage(caminho).free / 1024**3


def _parquets_de(periodo: str) -> int:
    pasta = PRIMARY_FOLDER / periodo
    return len(list(pasta.glob("*.parquet"))) if pasta.exists() else 0


def rodar(
    periodos: list[str] | None = None,
    pular_download: bool = False,
    manter_intermediario: bool = False,
    reprocess: bool = False,
) -> dict[str, int]:
    """
    Roda o ETL até a camada primária, uma competência por vez.

    Devolve {competência: número de Parquet gerados}. Uma competência que já
    tenha Parquet é pulada quando `reprocess=False`, o que torna a execução
    retomável — importante porque a série inteira leva bastante tempo.
    """
    periodos = periodos or PERIODOS_ANUAIS
    PRIMARY_FOLDER.mkdir(parents=True, exist_ok=True)
    INTERMEDIATE_FOLDER.mkdir(parents=True, exist_ok=True)

    resultado: dict[str, int] = {}

    for periodo in periodos:
        if not reprocess and _parquets_de(periodo):
            print(f"[{periodo}] já convertida ({_parquets_de(periodo)} Parquet). Pulando.")
            resultado[periodo] = _parquets_de(periodo)
            continue

        livre = espaco_livre_gb(PRIMARY_FOLDER)
        if livre < MARGEM_DISCO_GB:
            raise RuntimeError(
                f"apenas {livre:.1f} GB livres, abaixo da margem de "
                f"{MARGEM_DISCO_GB} GB. Uma competência precisa de espaço para o "
                f"DuckDB intermediário. Libere espaço ou remova ZIP já "
                f"convertidos de {RAW_FOLDER}."
            )

        print(f"\n{'=' * 70}\n[{periodo}] iniciando. {livre:.1f} GB livres.\n{'=' * 70}")

        if not pular_download:
            download_cnes_zips([periodo], reprocess=False)

        zip_esperado = RAW_FOLDER / f"BASE_DE_DADOS_CNES_{periodo}.ZIP"
        if not zip_esperado.exists():
            print(f"[{periodo}] ZIP ausente. Pulando.")
            continue

        duckdb_path = INTERMEDIATE_FOLDER / f"sql_cnes_{periodo}.duckdb"
        try:
            process_cnes_zip([periodo], reprocess=reprocess)
            clean_cnes_data([periodo], reprocess=reprocess)
            resultado[periodo] = _parquets_de(periodo)
            print(f"[{periodo}] {resultado[periodo]} Parquet em {PRIMARY_FOLDER / periodo}")
        finally:
            # Sempre limpa, mesmo se a conversão falhou: um DuckDB parcial de
            # vários GB não serve para nada e ocupa o espaço da competência
            # seguinte.
            if not manter_intermediario and duckdb_path.exists():
                tamanho = duckdb_path.stat().st_size / 1024**3
                duckdb_path.unlink()
                print(f"[{periodo}] intermediário removido ({tamanho:.1f} GB liberados)")

    return resultado


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--periodos", nargs="*", help="competências YYYYMM")
    ap.add_argument("--pular-download", action="store_true")
    ap.add_argument(
        "--manter-intermediario",
        action="store_true",
        help="não apaga o DuckDB após converter (usa muito mais disco)",
    )
    ap.add_argument("--reprocess", action="store_true")
    ap.add_argument(
        "--sem-mudancas",
        action="store_true",
        help="não roda a detecção de mudança ao final",
    )
    args = ap.parse_args()

    resultado = rodar(
        periodos=args.periodos,
        pular_download=args.pular_download,
        manter_intermediario=args.manter_intermediario,
        reprocess=args.reprocess,
    )

    print(f"\n{'=' * 70}\nCamada primária:")
    for periodo, n in sorted(resultado.items()):
        print(f"  {periodo}: {n} tabelas")

    if args.sem_mudancas or len(resultado) < 2:
        return 0

    # Importado aqui para que a etapa anterior não pague o custo do import.
    from src.changes import detectar_mudancas, taxa_de_mudanca

    print(f"\n{'=' * 70}\nDetectando mudanças entre competências consecutivas...")
    detectar_mudancas(periodos=sorted(resultado), reprocess=args.reprocess)
    print(f"Eventos em {CHANGES_FOLDER}")

    df = taxa_de_mudanca()
    print("\nMaiores taxas de mudança:")
    print(
        df.nlargest(15, "taxa_mudanca")[
            ["tabela", "periodo_destino", "eventos", "taxa_mudanca", "chave_declarada"]
        ].to_string(index=False)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
