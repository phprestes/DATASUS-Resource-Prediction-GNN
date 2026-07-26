"""
ETL do servidor: as mesmas camadas, várias competências ao mesmo tempo.

O conteúdo produzido é idêntico ao do ETL do notebook, e isso é requisito, não
economia: os arquivos do CNES já são nacionais, o recorte espacial só age na
modelagem, e se as duas camadas primárias divergissem a matriz de D-34 estaria
comparando dado em vez de técnica. Por isso os estágios reutilizam
`src.etl.extract`, `src.etl.to_sql` e `src.etl.to_parquet`.

O que muda é como eles são chamados:

- **em paralelo**, uma competência por processo, contra 16 a 40 núcleos;
- **em SSD**, com raiz sob `/var/fasttmp` (`hpc/config/paths.py`);
- **com teto de memória por processo**, senão N DuckDB dimensionam o buffer pela
  RAM total e somam N vezes a máquina;
- **retomável**, porque o cluster não tem escalonador e mata processo com mais de
  168 h: competência já convertida é pulada.

Uso:
    python -m hpc.etl.pipeline                          # série canônica
    python -m hpc.etl.pipeline --periodos 202501 202601
    python -m hpc.etl.pipeline --pular-download         # ZIPs vindos por rsync
    python -m hpc.etl.pipeline --conferir-contra data/03_primary
"""

from __future__ import annotations

import argparse
import shutil
import time
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from hpc.config.ambiente import perfil_maquina
from hpc.config.paths import camadas
from src.config.schema import FACT_TABLES
from src.etl.extract import PERIODOS_ANUAIS, download_cnes_zips
from src.etl.to_parquet import clean_cnes_data
from src.etl.to_sql import process_cnes_zip

# Cada competência precisa de espaço para o ZIP (~0,7 GB), os CSV descompactados
# um a um (~1,5 GB de pico) e o DuckDB intermediário (~4 GB). Com folga, 8 GB por
# processo simultâneo.
DISCO_POR_PROCESSO_GB = 8.0


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _parquets_de(periodo: str, primary: Path) -> int:
    pasta = primary / periodo
    return len(list(pasta.glob("*.parquet"))) if pasta.exists() else 0


def _uma_competencia(
    periodo: str,
    reprocess: bool,
    manter_intermediario: bool,
    limite_memoria: str,
) -> tuple[str, int, str]:
    """
    Ingestão e conversão de uma competência. Roda em processo próprio.

    Devolve `(periodo, n_parquet, observacao)`. Não levanta: uma competência que
    falha não deve derrubar as outras oito, e o relatório final mostra quem ficou
    de fora.
    """
    mapa = camadas(criar=True)
    temp = mapa["temp"] / periodo
    duckdb_path = mapa["intermediate"] / f"sql_cnes_{periodo}.duckdb"
    try:
        zip_esperado = mapa["raw"] / f"BASE_DE_DADOS_CNES_{periodo}.ZIP"
        if not zip_esperado.exists():
            return periodo, 0, "ZIP ausente"
        if not zipfile.is_zipfile(zip_esperado):
            return periodo, 0, "ZIP inválido ou truncado"

        process_cnes_zip(
            [periodo],
            input_folder=mapa["raw"],
            output_folder=mapa["intermediate"],
            reprocess=reprocess,
            temp_folder=temp,
            limite_memoria=limite_memoria,
        )
        clean_cnes_data(
            [periodo],
            input_folder=mapa["intermediate"],
            output_folder=mapa["primary"],
            reprocess=reprocess,
        )
        n = _parquets_de(periodo, mapa["primary"])
        obs = "ok" if n == len(FACT_TABLES) else f"apenas {n} de {len(FACT_TABLES)} tabelas"
        return periodo, n, obs
    except Exception as erro:  # noqa: BLE001 — ver a docstring
        return periodo, 0, f"falhou: {type(erro).__name__}: {erro}"
    finally:
        if temp.exists():
            shutil.rmtree(temp, ignore_errors=True)
        if not manter_intermediario and duckdb_path.exists():
            duckdb_path.unlink()
            Path(f"{duckdb_path}.wal").unlink(missing_ok=True)


def rodar(
    periodos: list[str] | None = None,
    pular_download: bool = False,
    reprocess: bool = False,
    trabalhadores: int | None = None,
    manter_intermediario: bool = False,
    limite_memoria_por_processo: str | None = None,
) -> dict[str, int]:
    """
    Produz a camada primária na raiz do servidor. Devolve {competência: n_parquet}.

    O download fica **em série** de propósito: é limitado pela rede e pelo
    servidor do DATASUS, e paralelizá-lo só multiplicaria timeouts. A ingestão,
    que é limitada por CPU e disco, é o que vai em paralelo.
    """
    periodos = periodos or list(PERIODOS_ANUAIS)
    mapa = camadas(criar=True)
    perfil = perfil_maquina()

    livre = shutil.disk_usage(mapa["raw"]).free / 1024**3
    teto_por_disco = max(1, int(livre // DISCO_POR_PROCESSO_GB))
    trabalhadores = trabalhadores or min(
        4, max(1, (perfil.cpus or 4) // 4), teto_por_disco
    )
    # Um quinto da RAM por processo, com piso de 4 GB: o suficiente para o DuckDB
    # derramar para disco em vez de disputar memória com os vizinhos.
    limite = limite_memoria_por_processo or (
        f"{max(4, int((perfil.ram_gb if perfil.ram_gb == perfil.ram_gb else 16) // 5))}GB"
    )

    log(f"host {perfil.host} | {perfil.cpus} cpus | {perfil.ram_gb:.0f} GB de RAM")
    log(f"raiz de dados {mapa['primary'].parent} | {livre:.0f} GB livres")
    log(
        f"{len(periodos)} competências | {trabalhadores} processos | "
        f"teto de {limite} por processo"
    )

    pendentes = [
        p for p in periodos if reprocess or _parquets_de(p, mapa["primary"]) == 0
    ]
    prontas = {
        p: _parquets_de(p, mapa["primary"]) for p in periodos if p not in pendentes
    }
    for periodo, n in prontas.items():
        log(f"[{periodo}] já convertida ({n} Parquet). Pulando.")
    if not pendentes:
        return prontas

    if not pular_download:
        log(f"baixando {len(pendentes)} ZIP em série (limitado pela rede)")
        download_cnes_zips(pendentes, output_folder=mapa["raw"], reprocess=False)

    resultado = dict(prontas)
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=trabalhadores) as executor:
        futuros = {
            executor.submit(
                _uma_competencia, p, reprocess, manter_intermediario, limite
            ): p
            for p in pendentes
        }
        for futuro in as_completed(futuros):
            periodo, n, obs = futuro.result()
            resultado[periodo] = n
            log(f"[{periodo}] {obs} ({n} Parquet)")

    log(f"camada primária pronta em {time.time() - t0:.0f}s")
    return resultado


def conferir_contra(outra_primaria: Path, periodos: list[str] | None = None) -> int:
    """
    Compara a contagem de linhas com outra camada primária, tabela por tabela.

    É a verificação que separa "o ETL do servidor é mais rápido" de "o ETL do
    servidor produz outra coisa". Divergência aqui invalida a comparação entre as
    metades da matriz de D-34, então vale rodar uma vez depois do primeiro ETL.
    """
    import duckdb

    mapa = camadas()
    periodos = periodos or sorted(p.name for p in mapa["primary"].iterdir() if p.is_dir())
    con = duckdb.connect()
    con.execute("SET memory_limit='2GB'")
    divergencias = 0

    for periodo in periodos:
        aqui, la = mapa["primary"] / periodo, Path(outra_primaria) / periodo
        if not la.exists():
            log(f"[{periodo}] ausente em {outra_primaria}, pulando")
            continue
        for tabela in sorted(FACT_TABLES):
            a, b = aqui / f"{tabela}.parquet", la / f"{tabela}.parquet"
            if not a.exists() and not b.exists():
                continue
            if not a.exists() or not b.exists():
                log(f"[{periodo}] {tabela}: existe em apenas um dos lados")
                divergencias += 1
                continue
            na = con.execute(f"SELECT COUNT(*) FROM read_parquet('{a}')").fetchone()[0]
            nb = con.execute(f"SELECT COUNT(*) FROM read_parquet('{b}')").fetchone()[0]
            if na != nb:
                log(f"[{periodo}] {tabela}: {na:,} aqui contra {nb:,} lá")
                divergencias += 1

    log(
        "camadas idênticas em contagem de linhas"
        if not divergencias
        else f"{divergencias} divergências — o ETL do servidor não reproduz o outro"
    )
    return divergencias


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--periodos", nargs="*", help="competências YYYYMM")
    ap.add_argument("--pular-download", action="store_true",
                    help="usa ZIPs já presentes; para nó sem internet")
    ap.add_argument("--reprocess", action="store_true")
    ap.add_argument("--trabalhadores", type=int, default=None)
    ap.add_argument("--manter-intermediario", action="store_true")
    ap.add_argument("--limite-memoria", default=None,
                    help="teto do DuckDB por processo, ex: 32GB")
    ap.add_argument("--conferir-contra", type=Path, default=None,
                    help="camada primária de referência para comparar contagens")
    args = ap.parse_args()

    resultado = rodar(
        periodos=args.periodos,
        pular_download=args.pular_download,
        reprocess=args.reprocess,
        trabalhadores=args.trabalhadores,
        manter_intermediario=args.manter_intermediario,
        limite_memoria_por_processo=args.limite_memoria,
    )

    print(f"\n{'=' * 70}\nCamada primária:")
    for periodo, n in sorted(resultado.items()):
        print(f"  {periodo}: {n} tabelas")

    if args.conferir_contra:
        print(f"\n{'=' * 70}\nConferindo contra {args.conferir_contra}")
        return 1 if conferir_contra(args.conferir_contra) else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
