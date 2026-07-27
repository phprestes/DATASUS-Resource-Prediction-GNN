"""
Formato de artefato de modelo, comum aos dois pipelines.

Existe por uma razão concreta: até aqui o experimento media e **descartava**. O
modelo treinado morria com o processo, e `docs/resultados/*.json` guardava só a
métrica agregada — o que torna impossível redesenhar uma curva de
precisão–revocação, inspecionar quem o modelo errou, ou reavaliar sem repetir o
treino. Ver D-35.

Um diretório por execução, sob `models/`:

    modelo.pt                  state_dict com tensores em CPU
    manifesto.json             hiperparâmetros, escopo, modo, métricas, procedência
    indice.parquet             ordem de `unidades` e de `itens`
    historico.parquet          curva de treino por época (quando houver treino)
    previsoes/teste.parquet    escore por exemplo do conjunto avaliado
    previsoes/teste-compacto.parquet   recorte leve do anterior

O mesmo formato serve ao pipeline desta máquina (`tools/roda_experimento.py`) e
ao do servidor (`hpc/`). É deliberado: as duas metades da matriz técnica × escopo
só são comparáveis se o artefato for lido pelo mesmo código.

**Por que o índice é obrigatório.** Um `state_dict` sem a ordem de `unidades` e
`itens` não significa nada: o embedding de item é indexado por posição, e trocar
a ordem produz um modelo que carrega sem erro e pontua lixo. É a mesma classe de
erro que `IndicePares` existe para evitar, agora atravessando máquinas.
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from src.config.paths import BASE_DIR, MODELS_DIR

# Nomes fixos dentro do pacote. Mudar um deles quebra a leitura de execuções
# antigas, então mudança aqui pede versão nova em FORMATO.
FORMATO = "1.0"
ARQ_MODELO = "modelo.pt"
ARQ_MANIFESTO = "manifesto.json"
ARQ_INDICE = "indice.parquet"
ARQ_HISTORICO = "historico.parquet"
PASTA_PREVISOES = "previsoes"
ARQ_PREVISOES = "teste.parquet"
ARQ_PREVISOES_COMPACTAS = "teste-compacto.parquet"


class ErroArtefato(RuntimeError):
    """Pacote de modelo ausente, incompleto ou internamente inconsistente."""


@dataclass
class ExecucaoSalva:
    """Pacote lido do disco. Os dados pesados são carregados sob demanda."""

    caminho: Path
    manifesto: dict = field(default_factory=dict)

    @property
    def nome(self) -> str:
        """
        Returns:
            Nome do diretório do pacote, que carrega data, trilha, escopo, modo,
            variante e semente (ver `nome_de_execucao`).
        """
        return self.caminho.name

    @property
    def metricas(self) -> dict:
        """
        Returns:
            Métricas gravadas no manifesto, ou mapa vazio. São as **declaradas**;
            para recomputar do escore salvo, use `recomputar_metricas`.
        """
        return self.manifesto.get("metricas", {})

    def indice(self) -> dict[str, list[str]]:
        """
        Ordem de `unidades` e `itens`, como o treino a viu.

        Returns:
            Mapa `{"unidades": [...], "itens": [...]}`. Não é opcional: o
            embedding de item é indexado por posição, então pesos sem esta ordem
            carregam sem erro e pontuam lixo (D-35).
        """
        df = pd.read_parquet(self.caminho / ARQ_INDICE)
        return {
            eixo: df.loc[df["eixo"] == eixo, "valor"].tolist()
            for eixo in df["eixo"].unique()
        }

    def previsoes(self, compactas: bool = False) -> pd.DataFrame:
        """
        Escore por exemplo, como gravado no treino.

        Args:
            compactas: usa a versão reduzida, quando existe.

        Returns:
            DataFrame com rótulo, escore e entidade por exemplo. É o que permite
            recomputar métrica e gerar curva de precisão–revocação sem GPU e sem
            a camada de dados.

        Raises:
            ErroArtefato: o pacote não tem previsão salva, e portanto não pode
                ser reavaliado fora da máquina que o treinou.
        """
        arquivo = ARQ_PREVISOES_COMPACTAS if compactas else ARQ_PREVISOES
        caminho = self.caminho / PASTA_PREVISOES / arquivo
        if not caminho.exists():
            raise ErroArtefato(
                f"{caminho} não existe. Execuções sem previsão salva não podem ser "
                "reavaliadas fora da máquina que as treinou."
            )
        return pd.read_parquet(caminho)

    def historico(self) -> pd.DataFrame:
        """
        Curva de treino, uma linha por época.

        Returns:
            DataFrame com época, perda e AP de validação. Vazio nas trilhas sem
            treino. O número de épocas até a parada é resultado reportável, não
            detalhe de implementação (D-42).
        """
        caminho = self.caminho / ARQ_HISTORICO
        if not caminho.exists():
            return pd.DataFrame()
        return pd.read_parquet(caminho)

    def pesos(self, dispositivo: str = "cpu") -> dict:
        """
        `state_dict` do modelo, mapeado para o dispositivo pedido.

        O default é CPU porque o caso de uso é justamente inspecionar num
        notebook, longe da GPU que treinou.

        Args:
            dispositivo: destino do mapeamento, `"cpu"` ou `"cuda"`.

        Returns:
            `state_dict` do modelo.

        Raises:
            ErroArtefato: o pacote não tem pesos, o que é o caso das baselines.
        """
        import torch

        caminho = self.caminho / ARQ_MODELO
        if not caminho.exists():
            raise ErroArtefato(f"{caminho} não existe: execução sem pesos salvos")
        return torch.load(caminho, map_location=dispositivo, weights_only=True)


# ---------------------------------------------------------------------------
# Procedência
# ---------------------------------------------------------------------------


def commit_do_git() -> str | None:
    """Commit atual, ou None fora de um repositório. Nunca levanta."""
    try:
        saida = subprocess.run(
            ["git", "-C", str(BASE_DIR), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return saida.stdout.strip() or None
    except Exception:
        return None


def arvore_suja() -> bool | None:
    """
    Se há alteração não commitada. Entra no manifesto porque um número medido
    sobre árvore suja não é reproduzível a partir do commit registrado.
    """
    try:
        saida = subprocess.run(
            ["git", "-C", str(BASE_DIR), "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return bool(saida.stdout.strip())
    except Exception:
        return None


def versoes() -> dict[str, str]:
    """Versões das bibliotecas que afetam o número reportado."""
    saida = {"python": sys.version.split()[0], "plataforma": platform.platform()}
    for modulo in ("numpy", "pandas", "torch", "torch_geometric", "sklearn", "duckdb"):
        try:
            saida[modulo] = __import__(modulo).__version__
        except Exception:
            saida[modulo] = "ausente"
    return saida


def nome_de_execucao(
    trilha: str,
    escopo: str | None,
    modo: str = "compativel",
    quando: date | None = None,
    variante: str | None = None,
    semente: int | None = None,
) -> str:
    """
    Nome do diretório de um pacote: data, trilha, escopo, modo, variante e semente.

    Todo eixo da bateria entra no nome, e por um motivo só: duas execuções que
    diferem em qualquer um deles são resultados distintos, e sem o eixo no
    caminho a segunda sobrescreve a primeira em silêncio. Já aconteceu com a
    variante de pandemia, que só existia dentro do JSON.

    Args:
        trilha: nome do modelo, por exemplo `gnn_relacional`.
        escopo: recorte espacial; `None` vira `pais`.
        modo: `compativel` ou `completo` (D-34).
        quando: data do pacote. `None` usa hoje.
        variante: `com-pandemia` ou `sem-pandemia`. `None` omite do nome, o que
            mantém compatibilidade com os pacotes já gravados.
        semente: semente da execução. `None` omite do nome.

    Returns:
        Nome de diretório, sem separador de caminho.
    """
    quando = quando or date.today()
    partes = [str(quando), trilha, escopo or "pais", modo]
    if variante:
        partes.append(variante)
    if semente is not None:
        partes.append(f"s{semente}")
    return "-".join(partes)


# ---------------------------------------------------------------------------
# Escrita
# ---------------------------------------------------------------------------


def _previsoes_para_df(
    previsao, itens: "np.ndarray | pd.Series | None" = None
) -> pd.DataFrame:
    """
    Escores por exemplo em colunas estreitas.

    `entidade` fica como código inteiro, e a tradução mora em `indice.parquet`.
    Materializar `co_unidade` como string aqui multiplicaria o arquivo por
    quarenta, que é a razão de `Previsao` guardar códigos (D-23).

    Args:
        previsao: `Previsao` com rótulos, escores e entidades.
        itens: item de cada exemplo, na **mesma ordem** da previsão. `None` omite
            a coluna, o que impede recomputar MAP@k depois.

    Returns:
        DataFrame com `entidade` (int32), `y` (int8), `escore` (float32) e, quando
        dado, `item` (int16).

    Raises:
        ErroArtefato: `itens` tem comprimento diferente da previsão, o que
            significa que vieram de fatias diferentes e o par sairia embaralhado.
    """
    dados = {
        "entidade": np.asarray(previsao.entidades, dtype=np.int32),
        "y": np.asarray(previsao.y, dtype=np.int8),
        "escore": np.asarray(previsao.escore, dtype=np.float32),
    }
    if itens is not None:
        item = pd.Series(itens)
        if len(item) != len(dados["y"]):
            raise ErroArtefato(
                f"itens tem {len(item)} linhas e a previsão {len(dados['y'])}: "
                "as duas precisam vir da mesma fatia da tabela de tarefa, na mesma "
                "ordem, senão o par (entidade, item) sai embaralhado"
            )
        if isinstance(item.dtype, pd.CategoricalDtype):
            item = item.cat.codes
        dados["item"] = np.asarray(item, dtype=np.int16)
    return pd.DataFrame(dados)


def _compactar_previsoes(
    df: pd.DataFrame, top_por_entidade: int = 20, negativos: int = 200_000, semente: int = 42
) -> pd.DataFrame:
    """
    Recorte leve: os melhores escores de cada entidade mais uma amostra de resto.

    Serve para levar a previsão a uma máquina modesta. **Não** serve para
    recomputar AP nem prevalência — o arquivo completo é que serve —, e por isso
    o compacto carrega a coluna `origem` marcando de onde cada linha veio.

    O `top` default é 20 porque o vocabulário do alvo tem 99 itens: pegar 50 por
    estabelecimento guardaria metade do arquivo completo e não compactaria nada.
    Com 20, o compacto fica em cerca de um quinto, e ainda cobre MAP@10 com folga.

    Args:
        df: previsões completas, como `_previsoes_para_df` devolve.
        top_por_entidade: quantos melhores escores manter por entidade.
        negativos: teto da amostra do resto.
        semente: semente da amostra.

    Returns:
        DataFrame com a coluna `origem` marcando `"topo"` ou `"amostra"`, para que
        ninguém confunda o recorte com o arquivo completo.
    """
    rng = np.random.default_rng(semente)
    ordenado = df.sort_values("escore", ascending=False)
    topo = ordenado.groupby("entidade", sort=False).head(top_por_entidade)
    resto = df.drop(index=topo.index)
    if len(resto) > negativos:
        escolha = rng.choice(len(resto), size=negativos, replace=False)
        resto = resto.iloc[np.sort(escolha)]
    topo = topo.assign(origem="topo")
    resto = resto.assign(origem="amostra")
    return pd.concat([topo, resto], ignore_index=True)


def salvar_execucao(
    trilha: str,
    previsao,
    metricas: dict,
    *,
    escopo: str | None = None,
    modo: str = "compativel",
    variante: str | None = None,
    semente: int | None = None,
    modelo=None,
    unidades: "list[str] | None" = None,
    itens_indice: "list[str] | None" = None,
    itens_por_exemplo: "np.ndarray | pd.Series | None" = None,
    historico: "pd.DataFrame | None" = None,
    hiperparametros: dict | None = None,
    particao=None,
    extra: dict | None = None,
    pasta_base: Path = MODELS_DIR,
    nome: str | None = None,
    salvar_previsoes: bool = True,
) -> Path:
    """
    Grava um pacote de execução e devolve o diretório escrito.

    `metricas` é o dicionário que `src.ml.metrics.avaliar_classificacao` devolve,
    ou um mapa de visões para esse dicionário — a comparação pareada de D-15 tem
    duas visões, e as duas cabem aqui.

    `modelo` é opcional: baseline não tem pesos, e ainda assim vale salvar
    previsão e métrica, porque é o que permite refazer a curva com o piso ao lado
    (D-11).

    Args:
        trilha: nome do modelo, por exemplo `gnn_relacional`.
        previsao: `Previsao` com rótulos, escores e entidades.
        metricas: métricas por visão, ou um bloco único.
        escopo: recorte espacial da execução.
        modo: `compativel` ou `completo` (D-34).
        variante: `com-pandemia` ou `sem-pandemia`.
        semente: semente da execução.
        modelo: modelo treinado. `None` para baseline.
        unidades: ordem de `co_unidade` que o modelo viu. Obrigatória quando
            `modelo` é dado.
        itens_indice: ordem do vocabulário de itens. Idem.
        itens_por_exemplo: item de cada exemplo, para o MAP@k ser recomputável.
        historico: curva de treino.
        particao: partição temporal, gravada no manifesto.
        hiperparametros: gravados no manifesto como procedência.
        extra: campos livres do manifesto.
        pasta_base: raiz de `models/`.
        nome: nome do diretório. `None` deriva de `nome_de_execucao`.
        salvar_previsoes: grava o escore por exemplo.

    Returns:
        Diretório escrito.

    Raises:
        ErroArtefato: `modelo` foi passado sem `unidades` e `itens_indice`. A
            recusa é deliberada: pesos sem a ordem carregam sem erro e pontuam
            lixo (D-35).
    """
    import torch

    nome = nome or nome_de_execucao(trilha, escopo, modo, variante=variante, semente=semente)
    destino = Path(pasta_base) / nome
    (destino / PASTA_PREVISOES).mkdir(parents=True, exist_ok=True)

    if modelo is not None:
        pesos = {c: t.detach().cpu() for c, t in modelo.state_dict().items()}
        torch.save(pesos, destino / ARQ_MODELO)

    if unidades is not None or itens_indice is not None:
        linhas = [{"eixo": "unidades", "posicao": i, "valor": u}
                  for i, u in enumerate(unidades or [])]
        linhas += [{"eixo": "itens", "posicao": i, "valor": k}
                   for i, k in enumerate(itens_indice or [])]
        pd.DataFrame(linhas).to_parquet(destino / ARQ_INDICE, index=False)
    elif modelo is not None:
        raise ErroArtefato(
            "pacote com pesos exige `unidades` e `itens_indice`: sem a ordem, o "
            "state_dict carrega sem erro e pontua lixo"
        )

    if historico is not None and len(historico):
        historico.to_parquet(destino / ARQ_HISTORICO, index=False)

    df_previsoes = None
    if salvar_previsoes:
        df_previsoes = _previsoes_para_df(previsao, itens_por_exemplo)
        df_previsoes.to_parquet(
            destino / PASTA_PREVISOES / ARQ_PREVISOES, index=False
        )
        _compactar_previsoes(df_previsoes).to_parquet(
            destino / PASTA_PREVISOES / ARQ_PREVISOES_COMPACTAS, index=False
        )

    manifesto = {
        "formato": FORMATO,
        "nome": nome,
        "data": str(date.today()),
        "trilha": trilha,
        "escopo": escopo,
        "modo": modo,
        "conjunto": getattr(previsao, "conjunto", None),
        "modelo_salvo": modelo is not None,
        "previsoes_salvas": bool(salvar_previsoes),
        "n_exemplos": int(len(previsao.y)),
        "hiperparametros": hiperparametros or {},
        "metricas": metricas,
        "procedencia": {
            "commit": commit_do_git(),
            "arvore_suja": arvore_suja(),
            "versoes": versoes(),
        },
    }
    if particao is not None:
        manifesto["particao"] = {
            conjunto: [t.destino for t in grupo]
            for conjunto, grupo in particao.conjuntos.items()
        }
        manifesto["corte_do_grafo"] = particao.antes_de_todos_os_rotulos
        manifesto["fim_do_treino"] = particao.fim_do_treino
    if extra:
        manifesto.update(extra)

    (destino / ARQ_MANIFESTO).write_text(
        json.dumps(manifesto, indent=2, ensure_ascii=False, default=float),
        encoding="utf-8",
    )
    return destino


# ---------------------------------------------------------------------------
# Leitura e conferência
# ---------------------------------------------------------------------------


def carregar_execucao(caminho: "str | Path") -> ExecucaoSalva:
    """
    Lê o manifesto de um pacote, sem tocar nos dados pesados.

    Args:
        caminho: diretório do pacote.

    Returns:
        `ExecucaoSalva` com o manifesto carregado. Previsões, pesos, índice e
        histórico ficam sob demanda.

    Raises:
        ErroArtefato: não há manifesto no caminho, logo não é um pacote.
    """
    caminho = Path(caminho)
    arquivo = caminho / ARQ_MANIFESTO
    if not arquivo.exists():
        raise ErroArtefato(
            f"{arquivo} não existe: {caminho} não é um pacote de execução"
        )
    return ExecucaoSalva(
        caminho=caminho, manifesto=json.loads(arquivo.read_text(encoding="utf-8"))
    )


def listar_execucoes(pasta_base: Path = MODELS_DIR) -> list[ExecucaoSalva]:
    """
    Todos os pacotes de `models/`.

    Args:
        pasta_base: raiz a varrer.

    Returns:
        Pacotes do mais recente para o mais antigo. Lista vazia se a pasta não
        existe, para que o chamador não precise checar antes.
    """
    if not Path(pasta_base).exists():
        return []
    achados = [
        carregar_execucao(p)
        for p in sorted(Path(pasta_base).iterdir())
        if (p / ARQ_MANIFESTO).exists()
    ]
    # Ordena por data e, no empate, pelo nome — que começa pela data também. Sem
    # o desempate, duas execuções do mesmo dia saem na ordem do sistema de
    # arquivos, e `make validar` sem argumento pegaria a errada.
    return sorted(
        achados,
        key=lambda e: (e.manifesto.get("data", ""), e.nome),
        reverse=True,
    )


def recomputar_metricas(
    execucao: "ExecucaoSalva | str | Path", k: int = 10
) -> dict[str, dict]:
    """
    Recalcula as métricas a partir das previsões salvas, sem GPU e sem `data/`.

    É o que dá sentido a "validar em qualquer dispositivo": as métricas do
    manifesto passam a ser verificáveis por quem recebe o pacote, em vez de
    aceitas por confiança.

    Args:
        execucao: pacote, ou caminho para um.
        k: tamanho do topo do MAP@k.

    Returns:
        Mapa com a visão `teste_completo`. A visão pareada exige o conjunto de
        posicionáveis, que não vai no pacote.
    """
    from src.ml.metrics import avaliar_classificacao

    if not isinstance(execucao, ExecucaoSalva):
        execucao = carregar_execucao(execucao)
    df = execucao.previsoes()
    y = df["y"].to_numpy()
    escore = df["escore"].to_numpy()
    entidades = df["entidade"].to_numpy()
    return {"teste_completo": avaliar_classificacao(y, escore, entidades, k=k)}


def conferir(
    execucao: "ExecucaoSalva | str | Path", tolerancia: float = 1e-6, k: int = 10
) -> list[str]:
    """
    Divergências entre o manifesto e o que as previsões salvas produzem.

    Lista vazia é o resultado esperado. Qualquer item é sinal de pacote
    inconsistente — previsão de uma execução com métrica de outra, por exemplo.

    Args:
        execucao: pacote, ou caminho para um.
        tolerancia: diferença absoluta aceita por métrica.
        k: tamanho do topo do MAP@k.

    Returns:
        Uma string por divergência, vazia quando tudo confere. É o que
        `make validar` imprime.
    """
    if not isinstance(execucao, ExecucaoSalva):
        execucao = carregar_execucao(execucao)
    if not execucao.manifesto.get("previsoes_salvas"):
        return ["execução sem previsões salvas: nada a conferir"]

    recomputado = recomputar_metricas(execucao, k=k)["teste_completo"]
    declarado = execucao.metricas
    # O manifesto pode ter uma visão só ou várias; a comparável é a completa.
    if "teste_completo" in declarado:
        declarado = declarado["teste_completo"]

    problemas = []
    for chave, valor in recomputado.items():
        if chave not in declarado:
            continue
        esperado = declarado[chave]
        if esperado is None:
            continue
        if abs(float(esperado) - float(valor)) > tolerancia:
            problemas.append(
                f"{chave}: manifesto diz {esperado:.6f}, previsões dão {valor:.6f}"
            )
    return problemas
