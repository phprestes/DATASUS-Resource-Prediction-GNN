"""
Roda as três trilhas e escreve os resultados em docs/resultados/.

Existe como script, e não apenas como notebook, por duas razões práticas: o
treino leva vinte minutos e é mais confortável em background, e uma execução
interrompida não pode perder o que já mediu.

O resultado é gravado incrementalmente a cada modelo. Uma queda no meio da
trilha 3 preserva a trilha 1 e a 2.

Uso:
    python -m tools.roda_experimento
    python -m tools.roda_experimento --recorte 355030 --epocas 50
    python -m tools.roda_experimento --pular-gnn      # só as baselines
"""

from __future__ import annotations

import argparse
import gc
import json
import resource
import time
from datetime import date
from pathlib import Path

import pandas as pd

from src.config.paths import DOCS_DIR, PRIMARY_FOLDER
from src.etl import changes
from src.ml import artefatos, baselines, gnn, graph, metrics, tasks
from src.ml.splits import particionar

PASTA_RESULTADOS = DOCS_DIR / "resultados"


def rss_gb() -> float:
    """
    Pico de memória residente do processo até agora.

    Returns:
        Gigabytes. É pico acumulado, não uso instantâneo — o que interessa numa
        máquina de 9 GB é o máximo que já se pediu.
    """
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6


def log(msg: str) -> None:
    """
    Imprime com hora e pico de memória, sem buffer.

    Args:
        msg: mensagem a registrar. O pico vai em toda linha porque memória é a
            restrição que decide se a execução termina.
    """
    print(f"[{time.strftime('%H:%M:%S')}  pico {rss_gb():.2f} GB] {msg}", flush=True)


def main() -> int:
    """
    Entrada de linha de comando das três trilhas.

    Returns:
        0 em sucesso. Código de saída do processo.
    """
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--recorte", default=graph.RECORTE_PADRAO)
    ap.add_argument("--epocas", type=int, default=150)
    ap.add_argument("--paciencia", type=int, default=15)
    ap.add_argument("--k-vizinhos", type=int, default=10)
    ap.add_argument("--pular-gnn", action="store_true")
    ap.add_argument("--semente", type=int, default=gnn.SEMENTE,
                    help="varia o sorteio de minilote e a inicialização; repetir "
                         "a execução com sementes diferentes é o que mede a banda "
                         "de ruído")
    ap.add_argument("--excluir-pandemia", action="store_true",
                    help="descarta toda transição que toque 202001 ou 202101; é o "
                         "experimento de controle da seção 4.1 da metodologia")
    ap.add_argument("--pasta-primaria", type=Path, default=None,
                    help="camada primária alternativa; no cluster aponta para "
                         "$IC_HPC_DATA/03_primary, que é onde o ETL do servidor grava")
    ap.add_argument("--saida", type=Path, default=None)
    args = ap.parse_args()

    pasta_primaria = args.pasta_primaria or PRIMARY_FOLDER

    PASTA_RESULTADOS.mkdir(parents=True, exist_ok=True)
    variante = "sem-pandemia" if args.excluir_pandemia else "com-pandemia"
    saida = args.saida or (
        PASTA_RESULTADOS
        / f"{date.today()}-trilhas-{args.recorte or 'pais'}-{variante}-s{args.semente}.json"
    )

    periodos = changes.periodos_disponiveis(pasta_primaria)
    particao = particionar(periodos, excluir_pandemia=args.excluir_pandemia)
    # O grafo é estático, então o corte tem de ser anterior a QUALQUER rótulo, e
    # não apenas ao fim do treino: a aresta estabelecimento-equipamento em t+1 é
    # o alvo da transição que termina em t+1. Ver D-25.
    corte_grafo = particao.antes_de_todos_os_rotulos

    resultados: dict = {
        "experimento": "aquisicao de equipamento — tres trilhas",
        "data": str(date.today()),
        "recorte": args.recorte,
        "excluir_pandemia": args.excluir_pandemia,
        "semente": args.semente,
        "snapshots": periodos,
        "particao": {
            "treino": [t.destino for t in particao.treino],
            "validacao": [t.destino for t in particao.validacao],
            "teste": [t.destino for t in particao.teste],
            "fim_do_treino": particao.fim_do_treino,
            "corte_do_grafo": corte_grafo,
        },
    }

    def salvar() -> None:
        """
        Grava o JSON de resultados agora, sobrescrevendo.

        Chamado depois de cada modelo: uma queda na trilha 3 preserva a 1 e a 2,
        que é a razão de este script existir além do notebook.
        """
        saida.write_text(
            json.dumps(resultados, indent=2, ensure_ascii=False, default=float),
            encoding="utf-8",
        )

    log(f"recorte {args.recorte!r} | snapshots {len(periodos)} | "
        f"{variante} | semente {args.semente}")
    log(f"fim do treino {particao.fim_do_treino} | corte do grafo {corte_grafo}")

    # ---------------------------------------------------------------- tarefa
    tarefa = tasks.tarefa_aquisicao(
        particao, recorte=args.recorte, pasta=pasta_primaria
    )
    resultados["tarefa"] = {
        "linhas": len(tarefa.df),
        "positivos": int(tarefa.df[tasks.COL_ROTULO].sum()),
        "memoria_gb": round(tarefa.memoria_gb(), 3),
    }
    log(f"tarefa: {len(tarefa.df):,} linhas, {tarefa.memoria_gb():.2f} GB")
    salvar()

    # ----------------------------------------------------------------- grafo
    # Projeção mínima: sem ela o Database do estado carrega 76 milhões de linhas
    # com todas as colunas e chega a 5,3 GB numa máquina de 9 GB (D-23).
    t0 = time.time()
    db = graph.montar_db(
        recorte=args.recorte,
        pasta=pasta_primaria,
        colunas=graph.colunas_minimas_para_grafo(),
    )
    log(f"Database em {time.time() - t0:.0f}s: {len(db.table_dict)} tabelas")

    unidades = sorted(
        set(db.table_dict[graph.TABELA_RAIZ].df[graph.COL_ENTIDADE].to_pylist())
    )
    itens = sorted(tarefa.df[tarefa.col_item].cat.categories)
    indice = gnn.IndicePares.de(unidades, itens)

    # A trilha 3 só alcança os posicionáveis. Conhecer o subconjunto antes de
    # qualquer modelo evita reter previsões inteiras só para restringi-las (D-15).
    posicionaveis = set(graph.coordenadas_por_unidade(db)[graph.COL_ENTIDADE])
    log(f"{len(unidades):,} estabelecimentos, {len(itens)} itens, "
        f"{len(posicionaveis):,} posicionáveis "
        f"({100 * len(posicionaveis) / len(unidades):.1f}%)")
    gc.collect()

    itens_do_teste = tarefa.por_conjunto("teste")[tarefa.col_item]

    def avaliar(
        previsao,
        nome: str,
        modelo=None,
        curva=None,
        indice_do_modelo: "gnn.IndicePares | None" = None,
    ) -> None:
        """
        Mede nas duas visões e **salva o pacote da execução** em `models/`.

        A versão anterior media e descartava, o que tornava impossível refazer uma
        curva de precisão–revocação ou reavaliar sem repetir o treino. Agora o
        escore por exemplo vai para o disco junto com a métrica, o índice e — nas
        trilhas com treino — os pesos. Ver D-35.

        Args:
            previsao: `Previsao` a avaliar.
            nome: rótulo do modelo na tabela de resultados.
            modelo: modelo treinado. `None` para baseline.
            curva: histórico de treino.
            indice_do_modelo: índice **do modelo**, não do experimento. A trilha 3
                só alcança os posicionáveis e portanto tem outra ordem de
                `unidades`; salvar a ordem errada dá um pacote que carrega sem
                erro e pontua lixo.
        """
        resultados.setdefault("teste_completo", {})[nome] = (
            metrics.avaliar_classificacao(
                previsao.y, previsao.escore, previsao.entidades, k=10
            )
        )
        dentro = previsao.mascara_de_entidades(posicionaveis)
        resultados.setdefault("teste_pareado", {})[nome] = (
            metrics.avaliar_classificacao(
                previsao.y[dentro], previsao.escore[dentro],
                previsao.entidades[dentro], k=10,
            )
        )
        completo = resultados["teste_completo"][nome]
        pareado = resultados["teste_pareado"][nome]
        log(f"{nome}: AP={completo['average_precision']:.5f} "
            f"MAP@10={completo['map@10']:.4f} | pareada "
            f"AP={pareado['average_precision']:.5f} MAP@10={pareado['map@10']:.4f}")
        salvar()

        # `modo="compativel"` porque este é o pipeline com as limitações da
        # máquina de 9 GB: grafo estático, projeção mínima, negativos 200:1 e um
        # passo de gradiente por época. É a célula A da matriz de D-34.
        # O índice tem de ser o do modelo, não o do experimento: a trilha 3 só
        # alcança os posicionáveis e portanto tem outra ordem de `unidades`.
        # Salvar a ordem errada dá um pacote que carrega sem erro e pontua lixo.
        do_modelo = indice_do_modelo or indice
        pacote = artefatos.salvar_execucao(
            nome,
            previsao,
            {"teste_completo": completo, "teste_pareado": pareado},
            escopo=args.recorte,
            modo="compativel",
            variante=variante,
            semente=args.semente,
            modelo=modelo,
            unidades=do_modelo.unidades if modelo is not None else None,
            itens_indice=do_modelo.itens if modelo is not None else None,
            itens_por_exemplo=itens_do_teste,
            historico=curva,
            particao=particao,
            hiperparametros={
                "epocas": args.epocas,
                "paciencia": args.paciencia,
                "k_vizinhos": args.k_vizinhos,
                "negativos_por_positivo": 200,
                "semente": args.semente,
                "excluir_pandemia": args.excluir_pandemia,
            },
            extra={
                "pipeline": "src (máquina local)",
                "limitacoes": [
                    "grafo estático cortado em " + corte_grafo,
                    "projeção mínima: duas colunas por tabela filha",
                    "negativos de treino subamostrados 200:1",
                    "um passo de gradiente por época",
                ],
            },
        )
        resultados.setdefault("pacotes", {})[nome] = str(
            pacote.relative_to(pacote.parents[1])
        )
        log(f"{nome}: pacote em {pacote}")
        salvar()

    # -------------------------------------------------------------- trilha 1
    for nome, fn in [
        ("persistencia", lambda: baselines.persistencia(tarefa, "teste")),
        ("popularidade_item",
         lambda: baselines.popularidade_item(tarefa, particao, "teste")),
        ("gbdt_geral", lambda: baselines.gbdt(tarefa, particao, conjunto="teste")),
    ]:
        previsao = fn()
        avaliar(previsao, nome)
        del previsao
        gc.collect()

    if args.pular_gnn:
        log("--pular-gnn: encerrando após a trilha 1")
        return 0

    features = gnn.features_de_estabelecimento(db, unidades, ate_periodo=corte_grafo)

    # -------------------------------------------------------------- trilha 2
    dados_rel = gnn.grafo_relacional_para_data(
        db, unidades, features, ate_periodo=corte_grafo
    )
    resultados["grafo_relacional"] = {
        "tipos_no": len(dados_rel.node_types),
        "relacoes": len(dados_rel.edge_types),
        "arestas": {k: int(v) for k, v in dados_rel.resumo_arestas.items()},
    }
    log(f"grafo relacional: {len(dados_rel.node_types)} tipos de nó, "
        f"{len(dados_rel.edge_types)} relações")
    salvar()

    t0 = time.time()
    modelo, historico = gnn.treinar_aquisicao(
        tarefa, particao, dados_rel, indice,
        epocas=args.epocas, paciencia=args.paciencia, verboso=True,
        semente=args.semente,
    )
    resultados.setdefault("treino", {})["gnn_relacional"] = {
        "segundos": round(time.time() - t0),
        "melhor_epoca": historico["melhor_epoca"],
        "ap_validacao": historico["melhor_ap_validacao"],
    }
    avaliar(
        gnn.prever_aquisicao(modelo, tarefa, dados_rel, indice, "teste",
                             "gnn_relacional"),
        "gnn_relacional",
        modelo=modelo,
        curva=historico["historico"],
        indice_do_modelo=indice,
    )
    del dados_rel, modelo
    gc.collect()

    # -------------------------------------------------------------- trilha 3
    grafo_geo = graph.montar_grafo_geografico(db, k=args.k_vizinhos)
    resultados["grafo_geografico"] = {
        "nos": grafo_geo.n_nos,
        "arestas": grafo_geo.n_arestas,
        "k": grafo_geo.k,
        "cobertura_pct": round(100 * grafo_geo.n_nos / len(unidades), 1),
    }
    log(f"grafo geográfico: {grafo_geo.n_nos:,} nós, {grafo_geo.n_arestas:,} arestas")

    indice_geo = gnn.IndicePares.de(grafo_geo.unidades, itens)
    dados_geo = gnn.grafo_geografico_para_data(
        grafo_geo,
        gnn.features_de_estabelecimento(db, grafo_geo.unidades, ate_periodo=corte_grafo),
    )

    t0 = time.time()
    modelo, historico = gnn.treinar_aquisicao(
        tarefa, particao, dados_geo, indice_geo,
        epocas=args.epocas, paciencia=args.paciencia, verboso=True,
        semente=args.semente,
    )
    resultados.setdefault("treino", {})["gnn_geografica"] = {
        "segundos": round(time.time() - t0),
        "melhor_epoca": historico["melhor_epoca"],
        "ap_validacao": historico["melhor_ap_validacao"],
    }
    avaliar(
        gnn.prever_aquisicao(modelo, tarefa, dados_geo, indice_geo, "teste",
                             "gnn_geografica"),
        "gnn_geografica",
        modelo=modelo,
        curva=historico["historico"],
        indice_do_modelo=indice_geo,
    )

    resultados["ambiente"] = {"pico_rss_gb": round(rss_gb(), 2)}
    salvar()

    # ----------------------------------------------------------------- saída
    for titulo, chave in [
        ("TODOS OS EXEMPLOS DE TESTE", "teste_completo"),
        (f"PAREADA — {len(posicionaveis):,} posicionáveis", "teste_pareado"),
    ]:
        print(f"\n{'=' * 78}\n{titulo}\n{'=' * 78}")
        print(metrics.tabela_de_resultados(resultados[chave]).to_string())

    log(f"escrito: {saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
