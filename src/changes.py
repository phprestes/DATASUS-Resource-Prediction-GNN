"""
Detecção de mudança entre snapshots consecutivos do CNES.

Este módulo existe porque um ZIP de competência é uma **fotografia do estado
atual** do banco de produção, não um log de eventos. Para cada linha ele traz
apenas a última `dt_atualizacao`, o que faz de
`to_chardt_atualizacaoddmmyyyy` um valor censurado à direita: informa quando a
linha mudou por último antes da extração, não a história dela. Usá-la
diretamente como eixo temporal de um grafo atribui a cada linha um instante que
depende de quando o snapshot foi tirado.

A unidade de análise é portanto a **transição** entre dois snapshots, e não a
linha. Comparando 01/2019 com 01/2020 recupera-se o que de fato entrou, saiu ou
mudou no intervalo — e é isso que gera exemplo de treino. Mudanças
intermediárias, como um equipamento adquirido e removido dentro do mesmo
intervalo, são irrecuperáveis por construção.

Implementa também o filtro "somente linhas que sofreram alteração" previsto no
projeto original, agora como consequência dessa definição.

Ver docs/02-metodologia.md, seção 4, e docs/03-decisoes.md, D-08.

Uso:
    python -m src.changes                    # todas as transições disponíveis
    python -m src.changes --tabelas rlEstabEquipamento
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

import duckdb
import pyarrow as pa
from tqdm import tqdm

from src.paths import CHANGES_FOLDER, PRIMARY_FOLDER
from src.schema import CNES_EXTRACT_COLUMNS, CNES_NATURAL_KEY

# Classificação de cada linha numa transição.
INSERIDA = "inserida"
REMOVIDA = "removida"
ALTERADA = "alterada"

# Colunas de auditoria: mudam junto com qualquer alteração de conteúdo, e às
# vezes mudam sozinhas por recarga do banco de produção. Ficam de fora da
# comparação de valores para que `alterada` signifique mudança de conteúdo real,
# mas seguem presentes na saída.
AUDITORIA = re.compile(r"^to_char.*dt_atualizacao|^co_usuario$|^nu_seq_processo$")

NOME_RESUMO = "_resumo.parquet"
RESUMO = CHANGES_FOLDER / NOME_RESUMO


def caminho_resumo(pasta_saida: Path = CHANGES_FOLDER) -> Path:
    """Onde vive o resumo de uma dada pasta de eventos."""
    return pasta_saida / NOME_RESUMO


@dataclass(frozen=True)
class Transicao:
    """Um par de snapshots consecutivos, rotulado pelo período de destino."""

    origem: str
    destino: str

    def __str__(self) -> str:
        return f"{self.origem}->{self.destino}"


def periodos_disponiveis(pasta: Path = PRIMARY_FOLDER) -> list[str]:
    """Competências com Parquet na camada primária, em ordem cronológica."""
    return sorted(p.name for p in pasta.iterdir() if p.is_dir() and p.name.isdigit())


def transicoes(periodos: list[str]) -> list[Transicao]:
    """
    Pares consecutivos. N snapshots produzem N-1 transições.

    Consecutivos na lista fornecida, não no calendário: se a série tem lacunas,
    a transição atravessa a lacuna e a interpretação disso é do chamador.
    """
    return [Transicao(a, b) for a, b in zip(periodos, periodos[1:])]


def _colunas_do_parquet(con: duckdb.DuckDBPyConnection, caminho: Path) -> list[str]:
    return [
        r[0]
        for r in con.execute(
            f"DESCRIBE SELECT * FROM read_parquet('{caminho}')"
        ).fetchall()
    ]


def _chave_de(tabela: str, colunas: list[str]) -> tuple[list[str], bool]:
    """
    Resolve a chave de linha da tabela, e diz se ela foi declarada.

    Sem chave natural declarada em docs/01-selecao-tabelas.md, cai para a tupla
    inteira de colunas não-auditoria. Nesse modo não se distingue modificação de
    remoção-mais-inserção, e a taxa de mudança sai inflada — o chamador precisa
    saber disso, daí o segundo valor de retorno.
    """
    declarada = [c for c in CNES_NATURAL_KEY.get(tabela, ()) if c in colunas]
    if declarada:
        return declarada, True
    return [c for c in colunas if not AUDITORIA.match(c)], False


def _sql_lista(colunas: list[str], prefixo: str = "") -> str:
    p = f"{prefixo}." if prefixo else ""
    return ", ".join(f'{p}"{c}"' for c in colunas)


def diff_tabela(
    con: duckdb.DuckDBPyConnection,
    tabela: str,
    transicao: Transicao,
    pasta_entrada: Path = PRIMARY_FOLDER,
    pasta_saida: Path = CHANGES_FOLDER,
    reprocess: bool = False,
) -> dict[str, int] | None:
    """
    Compara uma tabela entre dois snapshots e materializa os eventos de mudança.

    Escreve `{pasta_saida}/{tabela}/{destino}.parquet` com as colunas da chave,
    a classificação do evento e os valores do snapshot de destino — ou do de
    origem, no caso de remoção. Devolve a contagem por classificação, ou None se
    a tabela não existe em nenhum dos dois snapshots.

    Linhas inalteradas não são escritas: são a maioria absoluta e não constituem
    evento. A contagem delas volta no resumo, para que a taxa de mudança seja
    calculável.
    """
    origem = pasta_entrada / transicao.origem / f"{tabela}.parquet"
    destino = pasta_entrada / transicao.destino / f"{tabela}.parquet"
    if not origem.exists() and not destino.exists():
        return None

    # A tabela pode faltar num dos lados: tbEstabAtivSecundaria tem 0 linhas em
    # 201701 e 713.614 em 202501. O lado ausente vira um SELECT do lado presente
    # com WHERE FALSE — zero linhas, mas o mesmo schema, o que mantém os tipos
    # do join corretos. Tudo então conta como inserção, ou como remoção.
    presente = origem if origem.exists() else destino
    # A comparação usa só as colunas presentes nos **dois** lados. Três tabelas
    # têm colunas que somem e voltam entre competências (D-20), e tomar a lista
    # de um lado só faz o SELECT do outro referenciar coluna inexistente: o diff
    # morria com Binder Error e a transição desaparecia do resumo sem que a taxa
    # de mudança acusasse falta. Comparar a interseção é o que dá para afirmar —
    # uma coluna que não existe num dos snapshots não mudou nem deixou de mudar.
    presentes_nos_dois = set(_colunas_do_parquet(con, presente))
    if origem.exists() and destino.exists():
        presentes_nos_dois &= set(_colunas_do_parquet(con, destino))
        presentes_nos_dois &= set(_colunas_do_parquet(con, origem))
    colunas = [
        c
        for c in _colunas_do_parquet(con, presente)
        if c in CNES_EXTRACT_COLUMNS[tabela] and c in presentes_nos_dois
    ]
    chave, chave_declarada = _chave_de(tabela, colunas)
    valores = [c for c in colunas if c not in chave and not AUDITORIA.match(c)]

    def fonte(caminho: Path, marca: str) -> str:
        alvo = caminho if caminho.exists() else presente
        vazio = "" if caminho.exists() else " WHERE FALSE"
        return (
            f"SELECT {_sql_lista(colunas)}, TRUE AS {marca} "
            f"FROM read_parquet('{alvo}'){vazio}"
        )

    saida = pasta_saida / tabela / f"{transicao.destino}.parquet"
    if not saida.exists() or reprocess:
        saida.parent.mkdir(parents=True, exist_ok=True)

        # IS NOT DISTINCT FROM em vez de =: nulos precisam casar entre si, senão
        # toda linha com nulo na chave sairia como removida e reinserida.
        on = " AND ".join(f'a."{c}" IS NOT DISTINCT FROM b."{c}"' for c in chave)
        difere = (
            " OR ".join(f'a."{c}" IS DISTINCT FROM b."{c}"' for c in valores)
            if valores
            else "FALSE"
        )
        # A presença é detectada por coluna sentinela, não por nulo na chave:
        # uma linha real com chave nula existe, e testar a chave a classificaria
        # como inserção mesmo quando ela casou com o outro lado.
        projecao = ", ".join(
            f'COALESCE(b."{c}", a."{c}") AS "{c}"' for c in colunas
        )

        query = f"""
            WITH a AS ({fonte(origem, "_em_a")}),
                 b AS ({fonte(destino, "_em_b")})
            SELECT {projecao},
                   CASE
                       WHEN a._em_a IS NULL THEN '{INSERIDA}'
                       WHEN b._em_b IS NULL THEN '{REMOVIDA}'
                       ELSE '{ALTERADA}'
                   END AS evento,
                   '{transicao.origem}' AS periodo_origem,
                   '{transicao.destino}' AS periodo_destino
            FROM a FULL OUTER JOIN b ON {on}
            WHERE a._em_a IS NULL OR b._em_b IS NULL OR ({difere})
        """
        con.execute(f"COPY ({query}) TO '{saida}' (FORMAT 'parquet')")

    # O resumo é recalculado mesmo quando o diff foi reaproveitado, para que
    # _resumo.parquet fique completo depois de uma execução incremental.
    contagem = dict(
        con.execute(
            f"SELECT evento, COUNT(*) FROM read_parquet('{saida}') GROUP BY evento"
        ).fetchall()
    )
    return {
        "tabela": tabela,
        "periodo_origem": transicao.origem,
        "periodo_destino": transicao.destino,
        "chave_declarada": chave_declarada,
        "linhas_origem": _contar(con, origem),
        "linhas_destino": _contar(con, destino),
        INSERIDA: contagem.get(INSERIDA, 0),
        REMOVIDA: contagem.get(REMOVIDA, 0),
        ALTERADA: contagem.get(ALTERADA, 0),
    }


def _contar(con: duckdb.DuckDBPyConnection, caminho: Path) -> int:
    if not caminho.exists():
        return 0
    return con.execute(
        f"SELECT COUNT(*) FROM read_parquet('{caminho}')"
    ).fetchone()[0]


def detectar_mudancas(
    periodos: list[str] | None = None,
    tabelas: list[str] | None = None,
    pasta_entrada: Path = PRIMARY_FOLDER,
    pasta_saida: Path = CHANGES_FOLDER,
    reprocess: bool = False,
) -> "list[dict]":
    """
    Roda o diff para todas as transições e tabelas pedidas.

    Acumula um resumo em `_resumo.parquet`, que é a base do cálculo de taxa de
    mudança usado para decidir a densidade de snapshots (D-10).
    """
    periodos = periodos or periodos_disponiveis(pasta_entrada)
    if len(periodos) < 2:
        raise ValueError(
            f"detecção de mudança precisa de ao menos dois snapshots; "
            f"encontrados {len(periodos)} em {pasta_entrada}. Rode o ETL antes."
        )

    tabelas = tabelas or sorted(CNES_EXTRACT_COLUMNS)
    desconhecidas = [t for t in tabelas if t not in CNES_EXTRACT_COLUMNS]
    if desconhecidas:
        raise ValueError(
            f"tabelas fora do escopo declarado em docs/01-selecao-tabelas.md: "
            f"{desconhecidas}"
        )

    pasta_saida.mkdir(parents=True, exist_ok=True)
    resumo: list[dict] = []

    with duckdb.connect() as con:
        pares = [(t, tr) for tr in transicoes(periodos) for t in tabelas]
        for tabela, transicao in tqdm(pares, desc="Detectando mudanças"):
            try:
                linha = diff_tabela(
                    con, tabela, transicao, pasta_entrada, pasta_saida, reprocess
                )
            except Exception as e:
                tqdm.write(f"[ERRO] {tabela} em {transicao}: {e}")
                continue
            if linha:
                resumo.append(linha)

        if resumo:
            destino = caminho_resumo(pasta_saida)
            con.register("resumo_novo", pa.Table.from_pylist(resumo))
            # Acumula em vez de sobrescrever, para que execuções parciais
            # (--tabelas, --periodos) somem ao resumo em vez de apagá-lo.
            # taxa_de_mudanca() desempata mantendo a última entrada de cada par.
            consulta = (
                f"SELECT * FROM read_parquet('{destino}') "
                "UNION ALL BY NAME SELECT * FROM resumo_novo"
                if destino.exists()
                else "SELECT * FROM resumo_novo"
            )
            temporario = destino.with_suffix(".parquet.tmp")
            con.execute(f"COPY ({consulta}) TO '{temporario}' (FORMAT 'parquet')")
            temporario.replace(destino)

    return resumo


def taxa_de_mudanca(caminho: Path | None = None):
    """
    Taxa de mudança por tabela e transição, a partir do resumo materializado.

    É o insumo da decisão sobre densidade de snapshots: se a taxa anual for
    alta, um ano de intervalo esconde ciclos e a série precisa ser densificada.

    A coluna `chave_declarada` importa na leitura. Onde ela é falsa, a tabela não
    tem chave natural declarada, cada modificação conta como uma remoção mais
    uma inserção, e a taxa está superestimada.
    """
    import pandas as pd

    caminho = caminho or caminho_resumo()
    if not caminho.exists():
        raise FileNotFoundError(
            f"{caminho} não existe. Rode `python -m src.changes` antes."
        )

    df = pd.read_parquet(caminho)
    df = df.drop_duplicates(
        subset=["tabela", "periodo_origem", "periodo_destino"], keep="last"
    )
    df["eventos"] = df[INSERIDA] + df[REMOVIDA] + df[ALTERADA]
    base = df[["linhas_origem", "linhas_destino"]].max(axis=1)
    df["taxa_mudanca"] = (df["eventos"] / base.where(base > 0)).fillna(0.0)
    return df.sort_values(["tabela", "periodo_destino"]).reset_index(drop=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tabelas", nargs="*", help="subconjunto de tabelas")
    ap.add_argument("--periodos", nargs="*", help="subconjunto de competências")
    ap.add_argument(
        "--reprocess", action="store_true", help="recalcula diffs já materializados"
    )
    args = ap.parse_args()

    disponiveis = args.periodos or periodos_disponiveis()
    print(f"Snapshots: {disponiveis}")
    print(f"Transições: {[str(t) for t in transicoes(disponiveis)]}")

    resumo = detectar_mudancas(
        periodos=args.periodos, tabelas=args.tabelas, reprocess=args.reprocess
    )
    print(f"\n{len(resumo)} pares (tabela, transição) processados.")

    if resumo:
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
