"""
Detecção de hardware, guardas de execução e procedência da máquina.

Existe por três razões práticas, todas vindas do ambiente real do cluster do IME
(`brucutu`, `brucutuvi`, `brucutuvii`):

1. **A wiki não documenta VRAM.** O código não pode assumir 48 GB: ele mede em
   tempo de execução e decide se o encoder cabe em batch completo.
2. **Não há escalonador.** Sem SLURM para recusar um job mal dimensionado, a
   recusa tem de estar no programa — daí `exigir_cuda()`.
3. **O número medido depende da máquina.** `perfil_maquina()` entra no manifesto
   do modelo, para que uma métrica venha acompanhada de onde foi produzida.
"""

from __future__ import annotations

import os
import platform
import shutil
import socket
from dataclasses import asdict, dataclass, field

from hpc.config.paths import raiz_de_dados


class ErroAmbiente(RuntimeError):
    """Ambiente inadequado para a execução pedida."""


@dataclass
class GPU:
    indice: int
    nome: str
    vram_gb: float
    capacidade: str


@dataclass
class Perfil:
    """Retrato da máquina, para o manifesto do modelo."""

    host: str
    plataforma: str
    cpus: int
    ram_gb: float
    disco_livre_gb: float
    raiz_de_dados: str
    cuda_disponivel: bool
    versao_cuda: str | None = None
    gpus: list[GPU] = field(default_factory=list)

    @property
    def vram_total_gb(self) -> float:
        return round(sum(g.vram_gb for g in self.gpus), 1)

    def como_dict(self) -> dict:
        return asdict(self)

    def resumo(self) -> str:
        linhas = [
            f"host          {self.host}",
            f"plataforma    {self.plataforma}",
            f"cpus          {self.cpus}",
            f"ram           {self.ram_gb:.0f} GB",
            f"raiz de dados {self.raiz_de_dados}",
            f"disco livre   {self.disco_livre_gb:.0f} GB",
        ]
        if self.gpus:
            linhas.append(f"cuda          {self.versao_cuda}")
            for g in self.gpus:
                linhas.append(
                    f"gpu {g.indice}         {g.nome} — {g.vram_gb:.0f} GB "
                    f"(capacidade {g.capacidade})"
                )
        else:
            linhas.append("cuda          indisponível")
        return "\n".join(linhas)


def _ram_gb() -> float:
    """RAM total. Lê /proc/meminfo, que é o que existe no Debian do cluster."""
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            for linha in f:
                if linha.startswith("MemTotal:"):
                    return int(linha.split()[1]) / 1024**2
    except OSError:
        pass
    return float("nan")


def perfil_maquina() -> Perfil:
    """Retrato da máquina atual. Nunca levanta: o que não se sabe fica ausente."""
    try:
        import torch

        cuda = bool(torch.cuda.is_available())
        versao = torch.version.cuda if cuda else None
        gpus = []
        for i in range(torch.cuda.device_count() if cuda else 0):
            p = torch.cuda.get_device_properties(i)
            gpus.append(
                GPU(
                    indice=i,
                    nome=p.name,
                    vram_gb=round(p.total_memory / 1024**3, 1),
                    capacidade=f"{p.major}.{p.minor}",
                )
            )
    except Exception:
        cuda, versao, gpus = False, None, []

    try:
        raiz = str(raiz_de_dados())
        livre = shutil.disk_usage(raiz if os.path.exists(raiz) else "/").free / 1024**3
    except Exception as erro:
        raiz, livre = f"indisponível ({erro})", float("nan")

    return Perfil(
        host=socket.gethostname(),
        plataforma=platform.platform(),
        cpus=os.cpu_count() or 0,
        ram_gb=round(_ram_gb(), 1),
        disco_livre_gb=round(livre, 1),
        raiz_de_dados=raiz,
        cuda_disponivel=cuda,
        versao_cuda=versao,
        gpus=gpus,
    )


def exigir_cuda(permitir_cpu: bool = False) -> str:
    """
    Devolve o dispositivo de treino, recusando CPU por padrão.

    A recusa é deliberada. Este pipeline existe para rodar no servidor; deixá-lo
    cair em CPU silenciosamente produziria uma execução de dias que ninguém
    pediu — e, pior, um número que pareceria comparável ao do servidor. Para o
    smoke test, `permitir_cpu=True` é explícito.
    """
    perfil = perfil_maquina()
    if perfil.cuda_disponivel:
        return "cuda"
    if permitir_cpu:
        return "cpu"
    raise ErroAmbiente(
        "CUDA indisponível nesta máquina. O pipeline de hpc/ é para o servidor; "
        "para exercitar o caminho de código sem GPU use --permitir-cpu (ou "
        "PERMITIR_CPU=1 no Makefile), ciente de que o resultado não é comparável."
    )


def exigir_memoria(minimo_gb: float, o_que: str = "esta etapa") -> None:
    """Recusa etapa que notoriamente não cabe na RAM disponível."""
    perfil = perfil_maquina()
    if perfil.ram_gb == perfil.ram_gb and perfil.ram_gb < minimo_gb:
        raise ErroAmbiente(
            f"{o_que} pede ao menos {minimo_gb:.0f} GB de RAM e a máquina tem "
            f"{perfil.ram_gb:.0f} GB. Rode no servidor, ou reduza o recorte."
        )


def cabe_em_batch_completo(
    arestas: int, nos: int, dim: int = 64, folga: float = 0.6
) -> bool:
    """
    Estimativa grosseira de se o grafo cabe na GPU em batch completo.

    Conta o dominante: `edge_index` em int64 (16 bytes por aresta) mais as
    ativações de duas camadas (`nos × dim × 4` bytes, com folga para gradiente e
    otimizador). Serve para escolher entre batch completo e amostragem de
    vizinhança **antes** de estourar a memória, não para prever o consumo exato.
    """
    perfil = perfil_maquina()
    if not perfil.gpus:
        return False
    bytes_arestas = arestas * 16
    bytes_ativacoes = nos * dim * 4 * 6
    necessario_gb = (bytes_arestas + bytes_ativacoes) / 1024**3
    maior = max(g.vram_gb for g in perfil.gpus)
    return necessario_gb < maior * folga


def semente_global(semente: int = 42) -> None:
    """Fixa a semente de numpy e torch, incluindo CUDA."""
    import numpy as np

    np.random.seed(semente)
    try:
        import torch

        torch.manual_seed(semente)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(semente)
    except Exception:
        pass


def main() -> int:
    """`python -m hpc.config.ambiente` imprime o perfil e sai."""
    perfil = perfil_maquina()
    print(perfil.resumo())
    print()
    if perfil.gpus:
        print(f"VRAM total: {perfil.vram_total_gb} GB")
    else:
        print(
            "Sem GPU: o experimento do servidor recusará rodar sem --permitir-cpu."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
