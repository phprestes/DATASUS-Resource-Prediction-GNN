"""
Migrador de uso único: gera a PRIMEIRA versão de docs/01-selecao-tabelas.md
juntando as três fontes que hoje carregam a seleção de tabelas em paralelo.

    1. docs/SelecaoTabelas_v2.pdf  -> classificação semântica (Útil / Não Útil),
                                      tipo de dado de origem e descrição de cada
                                      coluna, lidos do dicionário de dados.
    2. src/constant.py            -> o que o código de fato usa: FACT_TABLES,
                                      CNES_USEFUL_COLUMNS, CNES_DTYPES,
                                      CNES_PKEY, CNES_FKEY.
    3. docs/relatorio_analise_dados.md -> estatísticas empíricas medidas nos
                                      snapshots 201701 e 202501 (% nulos,
                                      % valores únicos, moda).

Depois de rodar este script uma vez, docs/01-selecao-tabelas.md passa a ser a
fonte da verdade, mantida à mão e lida por src/schema.py. O script fica no
repositório apenas como registro de procedência: ele documenta de onde veio
cada linha da primeira versão do doc, e não é parte do pipeline.

Uso:
    python -m tools.build_selecao_inicial --check   # só diagnostica o parse
    python -m tools.build_selecao_inicial           # escreve o Markdown
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PDF_SELECAO = BASE_DIR / "docs" / "SelecaoTabelas_v2.pdf"
RELATORIO = BASE_DIR / "docs" / "relatorio_analise_dados.md"
SAIDA = BASE_DIR / "docs" / "01-selecao-tabelas.md"

CLASSIFICACOES = ("Não Útil", "Talvez útil", "Útil")

# Snapshots já perfilados pelo notebook 01. O notebook 00 estende para 9 anuais.
COMPETENCIAS = ("201701", "202501")

# Divergências reais entre o nome no dicionário Oracle e o nome do arquivo CSV
# distribuído pelo CNES. Não são erro de OCR nem de normalização: são nomes
# diferentes para a mesma coisa, e só se resolvem à mão.
ALIAS_TABELA = {
    "RL_NASF_CNES": "rlNasfEsf",
}
ALIAS_COLUNA = {
    ("rlEstabUnidAcolhim", "co_profissional_sus"): "CO_PROFISSIONAL",
    ("rlEquipeAldeia", "co_seq_equipe"): "SEQ_EQUIPE",
}

# Tipos SQL que aparecem na coluna "Tipo de Dado" do PDF. Usados para saber
# onde termina o nome da coluna quando o OCR perde underscores (CO LEITO).
TIPO_SQL = re.compile(
    r"^(VARCHAR2?|CHAR|NUMBER|INTEGER|DATE|FLOAT|LONG|CLOB|BLOB|TIMESTAMP)(\(.*\))?$",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Normalização de nomes
#
# As três fontes escrevem os mesmos nomes de três formas diferentes:
#
#   PDF (dicionário Oracle) : RL_ESTAB_COMPLEMENTAR / CO_UNIDADE / DT_ATUALIZACAO
#   CSV do CNES via DuckDB  : rlEstabComplementar  / co_unidade / to_chardt_atualizacaoddmmyyyy
#   constant.py             : rlEstabComplementar  / co_unidade / to_chardt_atualizacaoddmmyyyy
#
# O nome esquisito das datas vem do header do CSV, que é literalmente a
# expressão SQL usada na extração — TO_CHAR(DT_ATUALIZACAO,'DD/MM/YYYY'), às
# vezes com alias de tabela como TO_CHAR(A.DT_ATUALIZACAO,...) — achatada pelo
# normalize_names=True do DuckDB. As funções abaixo reduzem qualquer das três
# formas a uma chave comum de comparação.
# ---------------------------------------------------------------------------


def chave_tabela(nome: str) -> str:
    """RL_ESTAB_COMPLEMENTAR e rlEstabComplementar viram a mesma chave."""
    return nome.replace("_", "").lower()


def chave_coluna(nome: str) -> str:
    """
    Reduz um nome de coluna à sua identidade semântica.

    Desfaz três deformações: o embrulho TO_CHAR(...) das datas, o alias de
    tabela que às vezes vem dentro dele, e a perda de underscores pelo OCR.
    """
    n = nome.strip().lower()
    if n.startswith("to_char"):
        n = n[len("to_char") :]
        n = re.sub(r"ddmmyyyy$", "", n)
        # Alias de tabela grudado no início: adt_atualizacao -> dt_atualizacao.
        n = re.sub(r"^[a-z](?=(dt|co|nu|st|tp|qt|sq|no|ds|sg|ind)_)", "", n)
    return re.sub(r"[^a-z0-9]", "", n)


# ---------------------------------------------------------------------------
# Fonte 1: PDF da seleção
# ---------------------------------------------------------------------------


@dataclass
class ColunaPdf:
    nome: str
    tipo_origem: str
    classificacao: str
    descricao: str


def extrair_texto_pdf(pdf: Path) -> str:
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
        destino = Path(tmp.name)
    try:
        subprocess.run(
            ["pdftotext", "-layout", str(pdf), str(destino)],
            check=True,
            capture_output=True,
        )
        return destino.read_text(encoding="utf-8", errors="replace")
    finally:
        destino.unlink(missing_ok=True)


def juntar(acumulado: str, continuacao: str) -> str:
    """
    Emenda uma linha de continuação, desfazendo a hifenização do LaTeX.

    O PDF quebra palavras e enumerações no fim da linha ("vincu-" / "lado",
    "S-" / "Sim"), e emendar com espaço produziria "vincu- lado". Só se remove o
    hífen quando ele encerra a linha imediatamente depois de um caractere
    alfanumérico — assim hifens legítimos no meio do texto, como em
    "(0-Alugada, 1-Própria)", ficam intactos, porque não estão no fim da linha.
    """
    if re.search(r"[0-9a-záéíóúâêôãõçA-ZÁÉÍÓÚÂÊÔÃÕÇ]-$", acumulado):
        return acumulado[:-1] + continuacao.strip()
    return f"{acumulado} {continuacao.strip()}".strip()


def parse_pdf(texto: str) -> dict[str, tuple[str, list[ColunaPdf]]]:
    """
    Extrai, por tabela, o rótulo humano e a lista de colunas classificadas.

    O layout do pdftotext é de colunas fixas com descrições quebradas em várias
    linhas. A âncora do parse é a palavra de classificação: se a linha contém
    "Útil", "Não Útil" ou "Talvez útil", ela abre uma coluna nova; senão é
    continuação — do rótulo da seção, se ele ainda estiver aberto, ou da
    descrição da última coluna.
    """
    secao = re.compile(r"^\d+\.\d+\s+([A-Z][A-Z_0-9]+)\s*\((.*)$")
    # Ruído de paginação: número de página isolado, ou o cabeçalho da tabela.
    ruido = re.compile(r"^\s*\d+\s*$|Nome da Coluna|Tipo de Dado")

    tabelas: dict[str, tuple[str, list[ColunaPdf]]] = {}
    atual: list[ColunaPdf] | None = None
    # Nome da tabela cujo rótulo ainda não fechou o parêntese. Sete seções do
    # PDF têm o título quebrado em duas linhas.
    rotulo_aberto: str | None = None

    for linha in texto.splitlines():
        cabecalho = secao.match(linha)
        if cabecalho:
            nome, resto = cabecalho.group(1), cabecalho.group(2).strip()
            atual = []
            rotulo, fechou, _ = resto.partition(")")
            tabelas[nome] = (rotulo.strip(), atual)
            rotulo_aberto = None if fechou else nome
            continue

        if atual is None or not linha.strip() or ruido.match(linha):
            continue

        if rotulo_aberto is not None:
            rotulo, colunas = tabelas[rotulo_aberto]
            resto, fechou, _ = linha.strip().partition(")")
            tabelas[rotulo_aberto] = (juntar(rotulo, resto), colunas)
            if fechou:
                rotulo_aberto = None
            continue

        classificacao = next((c for c in CLASSIFICACOES if c in linha), None)
        if classificacao is None:
            if atual:
                atual[-1].descricao = juntar(atual[-1].descricao, linha)
            continue

        campos = linha.partition(classificacao)[0].split()
        descricao = linha.partition(classificacao)[2].strip()
        if not campos:
            continue

        # O tipo de dado é o último token e é reconhecível por padrão SQL. Tudo
        # antes dele é o nome da coluna — que pode ter virado dois tokens se o
        # OCR comeu o underscore (CO LEITO em vez de CO_LEITO).
        if len(campos) > 1 and TIPO_SQL.match(campos[-1]):
            nome = "_".join(campos[:-1])
            tipo_origem = campos[-1]
        else:
            nome = campos[0]
            tipo_origem = " ".join(campos[1:])

        atual.append(ColunaPdf(nome, tipo_origem, classificacao, descricao))

    return {t: v for t, v in tabelas.items() if v[1]}


# ---------------------------------------------------------------------------
# Fonte 3: relatório empírico
# ---------------------------------------------------------------------------


@dataclass
class StatColuna:
    pct_nulos: float
    pct_unicos: float
    moda: str


@dataclass
class StatTabela:
    linhas: dict[str, int] = field(default_factory=dict)
    colunas: dict[str, dict[str, StatColuna]] = field(default_factory=dict)


def parse_relatorio(caminho: Path) -> dict[str, StatTabela]:
    """
    Devolve stats[tabela] com contagem de linhas e estatísticas por competência.

    O relatório é um Markdown gerado pelo notebook 01: um cabeçalho por
    (tabela, competência) seguido de uma tabela de estatísticas por coluna.
    """
    texto = caminho.read_text(encoding="utf-8")
    cabecalho = re.compile(r"^### RELATÓRIO ESTRUTURAL: (\w+) \(Competência: (\d+)\)")
    total = re.compile(r"^\*\*Total de Linhas:\*\* (\d+)")

    stats: dict[str, StatTabela] = defaultdict(StatTabela)
    tabela = competencia = None

    for linha in texto.splitlines():
        m = cabecalho.match(linha)
        if m:
            tabela, competencia = m.group(1), m.group(2)
            stats[tabela].colunas.setdefault(competencia, {})
            continue

        if tabela is None or competencia is None:
            continue

        m = total.match(linha)
        if m:
            stats[tabela].linhas[competencia] = int(m.group(1))
            continue

        if not linha.startswith("|"):
            continue

        campos = [c.strip() for c in linha.strip("|").split("|")]
        if len(campos) < 5 or campos[0] == "Coluna" or set(campos[0]) <= set(":-"):
            continue
        try:
            stats[tabela].colunas[competencia][campos[0]] = StatColuna(
                pct_nulos=float(campos[1]),
                pct_unicos=float(campos[2]),
                moda=campos[3],
            )
        except ValueError:
            continue

    return dict(stats)


# ---------------------------------------------------------------------------
# Filtro empírico
# ---------------------------------------------------------------------------


def degenerada(medicoes: list[StatColuna]) -> str | None:
    """
    Aplica o filtro empírico a uma coluna, dadas suas medições por snapshot.

    Devolve o motivo da rejeição, ou None se a coluna sobrevive. Uma coluna é
    degenerada quando não carrega informação nenhuma: está sempre nula, ou é
    constante em todos os snapshots medidos.
    """
    if not medicoes:
        return None  # sem medição não se rejeita; fica pendente
    if all(m.pct_nulos >= 100.0 for m in medicoes):
        return "100% nula em todos os snapshots medidos"
    if all(m.pct_unicos == 0.0 for m in medicoes):
        return "sem valores distintos em todos os snapshots medidos"
    return None


# ---------------------------------------------------------------------------
# Montagem
# ---------------------------------------------------------------------------


@dataclass
class LinhaDoc:
    coluna: str
    tipo_origem: str
    dtype: str
    classificacao: str
    pkey: bool
    fkey_para: str
    nulos: str
    justificativa: str


@dataclass
class TabelaDoc:
    nome: str
    nome_dicionario: str
    rotulo: str
    escopo: str
    motivo_escopo: str
    pkey: str
    linhas_por_competencia: dict[str, int]
    colunas: list[LinhaDoc]


def carregar_constant_do_git(ref: str = "HEAD") -> dict[str, object]:
    """
    Carrega o src/constant.py que existia antes da refatoração.

    O arquivo foi removido quando docs/01-selecao-tabelas.md passou a ser a
    fonte da verdade, então não há como importá-lo. Lê-lo do histórico mantém
    este script executável, e com isso mantém verificável a alegação de que o
    doc reproduz a seleção anterior.
    """
    for candidato in (f"{ref}:src/constant.py", f"{ref}~1:src/constant.py"):
        resultado = subprocess.run(
            ["git", "-C", str(BASE_DIR), "show", candidato],
            capture_output=True,
            text=True,
        )
        if resultado.returncode == 0:
            # O módulo derivava seus paths de __file__, que não existe num exec
            # de string. Só as constantes de schema interessam aqui, então basta
            # apontar __file__ para onde o arquivo estava.
            namespace: dict[str, object] = {
                "__file__": str(BASE_DIR / "src" / "constant.py")
            }
            exec(compile(resultado.stdout, f"git:{candidato}", "exec"), namespace)
            return namespace

    raise SystemExit(
        "src/constant.py não foi encontrado no histórico git. Este script só "
        "roda em um repositório que ainda contenha o commit anterior à "
        "refatoração; ele existe como registro de procedência, não como parte "
        "do pipeline."
    )


def montar(ref_git: str = "HEAD") -> tuple[list[TabelaDoc], dict[str, int]]:
    antigo = carregar_constant_do_git(ref_git)
    CNES_DTYPES = antigo["CNES_DTYPES"]
    CNES_FKEY = antigo["CNES_FKEY"]
    CNES_PKEY = antigo["CNES_PKEY"]
    CNES_USEFUL_COLUMNS = antigo["CNES_USEFUL_COLUMNS"]
    FACT_TABLES = antigo["FACT_TABLES"]

    pdf = parse_pdf(extrair_texto_pdf(PDF_SELECAO))
    rel = parse_relatorio(RELATORIO)

    por_chave_pdf = {chave_tabela(ALIAS_TABELA.get(t, t)): (t, v) for t, v in pdf.items()}
    contadores = defaultdict(int)
    resultado: list[TabelaDoc] = []

    for tabela in sorted(FACT_TABLES, key=str.lower):
        entrada = por_chave_pdf.get(chave_tabela(tabela))
        nome_dic, (rotulo, colunas_pdf) = entrada if entrada else (tabela, ("", []))
        stats = rel.get(tabela, StatTabela())
        uteis_no_codigo = {chave_coluna(c) for c in CNES_USEFUL_COLUMNS.get(tabela, [])}
        dtypes = CNES_DTYPES.get(tabela, {})
        fkeys = CNES_FKEY.get(tabela, {})

        # Nome real da coluna, como sai do CSV, indexado pela chave semântica.
        nome_real: dict[str, str] = {}
        for medicoes in stats.colunas.values():
            for col in medicoes:
                nome_real.setdefault(chave_coluna(col), col)
        for col in CNES_USEFUL_COLUMNS.get(tabela, []):
            nome_real.setdefault(chave_coluna(col), col)

        alias_invertido = {
            chave_coluna(orig): chave_coluna(csv)
            for (tab, csv), orig in ALIAS_COLUNA.items()
            if tab == tabela
        }

        linhas: list[LinhaDoc] = []
        for cp in colunas_pdf:
            chave = alias_invertido.get(chave_coluna(cp.nome), chave_coluna(cp.nome))
            coluna = nome_real.get(chave, cp.nome.lower())

            medicoes = [
                m[coluna]
                for m in stats.colunas.values()
                if coluna in m
            ]
            nulos = (
                "/".join(f"{m.pct_nulos:.0f}" for m in medicoes) if medicoes else "n/m"
            )

            semantico_ok = cp.classificacao in ("Útil", "Talvez útil")
            motivo_empirico = degenerada(medicoes)

            if not semantico_ok:
                classificacao = "descartada"
                justificativa = f"filtro semântico: {cp.descricao or 'sem uso'}"
                contadores["descartada_semantica"] += 1
            elif motivo_empirico:
                classificacao = "descartada"
                justificativa = f"filtro empírico: {motivo_empirico}"
                contadores["descartada_empirica"] += 1
                if chave in uteis_no_codigo:
                    contadores["degenerada_mas_em_uso"] += 1
            elif not medicoes:
                classificacao = "pendente"
                justificativa = (
                    f"semanticamente útil, sem medição disponível. {cp.descricao}"
                )
                contadores["pendente"] += 1
            else:
                classificacao = "util"
                justificativa = cp.descricao
                contadores["util"] += 1

            linhas.append(
                LinhaDoc(
                    coluna=coluna,
                    tipo_origem=cp.tipo_origem,
                    dtype=dtypes.get(coluna, "string"),
                    classificacao=classificacao,
                    pkey=CNES_PKEY.get(tabela) == coluna,
                    fkey_para=fkeys.get(coluna, "-"),
                    nulos=nulos,
                    justificativa=re.sub(r"\s+", " ", justificativa).strip(" .") or "-",
                )
            )

        # Escopo da tabela: entra se sobrou pelo menos uma coluna aproveitável e
        # se ela foi medida com dados de verdade.
        tem_coluna = any(l.classificacao in ("util", "pendente") for l in linhas)
        tem_dados = any(n > 0 for n in stats.linhas.values())
        todas_nao_uteis = colunas_pdf and all(
            c.classificacao == "Não Útil" for c in colunas_pdf
        )
        if not colunas_pdf:
            escopo, motivo = "fora", "ausente do dicionário de dados"
        elif todas_nao_uteis:
            escopo, motivo = (
                "fora",
                f"filtro semântico: todas as {len(colunas_pdf)} colunas do "
                "dicionário são Não Útil",
            )
        elif not tem_coluna:
            escopo, motivo = "fora", "nenhuma coluna sobrevive aos dois filtros"
        elif not stats.linhas:
            escopo, motivo = "fora", "não perfilada em nenhum snapshot medido"
        elif not tem_dados:
            escopo, motivo = "fora", "vazia em todos os snapshots medidos"
        else:
            escopo, motivo = "incluida", ""
        contadores[f"tabela_{escopo}"] += 1

        resultado.append(
            TabelaDoc(
                nome=tabela,
                nome_dicionario=nome_dic,
                rotulo=rotulo,
                escopo=escopo,
                motivo_escopo=motivo,
                pkey=CNES_PKEY.get(tabela, "-"),
                linhas_por_competencia=stats.linhas,
                colunas=linhas,
            )
        )

    return resultado, dict(contadores)


CABECALHO = """# Seleção de tabelas e colunas do CNES

Este arquivo é a **fonte da verdade** do schema usado pelo projeto. É lido em
tempo de import por [`src/schema.py`](../src/schema.py), que dele deriva
`FACT_TABLES`, `CNES_USEFUL_COLUMNS`, `CNES_DTYPES`, `CNES_PKEY` e `CNES_FKEY`.
Editar este arquivo muda o pipeline; não existe uma segunda lista em código
para manter em sincronia.

Substitui `docs/SelecaoTabelas_v1.pdf` e `docs/SelecaoTabelas_v2.pdf`, que
ficam no repositório apenas como registro histórico.

## Critério de seleção

Uma coluna só é `util` se passar em **dois** filtros independentes:

1. **Semântico** — a coluna significa algo para a pergunta de pesquisa.
   Herdado da classificação Útil / Não Útil do `SelecaoTabelas_v2.pdf`, que foi
   lida do `DICIONARIO_DE_DADOS_CNES_2025.pdf`.
2. **Empírico** — a coluna não é degenerada nos dados reais: não está 100% nula
   em todos os snapshots medidos, e não é constante em todos eles.

A versão anterior da seleção aplicava só o primeiro. Isso deixava passar
colunas que o dicionário descreve como significativas mas que, no banco de
produção, não carregam informação nenhuma. O caso que motivou a mudança:
`DT_ATUALIZACAO_ORIGEM` é descrita como "data da primeira entrada no banco de
produção federal" e é semanticamente útil, mas chega 100% nula em
`rlEstabEquipamento` e preenchida em `rlEstabComplementar` — a diferença é
invisível para quem lê só o dicionário.

### Vocabulário de `classificacao`

| valor | significado |
|---|---|
| `util` | passou nos dois filtros; entra em `CNES_USEFUL_COLUMNS` |
| `descartada` | falhou em um dos filtros; a justificativa diz qual |
| `pendente` | semanticamente útil, ainda sem medição; resolvida pelo `notebook/00_analise_alvo.ipynb` |

### Escopo da tabela

O campo **escopo** de cada tabela vale `incluida` ou `fora`. Só as `incluida`
entram em `FACT_TABLES`, ou seja, só elas são ingeridas do ZIP. Antes desta
revisão, 57 tabelas eram ingeridas e 13 delas descartadas em silêncio na
conversão para Parquet, por não terem entrada em `CNES_USEFUL_COLUMNS`. O
descarte agora é declarado, com motivo escrito, e acontece antes do download
virar trabalho perdido.

## Notas de nomenclatura

Os nomes divergem entre o dicionário Oracle e os arquivos CSV distribuídos pelo
CNES. As tabelas abaixo usam o **nome do CSV**, que é o que o código vê. Três
deformações são recorrentes:

- **Datas embrulhadas.** O header do CSV é a própria expressão SQL da extração,
  `TO_CHAR(DT_ATUALIZACAO,'DD/MM/YYYY')`, achatada pelo `normalize_names=True`
  do DuckDB para `to_chardt_atualizacaoddmmyyyy`. Em `tbCargaHorariaSus` o
  alias da tabela sobrevive dentro do nome: `to_charadt_atualizacaoddmmyyyy`.
- **Nomes diferentes para a mesma coisa.** `RL_NASF_CNES` no dicionário é
  `rlNasfEsf` no CSV. `CO_PROFISSIONAL` em `RL_ESTAB_UNID_ACOLHIM` é
  `co_profissional_sus`. `SEQ_EQUIPE` em `RL_EQUIPE_ALDEIA` é `co_seq_equipe`.
- **Caixa.** O dicionário é `SCREAMING_SNAKE_CASE`; o CSV é `snake_case` e os
  nomes de tabela são `camelCase`.

## Legenda das colunas

- **dtype** — tipo de destino aplicado na conversão para Parquet por
  `src/to_parquet.py`. `datetime64[ns]` dispara `try_strptime` com máscara
  `%d/%m/%Y` e anula datas anteriores a 1900-01-01, sentinela do CNES.
- **pkey** / **fkey_para** — o grafo relacional entregue ao RelBench.
- **nulos** — percentual de nulos medido, por snapshot, na ordem
  {competencias}. `n/m` = não medida.
"""


def emitir(tabelas: list[TabelaDoc], contadores: dict[str, int]) -> str:
    incluidas = [t for t in tabelas if t.escopo == "incluida"]
    fora = [t for t in tabelas if t.escopo == "fora"]

    partes = [CABECALHO.format(competencias=" e ".join(COMPETENCIAS))]

    partes.append("\n## Resumo\n")
    partes.append(f"- Tabelas no dicionário: {len(tabelas)}\n")
    partes.append(f"- Tabelas `incluida`: {len(incluidas)}\n")
    partes.append(f"- Tabelas `fora`: {len(fora)}\n")
    partes.append(f"- Colunas `util`: {contadores.get('util', 0)}\n")
    partes.append(
        f"- Colunas `descartada` pelo filtro semântico: "
        f"{contadores.get('descartada_semantica', 0)}\n"
    )
    partes.append(
        f"- Colunas `descartada` pelo filtro empírico: "
        f"{contadores.get('descartada_empirica', 0)}\n"
    )
    partes.append(f"- Colunas `pendente`: {contadores.get('pendente', 0)}\n")

    partes.append("\n### Tabelas fora de escopo\n\n| tabela | motivo |\n|---|---|\n")
    for t in fora:
        partes.append(f"| `{t.nome}` | {t.motivo_escopo} |\n")

    partes.append("\n## Tabelas\n")
    for t in incluidas:
        partes.append(f"\n### {t.nome}\n\n")
        rotulo = f" — {t.rotulo}" if t.rotulo else ""
        partes.append(f"- **Dicionário:** `{t.nome_dicionario}`{rotulo}\n")
        partes.append(f"- **Escopo:** {t.escopo}\n")
        partes.append(f"- **Chave primária:** `{t.pkey}`\n")
        if t.linhas_por_competencia:
            contagem = ", ".join(
                f"{c}: {n:,}".replace(",", ".")
                for c, n in sorted(t.linhas_por_competencia.items())
            )
            partes.append(f"- **Linhas medidas:** {contagem}\n")
        partes.append(
            "\n| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para "
            "| nulos | justificativa |\n|---|---|---|---|---|---|---|---|\n"
        )
        for c in t.colunas:
            partes.append(
                f"| `{c.coluna}` | {c.tipo_origem} | {c.dtype} | {c.classificacao} "
                f"| {'sim' if c.pkey else '-'} "
                f"| {f'`{c.fkey_para}`' if c.fkey_para != '-' else '-'} "
                f"| {c.nulos} | {c.justificativa} |\n"
            )

    return "".join(partes)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="só diagnostica o parse")
    ap.add_argument(
        "--force",
        action="store_true",
        help="sobrescreve o doc existente, descartando edições feitas à mão",
    )
    args = ap.parse_args()

    if SAIDA.exists() and not (args.check or args.force):
        print(
            f"{SAIDA.relative_to(BASE_DIR)} já existe e é a fonte da verdade do\n"
            "schema, mantida à mão. Este script é um migrador de uso único e\n"
            "regerar o arquivo descartaria qualquer correção feita nele desde a\n"
            "primeira geração. Use --check para diagnosticar, ou --force se a\n"
            "intenção for mesmo recomeçar do zero.",
            file=sys.stderr,
        )
        return 1

    tabelas, contadores = montar()

    for chave in sorted(contadores):
        print(f"{chave:28} {contadores[chave]}")

    if args.check:
        print("\ncolunas hoje em uso que o filtro empírico rejeita:")
        for t in tabelas:
            for c in t.colunas:
                if c.classificacao == "descartada" and "empírico" in c.justificativa:
                    print(f"  {t.nome}.{c.coluna}: {c.justificativa}")
        return 0

    SAIDA.write_text(emitir(tabelas, contadores), encoding="utf-8")
    print(f"\nescrito: {SAIDA.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
