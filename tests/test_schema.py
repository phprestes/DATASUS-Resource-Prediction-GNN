"""
Testes de src/config/schema.py.

Duas famílias de garantia:

1. **O doc real é válido e consistente.** docs/01-selecao-tabelas.md é a fonte da
   verdade do pipeline; se ele estiver malformado o import falha, e é melhor que
   falhe aqui.
2. **O parser recusa o que deve recusar.** Cada validação existe por causa de um
   modo de falha concreto — a maioria deles já ocorreu no projeto. Um parser
   permissivo reintroduziria exatamente o problema que a refatoração eliminou:
   um schema silenciosamente incompleto.
"""

from __future__ import annotations

import pytest

from src.config import schema
from src.config.schema import ErroSchema

# Um doc mínimo mas bem formado, base das variações de erro abaixo.
DOC_VALIDO = """# Seleção

## Tabelas

### tbEstabelecimento

- **Dicionário:** `TB_ESTABELECIMENTO` — Estabelecimentos
- **Escopo:** incluida
- **Chave primária:** `co_unidade`

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | justificativa |
|---|---|---|---|---|---|---|
| `co_unidade` | VARCHAR2(31) | string | util | sim | - | chave |
| `tp_gestao` | CHAR(1) | category | util | - | - | gestão |
| `no_fantasia` | VARCHAR2(60) | string | descartada | - | - | filtro semântico |

### rlEstabEquipamento

- **Dicionário:** `RL_ESTAB_EQUIPAMENTO` — Equipamentos
- **Escopo:** incluida
- **Chave primária:** `co_unidade`
- **Chave natural:** `co_unidade`, `co_equipamento`

| coluna | tipo_origem | dtype | classificacao | pkey | fkey_para | justificativa |
|---|---|---|---|---|---|---|
| `co_unidade` | VARCHAR2(31) | string | util | sim | `tbEstabelecimento` | fkey |
| `co_equipamento` | CHAR(2) | category | util | - | - | tipo |
| `qt_existente` | NUMBER(3) | Int64 | util | - | - | quantidade |
"""


def parse(texto: str):
    tabelas, fora = schema._parse(texto, "teste.md")
    schema._validar(tabelas, "teste.md")
    return tabelas, fora


# ---------------------------------------------------------------------------
# O documento real
# ---------------------------------------------------------------------------


def test_doc_real_carrega_e_valida():
    tabelas, _ = schema.carregar()
    assert tabelas, "docs/01-selecao-tabelas.md não produziu nenhuma tabela"


def test_fact_tables_e_useful_columns_nao_podem_divergir():
    """
    O bug estrutural que a refatoração eliminou.

    Antes, FACT_TABLES tinha 57 tabelas e CNES_USEFUL_COLUMNS tinha 44: as 13
    restantes eram baixadas, extraídas e descartadas em silêncio na conversão
    para Parquet. Agora as duas são projeções da mesma tabela Markdown, e a
    divergência é impossível por construção — este teste é o que garante que
    continua impossível.
    """
    assert set(schema.FACT_TABLES) == set(schema.CNES_USEFUL_COLUMNS)


def test_toda_tabela_incluida_tem_coluna_materializavel():
    vazias = [t for t, cols in schema.CNES_EXTRACT_COLUMNS.items() if not cols]
    assert not vazias, f"tabelas incluídas sem coluna aproveitável: {vazias}"


def test_toda_tabela_de_fato_tem_chave_natural():
    """
    D-38: identificar a linha é imprescindível, e toda tabela do dicionário tem
    PRIMARY KEY.

    Sem chave natural, `src/etl/changes.py` cai no modo por tupla inteira, em que
    modificação conta como remoção mais inserção e a taxa de mudança sai inflada.
    Duas tabelas ficaram nesse modo entre D-27 e D-38 porque a identidade delas
    dependia de coluna que o filtro semântico havia descartado — descartar do
    Parquet e descartar da identidade da linha são decisões separadas.
    """
    sem_chave = [t for t in schema.FACT_TABLES if not schema.CNES_NATURAL_KEY.get(t)]
    assert not sem_chave, f"tabelas de fato sem chave natural declarada: {sem_chave}"


def test_chave_natural_e_subconjunto_das_colunas_materializadas():
    """
    A chave só serve se as colunas dela chegarem ao Parquet.

    `_validar` já recusa chave que cite coluna inexistente na tabela; este teste
    fecha o caso adjacente, o de coluna que existe no dicionário mas foi
    descartada e portanto não é materializada — foi o que impediu de declarar a
    chave de `rlEstabServClass` até `co_end_compl` voltar a `util` (D-38).
    """
    for tabela in schema.FACT_TABLES:
        materializadas = set(schema.CNES_EXTRACT_COLUMNS[tabela])
        fora = [c for c in schema.CNES_NATURAL_KEY[tabela] if c not in materializadas]
        assert not fora, f"{tabela}: chave natural fora do Parquet: {fora}"


def test_chaves_estrangeiras_apontam_para_tabelas_incluidas():
    """
    Reproduz D-14: rlEstabEqpUnidApoio apontava para rlEstabEndCompl, que não
    era materializada, e o grafo entregue ao RelBench saía com referência
    pendurada.
    """
    incluidas = set(schema.FACT_TABLES)
    penduradas = [
        f"{tabela}.{coluna} -> {destino}"
        for tabela, fkeys in schema.CNES_FKEY.items()
        for coluna, destino in fkeys.items()
        if destino not in incluidas
    ]
    assert not penduradas


def test_chave_primaria_esta_entre_as_colunas_materializadas():
    for tabela, pkey in schema.CNES_PKEY.items():
        assert pkey in schema.CNES_EXTRACT_COLUMNS[tabela], (
            f"{tabela}: chave primária {pkey!r} não é coluna materializada"
        )


def test_dtypes_cobrem_exatamente_as_colunas_materializadas():
    for tabela, colunas in schema.CNES_EXTRACT_COLUMNS.items():
        assert set(schema.CNES_DTYPES[tabela]) == set(colunas)


def test_useful_columns_e_subconjunto_de_extract_columns():
    """
    Colunas `pendente` são materializadas para poderem ser medidas, mas não
    entram na modelagem. A inclusão nunca pode se inverter.
    """
    for tabela, uteis in schema.CNES_USEFUL_COLUMNS.items():
        assert set(uteis) <= set(schema.CNES_EXTRACT_COLUMNS[tabela])


def test_tabelas_fora_de_escopo_tem_motivo_escrito():
    assert schema.TABELAS_FORA, "esperado ao menos uma tabela fora de escopo"
    sem_motivo = [t for t, motivo in schema.TABELAS_FORA.items() if not motivo.strip()]
    assert not sem_motivo


def test_tabelas_fora_nao_entram_em_fact_tables():
    assert not set(schema.TABELAS_FORA) & set(schema.FACT_TABLES)


def test_acesso_a_tabela_desconhecida_lista_as_validas():
    with pytest.raises(KeyError, match="incluida"):
        schema.tabela("tabelaQueNaoExiste")


# ---------------------------------------------------------------------------
# O parser
# ---------------------------------------------------------------------------


def test_parse_do_doc_minimo():
    tabelas, _ = parse(DOC_VALIDO)

    assert [t.nome for t in tabelas] == ["tbEstabelecimento", "rlEstabEquipamento"]

    estab = tabelas[0]
    assert estab.nome_dicionario == "TB_ESTABELECIMENTO"
    assert estab.pkey == "co_unidade"
    assert estab.por_classificacao("util") == ["co_unidade", "tp_gestao"]
    assert estab.chave_natural == ()

    equip = tabelas[1]
    assert equip.chave_natural == ("co_unidade", "co_equipamento")
    assert equip.colunas[0].fkey_para == "tbEstabelecimento"
    assert equip.colunas[2].dtype == "Int64"


def test_cabecalho_do_doc_nao_e_confundido_com_schema():
    """
    O cabeçalho do doc real tem tabelas Markdown que documentam vocabulário e
    escopo. Só o que vem depois de `## Tabelas` descreve schema.
    """
    preambulo = """# Seleção

## Critério

| valor | significado |
|---|---|
| `util` | passou nos dois filtros |

### Tabelas fora de escopo

| tabela | motivo |
|---|---|
| `rlEstabTeleCnes` | todas as colunas são Não Útil |

"""
    tabelas, fora = parse(preambulo + DOC_VALIDO)
    assert [t.nome for t in tabelas] == ["tbEstabelecimento", "rlEstabEquipamento"]
    assert fora == {"rlEstabTeleCnes": "todas as colunas são Não Útil"}


def test_doc_sem_secao_de_tabelas_e_recusado():
    with pytest.raises(ErroSchema, match="nenhuma tabela encontrada"):
        parse("# Seleção\n\nsó prosa, nenhuma tabela.\n")


def test_cabecalho_de_tabela_incompleto_e_recusado():
    texto = DOC_VALIDO.replace("| coluna | tipo_origem |", "| coluna | tipo_de_dado |", 1)
    with pytest.raises(ErroSchema, match="não tem as colunas"):
        parse(texto)


def test_classificacao_invalida_e_recusada():
    texto = DOC_VALIDO.replace("| util | sim | - | chave |", "| talvez | sim | - | chave |", 1)
    with pytest.raises(ErroSchema, match="classificacao"):
        parse(texto)


def test_escopo_invalido_e_recusado():
    texto = DOC_VALIDO.replace("**Escopo:** incluida", "**Escopo:** talvez", 1)
    with pytest.raises(ErroSchema, match="escopo"):
        parse(texto)


def test_linha_com_numero_errado_de_celulas_e_recusada():
    texto = DOC_VALIDO.replace(
        "| `tp_gestao` | CHAR(1) | category | util | - | - | gestão |",
        "| `tp_gestao` | CHAR(1) | category | util | - | gestão |",
        1,
    )
    with pytest.raises(ErroSchema, match="células"):
        parse(texto)


def test_tabela_declarada_duas_vezes_e_recusada():
    texto = DOC_VALIDO + DOC_VALIDO.split("## Tabelas", 1)[1]
    with pytest.raises(ErroSchema, match="declarada duas vezes"):
        parse(texto)


def test_coluna_repetida_na_mesma_tabela_e_recusada():
    texto = DOC_VALIDO.replace(
        "| `tp_gestao` | CHAR(1) | category | util | - | - | gestão |",
        "| `tp_gestao` | CHAR(1) | category | util | - | - | gestão |\n"
        "| `tp_gestao` | CHAR(1) | category | util | - | - | duplicada |",
        1,
    )
    with pytest.raises(ErroSchema, match="repete as colunas"):
        parse(texto)


def test_chave_primaria_inexistente_e_recusada():
    texto = DOC_VALIDO.replace("**Chave primária:** `co_unidade`", "**Chave primária:** `co_xyz`", 1)
    with pytest.raises(ErroSchema, match="chave primária"):
        parse(texto)


def test_chave_natural_citando_coluna_inexistente_e_recusada():
    texto = DOC_VALIDO.replace(
        "**Chave natural:** `co_unidade`, `co_equipamento`",
        "**Chave natural:** `co_unidade`, `co_inexistente`",
        1,
    )
    with pytest.raises(ErroSchema, match="chave natural"):
        parse(texto)


def test_chave_estrangeira_para_tabela_fora_de_escopo_e_recusada():
    texto = DOC_VALIDO.replace("| util | - | - | tipo |", "| util | - | `rlEstabEndCompl` | tipo |", 1)
    with pytest.raises(ErroSchema, match="não é uma tabela com escopo"):
        parse(texto)


def test_tabela_incluida_sem_coluna_aproveitavel_e_recusada():
    """
    Silêncio deixa de ser opção: uma tabela sem coluna útil precisa declarar
    escopo 'fora' com motivo, em vez de ser ingerida e descartada depois.
    """
    texto = DOC_VALIDO.replace("| util |", "| descartada |")
    with pytest.raises(ErroSchema, match="nenhuma coluna 'util' ou 'pendente'"):
        parse(texto)


def test_colunas_pendentes_sao_materializadas_mas_nao_uteis():
    texto = DOC_VALIDO.replace(
        "| `tp_gestao` | CHAR(1) | category | util | - | - | gestão |",
        "| `tp_gestao` | CHAR(1) | category | pendente | - | - | sem medição |",
        1,
    )
    tabelas, _ = parse(texto)
    estab = tabelas[0]

    assert estab.por_classificacao("util") == ["co_unidade"]
    assert estab.por_classificacao("util", "pendente") == ["co_unidade", "tp_gestao"]
    assert [c.nome for c in estab.colunas if c.materializar] == ["co_unidade", "tp_gestao"]


def test_erro_de_parse_nomeia_arquivo_e_linha():
    texto = DOC_VALIDO.replace("| util | sim | - | chave |", "| inventada | sim | - | chave |", 1)
    with pytest.raises(ErroSchema) as erro:
        parse(texto)
    assert "teste.md:" in str(erro.value)
