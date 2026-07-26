"""
Testes do formato de artefato de modelo.

O valor destes testes é negativo, como o do resto da suíte: eles existem para que
um pacote inconsistente **falhe** em vez de circular entre máquinas com métrica
que não corresponde à previsão salva. Ver D-35.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.ml.artefatos import (
    ErroArtefato,
    carregar_execucao,
    conferir,
    listar_execucoes,
    nome_de_execucao,
    recomputar_metricas,
    salvar_execucao,
)
from src.ml.baselines import Previsao
from src.ml.metrics import avaliar_classificacao


def previsao_sintetica(n: int = 400, semente: int = 7) -> Previsao:
    rng = np.random.default_rng(semente)
    entidades = rng.integers(0, 40, size=n).astype(np.int32)
    y = (rng.random(n) < 0.05).astype(np.int8)
    # Escore correlacionado com o rótulo, para que AP e MAP não fiquem degenerados.
    escore = (y * 0.6 + rng.random(n) * 0.4).astype(np.float32)
    return Previsao(
        modelo="sintetico",
        conjunto="teste",
        escore=escore,
        y=y,
        entidades=entidades,
        rotulos_entidade=np.array([f"u{i}" for i in range(40)]),
    )


def test_pacote_completo_ida_e_volta(tmp_path):
    previsao = previsao_sintetica()
    metricas = avaliar_classificacao(previsao.y, previsao.escore, previsao.entidades, k=10)

    destino = salvar_execucao(
        "baseline_sintetica",
        previsao,
        metricas,
        escopo="355030",
        modo="compativel",
        hiperparametros={"semente": 42},
        pasta_base=tmp_path,
    )

    lido = carregar_execucao(destino)
    assert lido.manifesto["trilha"] == "baseline_sintetica"
    assert lido.manifesto["escopo"] == "355030"
    assert lido.manifesto["modo"] == "compativel"
    assert lido.manifesto["n_exemplos"] == len(previsao.y)
    assert lido.previsoes().shape[0] == len(previsao.y)
    assert lido.previsoes(compactas=True).shape[0] <= len(previsao.y)


def test_metricas_do_manifesto_sao_recomputaveis(tmp_path):
    """
    O ponto do formato: quem recebe o pacote consegue verificar o número.

    Sem isto, "validar em qualquer dispositivo" seria aceitar a métrica por
    confiança — que é exatamente o modo de falha que D-11 documenta.
    """
    previsao = previsao_sintetica()
    metricas = avaliar_classificacao(previsao.y, previsao.escore, previsao.entidades, k=10)
    destino = salvar_execucao("gnn_falsa", previsao, metricas, pasta_base=tmp_path)

    recomputado = recomputar_metricas(destino)["teste_completo"]
    for chave in ("average_precision", "auc_roc", "map@10", "prevalencia"):
        assert recomputado[chave] == pytest.approx(metricas[chave], abs=1e-9)
    assert conferir(destino) == []


def test_manifesto_com_metrica_de_outra_execucao_e_denunciado(tmp_path):
    previsao = previsao_sintetica()
    metricas = avaliar_classificacao(previsao.y, previsao.escore, previsao.entidades, k=10)
    mentira = dict(metricas, average_precision=metricas["average_precision"] + 0.2)

    destino = salvar_execucao("gnn_falsa", previsao, mentira, pasta_base=tmp_path)
    problemas = conferir(destino)
    assert any("average_precision" in p for p in problemas)


def test_pesos_sem_indice_sao_recusados(tmp_path):
    """
    Um state_dict sem a ordem de unidades e itens carrega sem erro e pontua lixo.

    O embedding de item é indexado por posição: trocar a ordem entre a máquina que
    treinou e a que avalia não levanta exceção nenhuma, só devolve número errado.
    """
    import torch

    modelo = torch.nn.Linear(3, 1)
    previsao = previsao_sintetica()
    with pytest.raises(ErroArtefato, match="ordem"):
        salvar_execucao(
            "gnn_falsa",
            previsao,
            {},
            modelo=modelo,
            pasta_base=tmp_path,
        )


def test_indice_e_pesos_voltam_na_mesma_ordem(tmp_path):
    import torch

    modelo = torch.nn.Linear(4, 1)
    previsao = previsao_sintetica()
    unidades = [f"u{i}" for i in range(40)]
    itens = ["01", "02", "03"]

    destino = salvar_execucao(
        "gnn_falsa",
        previsao,
        {},
        modelo=modelo,
        unidades=unidades,
        itens_indice=itens,
        historico=pd.DataFrame({"epoca": [0, 1], "ap_validacao": [0.1, 0.2]}),
        pasta_base=tmp_path,
    )

    lido = carregar_execucao(destino)
    assert lido.indice()["unidades"] == unidades
    assert lido.indice()["itens"] == itens
    assert set(lido.pesos().keys()) == set(modelo.state_dict().keys())
    assert len(lido.historico()) == 2


def test_itens_desalinhados_com_a_previsao_falham(tmp_path):
    previsao = previsao_sintetica(n=100)
    with pytest.raises(ErroArtefato, match="mesma ordem|mesma fatia"):
        salvar_execucao(
            "gnn_falsa",
            previsao,
            {},
            itens_por_exemplo=np.zeros(99, dtype=np.int16),
            pasta_base=tmp_path,
        )


def test_pacote_sem_manifesto_nao_e_execucao(tmp_path):
    (tmp_path / "vazio").mkdir()
    with pytest.raises(ErroArtefato, match="não é um pacote"):
        carregar_execucao(tmp_path / "vazio")


def test_listagem_ordena_do_mais_recente(tmp_path):
    previsao = previsao_sintetica()
    salvar_execucao("a", previsao, {}, pasta_base=tmp_path, nome="2020-01-01-a")
    salvar_execucao("b", previsao, {}, pasta_base=tmp_path, nome="2026-01-01-b")
    nomes = [e.nome for e in listar_execucoes(tmp_path)]
    assert nomes == ["2026-01-01-b", "2020-01-01-a"]


def test_nome_de_execucao_separa_as_celulas_da_matriz():
    """
    Duas células de D-34 diferem apenas no modo; o nome precisa distingui-las,
    senão a segunda sobrescreve a primeira.
    """
    from datetime import date

    quando = date(2026, 7, 26)
    a = nome_de_execucao("gnn_relacional", "35", "compativel", quando)
    c = nome_de_execucao("gnn_relacional", "35", "completo", quando)
    d = nome_de_execucao("gnn_relacional", None, "completo", quando)
    assert a != c
    assert d.endswith("pais-completo")
