"""
Testes de src/splits.py.

O valor destes testes é negativo: eles existem para que a partição **falhe** em
vez de produzir silenciosamente um número bonito e errado. O modo de falha que
os motiva já ocorreu — `test()` avaliava sobre `train_mask` — e não deu erro
nenhum, só uma métrica otimista.
"""

from __future__ import annotations

import pytest

from src.splits import (
    ErroParticao,
    ParticaoTemporal,
    particionar,
    verificar_features_sem_vazamento,
    verificar_sem_vazamento,
)
from src.changes import Transicao
from src.extract import PERIODOS_ANUAIS

# A amostra canônica, lida de src/extract.py em vez de reescrita aqui: a série
# cresce um janeiro por ano (D-29), e uma lista duplicada neste arquivo passaria
# a testar uma amostra que não é mais a do projeto.
ANUAIS = list(PERIODOS_ANUAIS)


def destinos(grupo) -> list[str]:
    return [t.destino for t in grupo]


def test_particao_canonica_bate_com_a_metodologia():
    """A tabela da seção 6.1 de docs/02-metodologia.md, em código."""
    p = particionar(ANUAIS)

    assert destinos(p.treino) == [
        "201801", "201901", "202001", "202101", "202201", "202301",
    ]
    assert destinos(p.validacao) == ["202401", "202501"]
    assert destinos(p.teste) == ["202601"]
    assert p.fim_do_treino == "202301"


def test_corte_do_grafo_e_anterior_a_todos_os_rotulos():
    """
    O corte que um grafo estático precisa respeitar, e por que não é o mesmo
    que o das features.

    Com o grafo cortado em `fim_do_treino`, a transição de treino que termina
    naquele período tem o rótulo escrito no grafo: a aresta entre
    estabelecimento e equipamento em `t+1` é o alvo. Ver D-25.
    """
    p = particionar(ANUAIS)

    assert p.antes_de_todos_os_rotulos == "201701"
    assert p.antes_de_todos_os_rotulos < p.fim_do_treino

    # Nenhum destino de rótulo, em nenhum conjunto, pode ser visível no grafo.
    todos = p.treino + p.validacao + p.teste
    assert all(p.antes_de_todos_os_rotulos < t.destino for t in todos)


def test_n_snapshots_produzem_n_menos_uma_transicoes():
    """Nenhuma transição pode se perder ou ser contada duas vezes."""
    p = particionar(ANUAIS)
    total = len(p.treino) + len(p.validacao) + len(p.teste)
    assert total == len(ANUAIS) - 1


def test_particao_e_cronologica_nunca_sorteada():
    p = particionar(ANUAIS)
    assert max(destinos(p.treino)) < min(destinos(p.validacao))
    assert max(destinos(p.validacao)) < min(destinos(p.teste))


def test_conjunto_de_localiza_a_transicao():
    p = particionar(ANUAIS)
    assert p.conjunto_de(Transicao("201701", "201801")) == "treino"
    assert p.conjunto_de(Transicao(ANUAIS[-2], ANUAIS[-1])) == "teste"
    assert p.conjunto_de(Transicao("209901", "210001")) is None


def test_excluir_pandemia_descarta_transicoes_que_tocam_2020_ou_2021():
    """
    Toda transição com uma ponta em snapshot de pandemia sai, não só as que
    terminam nele. Filtrar apenas pelo destino deixaria 202101 -> 202201, que
    mede variação sobre uma base já distorcida pelo choque.
    """
    p = particionar(ANUAIS, excluir_pandemia=True)
    pares = [
        (t.origem, t.destino) for t in p.treino + p.validacao + p.teste
    ]

    assert pares == [
        ("201701", "201801"),
        ("201801", "201901"),
        ("202201", "202301"),
        ("202301", "202401"),
        ("202401", "202501"),
        ("202501", "202601"),
    ]
    assert not any("202001" in par or "202101" in par for par in pares)
    assert destinos(p.teste) == ["202601"]


def test_snapshots_insuficientes_sao_recusados():
    with pytest.raises(ErroParticao, match="ao menos 4 transições"):
        particionar(["201701", "201801", "201901"])


def test_mensagem_de_erro_menciona_a_exclusao_de_pandemia():
    """Sem isso o usuário não entende por que uma série que 'deveria dar' falhou."""
    with pytest.raises(ErroParticao, match="pandemia"):
        particionar(["201901", "202001", "202101", "202201", "202301"], excluir_pandemia=True)


def test_validacao_ou_teste_vazios_sao_recusados():
    with pytest.raises(ErroParticao, match="ao menos uma transição"):
        particionar(ANUAIS, n_teste=0)
    with pytest.raises(ErroParticao, match="ao menos uma transição"):
        particionar(ANUAIS, n_validacao=0)


def test_sobreposicao_entre_conjuntos_e_recusada():
    compartilhada = Transicao("202401", "202501")
    p = ParticaoTemporal(
        treino=(Transicao("201701", "201801"), compartilhada),
        validacao=(Transicao("202301", "202401"),),
        teste=(compartilhada,),
    )
    with pytest.raises(ErroParticao, match="ao mesmo tempo"):
        verificar_sem_vazamento(p)


def test_ordem_invertida_e_recusada():
    """Treinar no futuro e avaliar no passado é o vazamento mais grosseiro."""
    p = ParticaoTemporal(
        treino=(Transicao("202401", "202501"),),
        validacao=(Transicao("202301", "202401"),),
        teste=(Transicao("201701", "201801"),),
    )
    with pytest.raises(ErroParticao, match="passado precisa vir estritamente antes"):
        verificar_sem_vazamento(p)


def test_conjunto_vazio_e_recusado():
    p = ParticaoTemporal(
        treino=(Transicao("201701", "201801"),),
        validacao=(),
        teste=(Transicao("202401", "202501"),),
    )
    with pytest.raises(ErroParticao, match="está vazio"):
        verificar_sem_vazamento(p)


def test_transicao_repetida_no_mesmo_conjunto_e_recusada():
    repetida = Transicao("201701", "201801")
    p = ParticaoTemporal(
        treino=(repetida, repetida),
        validacao=(Transicao("202301", "202401"),),
        teste=(Transicao("202401", "202501"),),
    )
    with pytest.raises(ErroParticao, match="repete transições"):
        verificar_sem_vazamento(p)


def test_feature_lendo_alem_do_fim_do_treino_e_recusada():
    """
    O vazamento silencioso: rótulos divididos corretamente, mas features
    agregadas sobre a série inteira.
    """
    p = particionar(ANUAIS)

    verificar_features_sem_vazamento(p, ["201701", "202001", p.fim_do_treino])

    with pytest.raises(ErroParticao, match=r"posteriores ao fim da janela"):
        verificar_features_sem_vazamento(p, ["201701", p.fim_do_treino, ANUAIS[-1]])


def test_resumo_lista_os_tres_conjuntos():
    resumo = particionar(ANUAIS).resumo()
    for nome in ("treino", "validacao", "teste"):
        assert nome in resumo
    assert ANUAIS[-1] in resumo
