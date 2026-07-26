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

from src import baselines, changes, gnn, graph, metrics, tasks
from src.paths import DOCS_DIR
from src.splits import particionar

PASTA_RESULTADOS = DOCS_DIR / "resultados"


def rss_gb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}  pico {rss_gb():.2f} GB] {msg}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--recorte", default=graph.RECORTE_PADRAO)
    ap.add_argument("--epocas", type=int, default=150)
    ap.add_argument("--paciencia", type=int, default=15)
    ap.add_argument("--k-vizinhos", type=int, default=10)
    ap.add_argument("--pular-gnn", action="store_true")
    ap.add_argument("--saida", type=Path, default=None)
    args = ap.parse_args()

    PASTA_RESULTADOS.mkdir(parents=True, exist_ok=True)
    saida = args.saida or (
        PASTA_RESULTADOS / f"{date.today()}-trilhas-{args.recorte}.json"
    )

    periodos = changes.periodos_disponiveis()
    particao = particionar(periodos)
    # O grafo é estático, então o corte tem de ser anterior a QUALQUER rótulo, e
    # não apenas ao fim do treino: a aresta estabelecimento-equipamento em t+1 é
    # o alvo da transição que termina em t+1. Ver D-25.
    corte_grafo = particao.antes_de_todos_os_rotulos

    resultados: dict = {
        "experimento": "aquisicao de equipamento — tres trilhas",
        "data": str(date.today()),
        "recorte": args.recorte,
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
        saida.write_text(
            json.dumps(resultados, indent=2, ensure_ascii=False, default=float),
            encoding="utf-8",
        )

    log(f"recorte {args.recorte!r} | snapshots {len(periodos)}")
    log(f"fim do treino {particao.fim_do_treino} | corte do grafo {corte_grafo}")

    # ---------------------------------------------------------------- tarefa
    tarefa = tasks.tarefa_aquisicao(particao, recorte=args.recorte)
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
        recorte=args.recorte, colunas=graph.colunas_minimas_para_grafo()
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

    def avaliar(previsao, nome: str) -> None:
        """Mede nas duas visões e descarta — reter previsões custa centenas de MB."""
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
