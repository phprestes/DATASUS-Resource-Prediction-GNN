"""
Driver da bateria completa: todo pipeline, todo escopo, as duas variantes.

Um único comando produz o conjunto de resultados do artigo. Cada execução é um
subprocesso independente, o que torna a bateria **retomável**: uma queda perde a
execução em curso e não as anteriores, e relançar pula o que já tem resultado.

    python -m hpc.roda_tudo --seco            # imprime o plano, não roda nada
    python -m hpc.roda_tudo                   # a bateria inteira
    python -m hpc.roda_tudo --so hpc          # só o pipeline do servidor
    python -m hpc.roda_tudo --sementes 3      # com banda de ruído

O desenho da bateria e o que cada eixo isola estão em `docs/06-pipeline-hpc.md`.
"""

from __future__ import annotations

import argparse
import itertools
import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from src.config.paths import DOCS_DIR

PASTA_RESULTADOS = DOCS_DIR / "resultados"

# Escopos, do mais estreito ao mais largo. O recorte é um prefixo de código IBGE
# e a hierarquia do código faz o resto: `'355030'` é a capital, `'35'` o estado,
# vazio o país. Não há caso especial — município é apenas o prefixo completo.
ESCOPOS = {
    "capital": "355030",
    "estado": "35",
    "pais": "",
}

# `compativel` replica as quatro limitações da máquina de 9 GB em qualquer
# escopo; `completo` as levanta. Ver D-34. O pipeline `src` não tem esse eixo:
# ele *é* a técnica limitada.
MODOS = ("compativel", "completo")

VARIANTES = {
    "com-pandemia": False,
    "sem-pandemia": True,
}


@dataclass(frozen=True)
class Execucao:
    """Uma célula da bateria, e o comando que a produz."""

    pipeline: str
    escopo: str
    modo: str
    variante: str
    semente: int

    @property
    def recorte(self) -> str:
        """
        Returns:
            Prefixo de código IBGE do escopo. String vazia para o país, que é o
            que os orquestradores interpretam como "sem recorte".
        """
        return ESCOPOS[self.escopo]

    @property
    def rotulo(self) -> str:
        """Identificador legível, usado em log e no manifesto."""
        return (
            f"{self.pipeline}/{self.escopo}/{self.modo}/{self.variante}"
            f"/s{self.semente}"
        )

    @property
    def saida(self) -> Path:
        """
        Onde o resultado desta célula é gravado.

        Precisa casar exatamente com o nome que o orquestrador escolhe, senão a
        retomada não reconhece o que já rodou e a bateria refaz tudo.
        """
        nome_escopo = self.recorte or "pais"
        if self.pipeline == "src":
            base = f"{date.today()}-trilhas-{nome_escopo}"
        else:
            base = f"{date.today()}-hpc-{nome_escopo}-{self.modo}"
        return PASTA_RESULTADOS / f"{base}-{self.variante}-s{self.semente}.json"

    def comando(self, epocas: int, pasta_primaria: Path | None) -> list[str]:
        """
        Linha de comando completa desta execução.

        Args:
            epocas: teto de épocas de treino, repassado ao orquestrador.
            pasta_primaria: camada primária a usar. `None` deixa cada pipeline
                escolher o seu default — o que só é correto fora do cluster.

        Returns:
            Argumentos prontos para `subprocess.run`.
        """
        comum = [
            sys.executable, "-m",
            "tools.roda_experimento" if self.pipeline == "src" else "hpc.ml.experimento",
            "--recorte", self.recorte,
            "--epocas", str(epocas),
            "--semente", str(self.semente),
        ]
        if VARIANTES[self.variante]:
            comum.append("--excluir-pandemia")
        if pasta_primaria is not None:
            comum += ["--pasta-primaria", str(pasta_primaria)]
        if self.pipeline == "hpc":
            comum += ["--modo", self.modo, "--reusar-grafos"]
        return comum


def planejar(
    pipelines: tuple[str, ...],
    escopos: tuple[str, ...],
    sementes: int,
) -> list[Execucao]:
    """
    Enumera as células da bateria, na ordem em que devem rodar.

    A ordem é deliberada: escopo crescente, e dentro dele semente crescente. Uma
    bateria interrompida terá terminado os escopos baratos, que é onde erro de
    configuração aparece primeiro — descobrir que o recorte está errado depois de
    seis horas no país é o desperdício que esta ordem evita.

    Repetição por semente mede variação de inicialização. A fonte dominante de
    irreprodutibilidade era outra e foi corrigida — a tabela de tarefa saía do
    DuckDB em ordem arbitrária e o minilote é sorteado por índice (D-43) —, mas o
    que resta só se quantifica repetindo: sem banda medida, diferença entre células
    não é interpretável (D-44).

    Args:
        pipelines: quais pipelines incluir, entre `"src"` e `"hpc"`.
        escopos: nomes de `ESCOPOS`, do mais estreito ao mais largo.
        sementes: quantas repetições por célula. 1 desliga a banda de ruído.

    Returns:
        Execuções na ordem de lançamento, sem duplicatas.
    """
    plano: list[Execucao] = []
    for escopo, semente_i in itertools.product(escopos, range(sementes)):
        semente = 42 + semente_i
        for variante in VARIANTES:
            if "src" in pipelines:
                # O pipeline local não tem eixo de modo: ele é a técnica
                # limitada, e rotulá-lo `compativel` mantém o JSON comparável
                # com a célula equivalente do servidor.
                plano.append(
                    Execucao("src", escopo, "compativel", variante, semente)
                )
            if "hpc" in pipelines:
                for modo in MODOS:
                    plano.append(Execucao("hpc", escopo, modo, variante, semente))
    return plano


def rodar(execucao: Execucao, epocas: int, pasta_primaria: Path | None) -> dict:
    """
    Executa uma célula e devolve o registro dela para o manifesto.

    Args:
        execucao: célula a rodar.
        epocas: teto de épocas, repassado ao orquestrador.
        pasta_primaria: camada primária, ou `None` para o default do pipeline.

    Returns:
        Registro com rótulo, situação (`"pulada"`, `"ok"` ou `"falhou"`), código
        de saída, duração em segundos e caminho do resultado.
    """
    if execucao.saida.exists():
        print(f"  já existe, pulando: {execucao.saida.name}", flush=True)
        return {**asdict(execucao), "situacao": "pulada", "segundos": 0}

    comando = execucao.comando(epocas, pasta_primaria)
    print(f"  $ {' '.join(comando)}", flush=True)
    t0 = time.time()
    concluido = subprocess.run(comando)
    segundos = round(time.time() - t0)
    situacao = "ok" if concluido.returncode == 0 else "falhou"
    print(f"  {situacao} em {segundos}s", flush=True)
    return {
        **asdict(execucao),
        "situacao": situacao,
        "codigo_saida": concluido.returncode,
        "segundos": segundos,
        "resultado": execucao.saida.name if situacao == "ok" else None,
    }


def main() -> int:
    """
    Entrada de linha de comando da bateria completa.

    Returns:
        0 se toda célula terminou bem, 1 se alguma falhou. O código de saída
        distingue "bateria completa" de "bateria com buraco", que importa quando
        ela roda desacompanhada sob `screen`.
    """
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--so", choices=["src", "hpc", "ambos"], default="ambos",
                    help="restringe o eixo de pipeline")
    ap.add_argument("--escopos", nargs="+", choices=list(ESCOPOS), default=list(ESCOPOS),
                    help="quais recortes espaciais rodar")
    ap.add_argument("--sementes", type=int, default=1,
                    help="repetições por célula; >1 mede a banda de ruído")
    ap.add_argument("--epocas", type=int, default=150)
    ap.add_argument("--pasta-primaria", type=Path, default=None,
                    help="camada primária; no cluster, $IC_HPC_DATA/03_primary")
    ap.add_argument("--seco", action="store_true",
                    help="imprime o plano e sai, sem rodar nada")
    ap.add_argument("--continuar-apos-falha", action="store_true", default=True,
                    help="mantém a bateria de pé quando uma célula falha (padrão)")
    args = ap.parse_args()

    pipelines = ("src", "hpc") if args.so == "ambos" else (args.so,)
    plano = planejar(pipelines, tuple(args.escopos), args.sementes)

    print(f"{len(plano)} execuções planejadas\n")
    for i, e in enumerate(plano, 1):
        marca = "·" if not e.saida.exists() else "✓"
        print(f"  {marca} {i:>3}. {e.rotulo}")
    print()

    if args.seco:
        print("--seco: nada foi executado")
        return 0

    PASTA_RESULTADOS.mkdir(parents=True, exist_ok=True)
    manifesto = PASTA_RESULTADOS / f"{date.today()}-bateria.json"
    registros: list[dict] = []

    for i, execucao in enumerate(plano, 1):
        print(f"[{i}/{len(plano)}] {execucao.rotulo}", flush=True)
        registro = rodar(execucao, args.epocas, args.pasta_primaria)
        registros.append(registro)
        # Gravação incremental: uma queda preserva o que já foi medido.
        manifesto.write_text(
            json.dumps(
                {"data": str(date.today()), "execucoes": registros},
                indent=2, ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        if registro["situacao"] == "falhou" and not args.continuar_apos_falha:
            print("interrompendo por falha", flush=True)
            break

    falhas = [r for r in registros if r["situacao"] == "falhou"]
    ok = [r for r in registros if r["situacao"] == "ok"]
    print(f"\n{'=' * 70}")
    print(f"{len(ok)} ok · {len(falhas)} falharam · manifesto em {manifesto}")
    for r in falhas:
        print(f"  falhou: {r['pipeline']}/{r['escopo']}/{r['modo']}/{r['variante']}")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
