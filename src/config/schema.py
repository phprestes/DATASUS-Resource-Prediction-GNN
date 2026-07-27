"""
Schema do CNES, derivado de docs/01-selecao-tabelas.md.

Aquele Markdown é a fonte única da verdade: editá-lo muda o pipeline. Este
módulo o lê em tempo de import e expõe as estruturas que o ETL e a montagem do
grafo consomem.

    FACT_TABLES            tabelas com escopo `incluida`; o que se ingere do ZIP
    CNES_EXTRACT_COLUMNS   colunas materializadas em Parquet (util + pendente)
    CNES_USEFUL_COLUMNS    colunas aprovadas nos dois filtros (só util)
    CNES_DTYPES            tipo de destino por coluna, aplicado na conversão
    CNES_PKEY              chave primária por tabela
    CNES_FKEY              {coluna: tabela_destino}, o grafo relacional
    TABELAS_FORA           {tabela: motivo} das excluídas, para inspeção

A distinção entre CNES_EXTRACT_COLUMNS e CNES_USEFUL_COLUMNS resolve um
problema de ordem: uma coluna `pendente` só pode ser medida se estiver no
Parquet, mas não deve entrar na modelagem antes de ser aprovada. O ETL usa a
primeira; os modelos usam a segunda. Quando não há colunas `pendente`, as duas
são idênticas.

O parser é estrito de propósito. Um Markdown malformado quebra o import, e o
erro nomeia arquivo, seção e linha — falhar no import é melhor que carregar um
schema silenciosamente incompleto, que foi exatamente o modo de falha da versão
anterior.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

from src.config.paths import SELECAO_TABELAS

CLASSIFICACOES_VALIDAS = frozenset({"util", "descartada", "pendente"})
ESCOPOS_VALIDOS = frozenset({"incluida", "fora"})

# Colunas que a tabela Markdown de cada seção precisa ter. Outras são ignoradas,
# o que permite acrescentar evidência ao doc sem tocar no parser.
COLUNAS_OBRIGATORIAS = ("coluna", "tipo_origem", "dtype", "classificacao", "pkey", "fkey_para")


class ErroSchema(ValueError):
    """Markdown de seleção malformado ou internamente inconsistente."""


@dataclass(frozen=True)
class Coluna:
    nome: str
    tipo_origem: str
    dtype: str
    classificacao: str
    pkey: bool
    fkey_para: str | None
    justificativa: str
    linha_doc: int

    @property
    def materializar(self) -> bool:
        """
        Se a coluna deve existir no Parquet.

        Returns:
            `True` para colunas `util` ou `pendente`. A `pendente` entra no
            Parquet para poder ser medida, mas fica fora de CNES_USEFUL_COLUMNS
            até ser aprovada.
        """
        return self.classificacao in ("util", "pendente")


@dataclass
class Tabela:
    nome: str
    nome_dicionario: str = ""
    escopo: str = "incluida"
    motivo_escopo: str = ""
    pkey: str | None = None
    # Conjunto de colunas que identifica uma linha, quando conhecido. Distinto
    # de pkey: pkey é a chave da entidade que o RelBench usa para ligar tabelas
    # (co_unidade), e quase nunca é única — rlEstabEquipamento tem uma linha por
    # equipamento, não por estabelecimento. src/etl/changes.py precisa da chave da
    # linha para distinguir modificação de remoção seguida de inserção.
    chave_natural: tuple[str, ...] = ()
    colunas: list[Coluna] = field(default_factory=list)
    linha_doc: int = 0

    def por_classificacao(self, *quais: str) -> list[str]:
        """
        Nomes das colunas com alguma das classificações pedidas.

        Args:
            *quais: classificações aceitas, entre `util`, `pendente` e
                `descartada`.

        Returns:
            Nomes na ordem em que aparecem no documento.
        """
        return [c.nome for c in self.colunas if c.classificacao in quais]


def _limpar(celula: str) -> str:
    """
    Normaliza uma célula da tabela Markdown.

    Args:
        celula: texto bruto da célula, possivelmente com crases e espaços.

    Returns:
        O conteúdo sem crases nem espaços. Célula vazia — marcada com `-` no
        documento — vira string vazia.
    """
    valor = celula.strip().strip("`").strip()
    return "" if valor == "-" else valor


def _celulas(linha: str) -> list[str]:
    """
    Divide uma linha de tabela Markdown nas suas células.

    Args:
        linha: linha começando e terminando com `|`.

    Returns:
        Conteúdo de cada célula, sem espaços nas bordas.
    """
    return [c.strip() for c in linha.strip().strip("|").split("|")]


def _e_separador(celulas: list[str]) -> bool:
    """
    Se a linha é o separador entre cabeçalho e corpo (`|---|---|`).

    Args:
        celulas: células já divididas por `_celulas`.

    Returns:
        `True` quando toda célula é composta apenas de `-`, `:` e espaço.
    """
    return all(set(c) <= set(":- ") and c for c in celulas)


def _parse(texto: str, origem: str) -> tuple[list[Tabela], dict[str, str]]:
    """
    Percorre o Markdown e devolve as tabelas e os motivos de exclusão.

    Só o conteúdo depois de `## Tabelas` descreve schema: o cabeçalho do
    documento tem tabelas Markdown que documentam vocabulário e escopo, e o
    parser espera aquela âncora antes de começar.

    Args:
        texto: conteúdo integral de `01-selecao-tabelas.md`.
        origem: nome do arquivo, usado só para compor mensagens de erro.

    Returns:
        Par `(tabelas, fora)`. `tabelas` na ordem do documento, incluindo as de
        escopo `fora`; `fora` mapeia nome da tabela excluída para o motivo.

    Raises:
        ErroSchema: escopo ou classificação inválidos, cabeçalho sem as colunas
            obrigatórias, linha com número de células diferente do cabeçalho,
            coluna sem nome, ou nenhuma tabela encontrada.
    """
    tabelas: list[Tabela] = []
    fora: dict[str, str] = {}
    atual: Tabela | None = None
    em_schema = False
    em_fora = False
    cabecalho: list[str] | None = None

    meta = re.compile(r"^-\s+\*\*(.+?):\*\*\s*(.*)$")

    for n, linha in enumerate(texto.splitlines(), start=1):
        if linha.startswith("## "):
            titulo = linha[3:].strip().lower()
            em_schema = titulo == "tabelas"
            em_fora = False
            atual, cabecalho = None, None
            continue

        if linha.startswith("### "):
            titulo = linha[4:].strip()
            em_fora = titulo.lower().startswith("tabelas fora de escopo")
            cabecalho = None
            if em_schema:
                atual = Tabela(nome=titulo, linha_doc=n)
                tabelas.append(atual)
            else:
                atual = None
            continue

        if em_fora and linha.startswith("|"):
            celulas = _celulas(linha)
            if len(celulas) == 2 and not _e_separador(celulas):
                nome, motivo = _limpar(celulas[0]), celulas[1].strip()
                if nome.lower() != "tabela":
                    fora[nome] = motivo
            continue

        if atual is None:
            continue

        m = meta.match(linha.strip())
        if m:
            rotulo, valor = m.group(1).strip().lower(), m.group(2).strip()
            if rotulo == "escopo":
                atual.escopo = valor.lower()
                if atual.escopo not in ESCOPOS_VALIDOS:
                    raise ErroSchema(
                        f"{origem}:{n}: tabela {atual.nome!r} tem escopo "
                        f"{valor!r}; esperado um de {sorted(ESCOPOS_VALIDOS)}"
                    )
            elif rotulo.startswith("dicion"):
                atual.nome_dicionario = _limpar(valor.split("—")[0])
            elif rotulo.startswith("chave prim"):
                atual.pkey = _limpar(valor) or None
            elif rotulo.startswith("chave natural"):
                atual.chave_natural = tuple(
                    p for p in (_limpar(x) for x in valor.split(",")) if p
                )
            continue

        if not linha.startswith("|"):
            continue

        celulas = _celulas(linha)
        if cabecalho is None:
            faltando = [c for c in COLUNAS_OBRIGATORIAS if c not in celulas]
            if faltando:
                raise ErroSchema(
                    f"{origem}:{n}: cabeçalho da tabela de {atual.nome!r} não tem "
                    f"as colunas {faltando}; encontrado {celulas}"
                )
            cabecalho = celulas
            continue

        if _e_separador(celulas):
            continue

        if len(celulas) != len(cabecalho):
            raise ErroSchema(
                f"{origem}:{n}: linha de {atual.nome!r} tem {len(celulas)} células, "
                f"mas o cabeçalho tem {len(cabecalho)}"
            )

        campo = dict(zip(cabecalho, celulas))
        classificacao = campo["classificacao"].strip().lower()
        if classificacao not in CLASSIFICACOES_VALIDAS:
            raise ErroSchema(
                f"{origem}:{n}: coluna {campo['coluna']!r} de {atual.nome!r} tem "
                f"classificacao {classificacao!r}; esperado um de "
                f"{sorted(CLASSIFICACOES_VALIDAS)}"
            )

        nome = _limpar(campo["coluna"])
        if not nome:
            raise ErroSchema(f"{origem}:{n}: linha de {atual.nome!r} sem nome de coluna")

        atual.colunas.append(
            Coluna(
                nome=nome,
                tipo_origem=campo["tipo_origem"].strip(),
                dtype=_limpar(campo["dtype"]) or "string",
                classificacao=classificacao,
                pkey=campo["pkey"].strip().lower() in ("sim", "s", "x"),
                fkey_para=_limpar(campo["fkey_para"]) or None,
                justificativa=campo.get("justificativa", "").strip(),
                linha_doc=n,
            )
        )

    if not tabelas:
        raise ErroSchema(
            f"{origem}: nenhuma tabela encontrada. O doc precisa de uma seção "
            "'## Tabelas' com subseções '### nomeDaTabela'."
        )

    return tabelas, fora


def _validar(tabelas: list[Tabela], origem: str) -> None:
    """
    Checa a consistência interna do schema já parseado.

    Args:
        tabelas: saída de `_parse`, na ordem do documento.
        origem: nome do arquivo, usado só para compor mensagens de erro.

    Raises:
        ErroSchema: tabela declarada duas vezes, coluna repetida, chave primária
            ou natural citando coluna inexistente, tabela `incluida` sem nenhuma
            coluna aproveitável, ou chave estrangeira apontando para tabela que
            não está no escopo.
    """
    nomes = {t.nome for t in tabelas if t.escopo == "incluida"}

    vistos: dict[str, int] = {}
    for t in tabelas:
        if t.nome in vistos:
            raise ErroSchema(
                f"{origem}:{t.linha_doc}: tabela {t.nome!r} declarada duas vezes "
                f"(a primeira em :{vistos[t.nome]})"
            )
        vistos[t.nome] = t.linha_doc

        if t.escopo != "incluida":
            continue

        colunas = {c.nome for c in t.colunas}
        if len(colunas) != len(t.colunas):
            repetidas = sorted(
                n for n in colunas if sum(c.nome == n for c in t.colunas) > 1
            )
            raise ErroSchema(
                f"{origem}:{t.linha_doc}: tabela {t.nome!r} repete as colunas {repetidas}"
            )

        if t.pkey and t.pkey not in colunas:
            raise ErroSchema(
                f"{origem}:{t.linha_doc}: chave primária {t.pkey!r} de {t.nome!r} "
                "não está entre as colunas declaradas"
            )

        materializadas = {c.nome for c in t.colunas if c.materializar}
        faltando = [c for c in t.chave_natural if c not in materializadas]
        if faltando:
            raise ErroSchema(
                f"{origem}:{t.linha_doc}: chave natural de {t.nome!r} cita "
                f"{faltando}, que não são colunas materializadas da tabela"
            )

        if not t.por_classificacao("util", "pendente"):
            raise ErroSchema(
                f"{origem}:{t.linha_doc}: tabela {t.nome!r} tem escopo 'incluida' "
                "mas nenhuma coluna 'util' ou 'pendente'. Marque-a como 'fora' "
                "com um motivo, ou aprove alguma coluna."
            )

        for c in t.colunas:
            if c.fkey_para and c.fkey_para not in nomes:
                raise ErroSchema(
                    f"{origem}:{c.linha_doc}: {t.nome}.{c.nome} referencia "
                    f"{c.fkey_para!r}, que não é uma tabela com escopo 'incluida'"
                )


@lru_cache(maxsize=1)
def carregar() -> tuple[tuple[Tabela, ...], dict[str, str]]:
    """
    Lê e valida `docs/01-selecao-tabelas.md`. Resultado em cache por processo.

    Use este acesso quando precisar da justificativa ou do tipo de origem de uma
    coluna; para o pipeline, prefira as constantes do módulo, que já são
    derivadas daqui.

    Returns:
        Par `(tabelas, fora)`. `tabelas` na ordem do documento; `fora` mapeia
        nome da tabela excluída para o motivo declarado.

    Raises:
        ErroSchema: documento ausente, malformado ou internamente inconsistente.
    """
    if not SELECAO_TABELAS.exists():
        raise ErroSchema(
            f"{SELECAO_TABELAS} não encontrado. É a fonte da verdade do schema; "
            "sem ele o pipeline não sabe quais tabelas e colunas usar."
        )
    origem = SELECAO_TABELAS.name
    tabelas, fora = _parse(SELECAO_TABELAS.read_text(encoding="utf-8"), origem)
    _validar(tabelas, origem)
    return tuple(tabelas), fora


_TABELAS, TABELAS_FORA = carregar()
_INCLUIDAS = [t for t in _TABELAS if t.escopo == "incluida"]

FACT_TABLES: list[str] = [t.nome for t in _INCLUIDAS]

CNES_EXTRACT_COLUMNS: dict[str, list[str]] = {
    t.nome: t.por_classificacao("util", "pendente") for t in _INCLUIDAS
}

CNES_USEFUL_COLUMNS: dict[str, list[str]] = {
    t.nome: t.por_classificacao("util") for t in _INCLUIDAS
}

CNES_DTYPES: dict[str, dict[str, str]] = {
    t.nome: {c.nome: c.dtype for c in t.colunas if c.materializar} for t in _INCLUIDAS
}

CNES_PKEY: dict[str, str] = {t.nome: t.pkey for t in _INCLUIDAS if t.pkey}

CNES_NATURAL_KEY: dict[str, tuple[str, ...]] = {
    t.nome: t.chave_natural for t in _INCLUIDAS if t.chave_natural
}

CNES_FKEY: dict[str, dict[str, str]] = {
    t.nome: {c.nome: c.fkey_para for c in t.colunas if c.fkey_para and c.materializar}
    for t in _INCLUIDAS
    if any(c.fkey_para and c.materializar for c in t.colunas)
}


def tabela(nome: str) -> Tabela:
    """
    Declaração completa de uma tabela, incluindo colunas descartadas.

    Args:
        nome: nome da tabela na grafia do CSV, por exemplo `tbEstabelecimento`.

    Returns:
        A `Tabela` com todas as suas colunas, qualquer que seja o escopo.

    Raises:
        KeyError: o nome não aparece no documento.
    """
    for t in _TABELAS:
        if t.nome == nome:
            return t
    raise KeyError(
        f"{nome!r} não está em {SELECAO_TABELAS.name}. "
        f"Tabelas com escopo 'incluida': {FACT_TABLES}"
    )
