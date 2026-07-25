"""
Testes de src/changes.py.

O que precisa ser garantido, e por quê:

- A classificação inserida / removida / alterada tem que ser exata, porque o
  rótulo da tarefa primária de aquisição é derivado dela.
- Uma mudança apenas na coluna de auditoria não é evento. `dt_atualizacao` muda
  em recarga do banco de produção sem que nada de conteúdo mude; contá-la como
  evento inflaria a taxa de mudança e produziria rótulos falsos.
- Comparar um snapshot consigo mesmo tem que dar zero eventos. É o invariante
  mais barato que detecta erro de join, de nulo ou de projeção.
"""

from __future__ import annotations

import duckdb
import pytest

from src import changes
from tests.conftest import equipamento

TABELA = "rlEstabEquipamento"


@pytest.fixture
def con():
    with duckdb.connect() as c:
        yield c


def contagens(resumo: dict) -> tuple[int, int, int]:
    return resumo[changes.INSERIDA], resumo[changes.REMOVIDA], resumo[changes.ALTERADA]


def test_classifica_insercao_remocao_e_alteracao(con, camada_primaria):
    raiz, escrever = camada_primaria
    escrever(
        "201701",
        [
            equipamento("U1", "A"),
            equipamento("U1", "B", existente=2, uso=2),
            equipamento("U2", "C", tipo="2", sus="2", existente=5, uso=5),
        ],
    )
    escrever(
        "201801",
        [
            equipamento("U1", "A", atualizacao="09/09/2017"),
            equipamento("U1", "B", existente=7, uso=2, atualizacao="09/09/2017"),
            equipamento("U3", "D", atualizacao="09/09/2017"),
        ],
    )

    resumo = changes.diff_tabela(
        con, TABELA, changes.Transicao("201701", "201801"), raiz, raiz.parent / "changes"
    )

    # U3/D entrou, U2/C saiu, U1/B mudou de quantidade. U1/A só teve a data
    # de auditoria alterada e por isso não é evento.
    assert contagens(resumo) == (1, 1, 1)
    assert resumo["linhas_origem"] == 3
    assert resumo["linhas_destino"] == 3
    assert resumo["chave_declarada"] is True


def test_mudanca_apenas_de_auditoria_nao_e_evento(con, camada_primaria):
    raiz, escrever = camada_primaria
    escrever("201701", [equipamento("U1", "A", atualizacao="01/01/2017")])
    escrever("201801", [equipamento("U1", "A", atualizacao="31/12/2017")])

    resumo = changes.diff_tabela(
        con, TABELA, changes.Transicao("201701", "201801"), raiz, raiz.parent / "changes"
    )

    assert contagens(resumo) == (0, 0, 0)


def test_snapshot_contra_si_mesmo_nao_tem_eventos(con, camada_primaria):
    raiz, escrever = camada_primaria
    escrever(
        "201701",
        [
            equipamento("U1", "A"),
            equipamento("U1", "B", existente=9),
            equipamento("U2", "C", tipo="3"),
        ],
    )

    resumo = changes.diff_tabela(
        con, TABELA, changes.Transicao("201701", "201701"), raiz, raiz.parent / "changes"
    )

    assert contagens(resumo) == (0, 0, 0)


def test_chave_com_nulo_casa_em_vez_de_virar_remocao_e_insercao(con, camada_primaria):
    """
    Um nulo numa coluna da chave natural não pode quebrar o pareamento.

    Com `=` no lugar de `IS NOT DISTINCT FROM`, a linha não casaria consigo
    mesma e apareceria como uma remoção mais uma inserção — dois eventos falsos.
    """
    raiz, escrever = camada_primaria
    linha = equipamento("U1", "A")
    linha["tp_sus"] = None
    escrever("201701", [linha])
    escrever("201801", [dict(linha)])

    resumo = changes.diff_tabela(
        con, TABELA, changes.Transicao("201701", "201801"), raiz, raiz.parent / "changes"
    )

    assert contagens(resumo) == (0, 0, 0)


def test_tabela_ausente_no_destino_conta_tudo_como_remocao(con, camada_primaria):
    raiz, escrever = camada_primaria
    escrever("201701", [equipamento("U1", "A"), equipamento("U1", "B")])
    (raiz / "201801").mkdir(parents=True, exist_ok=True)  # snapshot sem a tabela

    resumo = changes.diff_tabela(
        con, TABELA, changes.Transicao("201701", "201801"), raiz, raiz.parent / "changes"
    )

    assert contagens(resumo) == (0, 2, 0)
    assert resumo["linhas_destino"] == 0


def test_tabela_ausente_na_origem_conta_tudo_como_insercao(con, camada_primaria):
    raiz, escrever = camada_primaria
    (raiz / "201701").mkdir(parents=True, exist_ok=True)
    escrever("201801", [equipamento("U1", "A")])

    resumo = changes.diff_tabela(
        con, TABELA, changes.Transicao("201701", "201801"), raiz, raiz.parent / "changes"
    )

    assert contagens(resumo) == (1, 0, 0)


def test_tabela_ausente_nos_dois_lados_devolve_none(con, camada_primaria):
    raiz, _ = camada_primaria
    (raiz / "201701").mkdir(parents=True, exist_ok=True)
    (raiz / "201801").mkdir(parents=True, exist_ok=True)

    resumo = changes.diff_tabela(
        con, TABELA, changes.Transicao("201701", "201801"), raiz, raiz.parent / "changes"
    )

    assert resumo is None


def test_eventos_materializados_carregam_valores_do_lado_correto(con, camada_primaria):
    """
    Remoção precisa carregar os valores da origem; inserção, os do destino.

    Sem isso a linha removida sairia com todas as colunas nulas, e o evento
    perderia a informação do que exatamente deixou de existir.
    """
    raiz, escrever = camada_primaria
    saida_raiz = raiz.parent / "changes"
    escrever("201701", [equipamento("U2", "C", existente=5)])
    escrever("201801", [equipamento("U3", "D", existente=8)])

    changes.diff_tabela(
        con, TABELA, changes.Transicao("201701", "201801"), raiz, saida_raiz
    )

    linhas = con.execute(
        f"SELECT co_unidade, qt_existente, evento "
        f"FROM read_parquet('{saida_raiz / TABELA / '201801.parquet'}') "
        f"ORDER BY evento"
    ).fetchall()

    assert linhas == [("U3", 8, changes.INSERIDA), ("U2", 5, changes.REMOVIDA)]


def test_transicoes_sao_pares_consecutivos():
    assert changes.transicoes([]) == []
    assert changes.transicoes(["201701"]) == []
    assert [str(t) for t in changes.transicoes(["201701", "201801", "201901"])] == [
        "201701->201801",
        "201801->201901",
    ]


def test_detectar_mudancas_exige_dois_snapshots(camada_primaria):
    raiz, escrever = camada_primaria
    escrever("201701", [equipamento("U1", "A")])

    with pytest.raises(ValueError, match="ao menos dois snapshots"):
        changes.detectar_mudancas(pasta_entrada=raiz, pasta_saida=raiz.parent / "changes")


def test_detectar_mudancas_recusa_tabela_fora_de_escopo(camada_primaria):
    raiz, escrever = camada_primaria
    escrever("201701", [equipamento("U1", "A")])
    escrever("201801", [equipamento("U1", "A")])

    with pytest.raises(ValueError, match="fora do escopo"):
        changes.detectar_mudancas(
            tabelas=["rlEstabTeleCnes"],
            pasta_entrada=raiz,
            pasta_saida=raiz.parent / "changes",
        )


def test_taxa_de_mudanca_agrega_o_resumo(camada_primaria):
    raiz, escrever = camada_primaria
    saida = raiz.parent / "changes"
    escrever("201701", [equipamento("U1", "A"), equipamento("U1", "B")])
    escrever("201801", [equipamento("U1", "A"), equipamento("U9", "Z")])

    changes.detectar_mudancas(
        tabelas=[TABELA], pasta_entrada=raiz, pasta_saida=saida
    )
    df = changes.taxa_de_mudanca(saida / "_resumo.parquet")

    assert len(df) == 1
    linha = df.iloc[0]
    assert linha["tabela"] == TABELA
    assert linha["periodo_destino"] == "201801"
    # U1/B saiu e U9/Z entrou: 2 eventos sobre 2 linhas de base.
    assert linha["eventos"] == 2
    assert linha["taxa_mudanca"] == pytest.approx(1.0)
