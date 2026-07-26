"""
Testes do grafo por transição e do laço de treino, com dado sintético.

**Sintético por obrigação, não por conveniência.** O pipeline de `hpc/` é
dimensionado para 440 GB; exercitá-lo com a camada primária real nesta máquina de
9 GB esgota a memória do sistema e do editor — já aconteceu. Aqui os grafos têm
dezenas de nós, e o que se verifica é a lógica: que nenhum grafo alcança o destino
da transição que serve, que o peso da aresta chega ao modelo, e que o treino
seleciona época pela validação.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import torch
from torch_geometric.data import HeteroData

from hpc.ml import grafo_temporal, treino
from src.etl.changes import Transicao
from src.ml.gnn import IndicePares
from src.ml.graph import TABELA_RAIZ
from src.ml.splits import ParticaoTemporal
from src.ml.tasks import COL_CONJUNTO, COL_ENTIDADE, COL_ROTULO, TabelaTarefa

N_UNIDADES = 24
N_ITENS = 5
ORIGENS = ["201701", "201801", "201901", "202001"]


def grafo_falso(ate_periodo: str, n_categorias: int = N_ITENS, com_peso: bool = True):
    """Grafo minúsculo com uma relação, no formato que `treino` espera."""
    torch.manual_seed(0)
    dados = HeteroData()
    dados[TABELA_RAIZ].x = torch.randn(N_UNIDADES, 4)
    dados["equipamento"].x = torch.randn(n_categorias, 3)

    origem = torch.arange(N_UNIDADES) % N_UNIDADES
    destino = torch.arange(N_UNIDADES) % n_categorias
    ida = (TABELA_RAIZ, "tem", "equipamento")
    volta = ("equipamento", "em", TABELA_RAIZ)
    dados[ida].edge_index = torch.stack([origem, destino])
    dados[volta].edge_index = torch.stack([destino, origem])
    if com_peso:
        peso = torch.rand(N_UNIDADES)
        dados[ida].edge_weight = peso
        dados[volta].edge_weight = peso
    dados.resumo_arestas = {"equipamento": N_UNIDADES}
    dados.ate_periodo = ate_periodo
    return dados


def grafos_falsos(origens=ORIGENS, com_peso: bool = True):
    unidades = [f"u{i:03d}" for i in range(N_UNIDADES)]
    grafos = grafo_temporal.GrafoPorTransicao(unidades=unidades)
    for origem in origens:
        grafos.por_origem[origem] = grafo_falso(origem, com_peso=com_peso)
        grafos.resumo[origem] = {"tipos_no": 2, "relacoes": 2, "arestas": N_UNIDADES}
    return grafos


def tarefa_falsa(particao: ParticaoTemporal) -> TabelaTarefa:
    """Tarefa sintética com uma fatia por transição e sinal aprendível."""
    rng = np.random.default_rng(7)
    linhas = []
    for conjunto, grupo in particao.conjuntos.items():
        for transicao in grupo:
            for u in range(N_UNIDADES):
                for k in range(N_ITENS):
                    # Sinal simples: itens de índice baixo em unidades de índice
                    # baixo são positivos com mais frequência.
                    p = 0.5 if (u + k) < 6 else 0.02
                    linhas.append(
                        {
                            COL_ENTIDADE: f"u{u:03d}",
                            "co_equipamento": f"{k:02d}",
                            COL_ROTULO: int(rng.random() < p),
                            COL_CONJUNTO: conjunto,
                            "periodo_origem": transicao.origem,
                            "periodo_destino": transicao.destino,
                        }
                    )
    df = pd.DataFrame(linhas)
    df[COL_ENTIDADE] = df[COL_ENTIDADE].astype("category")
    df["co_equipamento"] = df["co_equipamento"].astype("category")
    return TabelaTarefa(
        df=df,
        nome="sintetica",
        tipo="classificacao_binaria",
        col_entidade=COL_ENTIDADE,
        col_item="co_equipamento",
        col_rotulo=COL_ROTULO,
    )


@pytest.fixture()
def particao() -> ParticaoTemporal:
    return ParticaoTemporal(
        treino=(Transicao("201701", "201801"), Transicao("201801", "201901")),
        validacao=(Transicao("201901", "202001"),),
        teste=(Transicao("202001", "202101"),),
    )


def test_cada_grafo_e_cortado_na_origem_da_transicao(particao):
    """
    A garantia de D-25 traduzida para o grafo por transição.

    O grafo pode ser contemporâneo da **origem**, nunca do destino: a aresta
    estabelecimento-item em t+1 é o próprio rótulo.
    """
    grafos = grafos_falsos()
    todas = list(particao.treino + particao.validacao + particao.teste)
    grafo_temporal.verificar_sem_vazamento(grafos, todas)

    for transicao in todas:
        assert grafos.para(transicao).ate_periodo == transicao.origem


def test_grafo_que_alcanca_o_destino_e_recusado(particao):
    grafos = grafos_falsos()
    # Adultera o corte de um grafo para o destino da transição que ele serve.
    grafos.por_origem["201701"].ate_periodo = "201801"
    with pytest.raises(Exception, match="alcança o destino"):
        grafo_temporal.verificar_sem_vazamento(
            grafos, [Transicao("201701", "201801")]
        )


def test_transicao_sem_grafo_falha_com_mensagem_util():
    grafos = grafos_falsos(origens=["201701"])
    with pytest.raises(Exception, match="nenhum grafo montado"):
        grafos.para(Transicao("202401", "202501"))


def test_projecao_completa_traz_muito_mais_coluna_que_a_minima():
    """
    A limitação de D-23 medida: a projeção mínima entrega duas colunas por tabela
    filha, e é isso que deixa 298 das 368 colunas `util` fora do grafo.
    """
    from src.ml.graph import colunas_minimas_para_grafo

    completa = grafo_temporal.colunas_para_grafo_completo()
    minima = colunas_minimas_para_grafo()

    # A comparação que importa é sobre as tabelas **filhas**: a raiz entra inteira
    # nos dois casos, e é nas filhas que a projeção mínima corta.
    filhas_completa = sum(
        len(v) for t, v in completa.items() if t != TABELA_RAIZ
    )
    filhas_minima = sum(len(v) for t, v in minima.items() if t != TABELA_RAIZ)

    assert all(len(v) == 2 for t, v in minima.items() if t != TABELA_RAIZ)
    assert filhas_completa - filhas_minima > 250  # ~298 na medição de D-23
    assert filhas_completa > 4 * filhas_minima


def test_vocabularios_excluem_municipio_e_entidade():
    """
    Um nó por município ligaria todos os estabelecimentos da cidade entre si — a
    degeneração que D-27 documenta.
    """
    for tabela in ("rlEstabEquipamento", "rlEstabEquipeProf", "rlEquipeNasfEsf"):
        vocabularios = grafo_temporal._vocabularios(tabela)
        assert COL_ENTIDADE not in vocabularios
        assert not any(c.startswith("co_municipio") for c in vocabularios)


def test_colunas_de_peso_pegam_as_quantidades():
    pesos = grafo_temporal._colunas_de_peso("rlEstabEquipamento")
    assert "qt_existente" in pesos and "qt_uso" in pesos
    assert "co_equipamento" not in pesos


def test_treino_em_cpu_seleciona_epoca_pela_validacao(particao):
    """
    Laço completo em CPU com grafo de 24 nós: rápido e sem risco de memória.

    Verifica o que o laço promete — várias atualizações por época, histórico com
    uma linha por época, e pesos da melhor época de validação.
    """
    grafos = grafos_falsos()
    tarefa = tarefa_falsa(particao)
    indice = IndicePares.de(grafos.unidades, [f"{k:02d}" for k in range(N_ITENS)])

    modelo, curva = treino.treinar(
        tarefa,
        particao,
        grafos,
        indice,
        dispositivo="cpu",
        dim_saida=8,
        epocas=4,
        paciencia=4,
        passos_por_epoca=2,
        lote=64,
        amp=False,
        verboso=False,
    )

    assert len(curva["historico"]) == 4
    assert curva["passos_por_epoca"] == 2 * len(particao.treino)
    assert 0 <= curva["melhor_epoca"] <= 3
    assert curva["melhor_ap_validacao"] > 0
    assert curva["grafos_na_gpu"] is False

    previsao = treino.prever(
        modelo, tarefa, particao, grafos, indice, "teste", "gnn_sintetica",
        dispositivo="cpu",
    )
    esperado = len(tarefa.por_conjunto("teste"))
    assert len(previsao.escore) == esperado
    assert len(previsao.y) == esperado
    assert previsao.modelo == "gnn_sintetica"


def test_treino_usa_o_peso_da_aresta(particao):
    """
    `GraphConv` recebe `edge_weight`; sem isso o peso montado pelo grafo temporal
    seria carregado e ignorado, e a informação de quantidade voltaria a se perder.
    """
    grafos = grafos_falsos(com_peso=True)
    pesos = treino._pesos_do_grafo(grafos.por_origem["201701"])
    assert pesos is not None and len(pesos) == 2

    sem_peso = grafos_falsos(com_peso=False)
    assert treino._pesos_do_grafo(sem_peso.por_origem["201701"]) is None


def test_fatia_por_transicao_respeita_o_conjunto(particao):
    grafos = grafos_falsos()
    tarefa = tarefa_falsa(particao)
    indice = IndicePares.de(grafos.unidades, [f"{k:02d}" for k in range(N_ITENS)])

    fatias = treino._por_transicao(tarefa, particao, indice, "treino")
    assert [t.destino for t, *_ in fatias] == ["201801", "201901"]
    assert sum(len(y) for _, _, _, y, _ in fatias) == len(
        tarefa.por_conjunto("treino")
    )
