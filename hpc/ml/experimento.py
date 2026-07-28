"""
Orquestrador do servidor: uma célula da matriz de D-34 por execução.

    python -m hpc.ml.experimento --recorte 35 --modo compativel   # célula A
    python -m hpc.ml.experimento --recorte ""  --modo compativel   # célula B
    python -m hpc.ml.experimento --recorte 35 --modo completo      # célula C
    python -m hpc.ml.experimento --recorte ""  --modo completo      # célula D

Escreve dois artefatos por trilha: o resumo em `docs/resultados/` e o pacote de
modelo em `models/`, este último no mesmo formato do pipeline do notebook — mesmo
manifesto, mesmo índice, mesma previsão por exemplo (D-35). É o que permite
validar em qualquer máquina o que foi treinado aqui, e comparar as quatro células
com o mesmo código de leitura.

As baselines vêm de `src.ml.baselines` sem alteração: elas não têm gargalo de GPU,
e reimplementá-las só criaria uma segunda verdade sobre o piso do experimento.
"""

from __future__ import annotations

import argparse
import gc
import json
import time
from datetime import date
from pathlib import Path

from hpc.config.ambiente import exigir_cuda, perfil_maquina, semente_global
from hpc.config.paths import grafos_folder, primary_folder
from hpc.etl.grafo_store import materializar, nome_do_conjunto
from hpc.ml import tarefa as tarefa_hpc
from hpc.ml import treino as treino_hpc
from hpc.ml.grafo_temporal import carregar as carregar_grafos
from src.config.paths import DOCS_DIR
from src.etl.changes import periodos_disponiveis
from src.ml import artefatos, baselines, graph, metrics
from src.ml.gnn import IndicePares
from src.ml.splits import particionar

PASTA_RESULTADOS = DOCS_DIR / "resultados"


def log(msg: str) -> None:
    """
    Imprime com hora, sem buffer.

    Args:
        msg: mensagem a registrar. Sem buffer porque a execução vive sob `screen`.
    """
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def main() -> int:
    """
    Entrada de linha de comando de uma célula da matriz.

    Returns:
        0 em sucesso. Código de saída do processo.
    """
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--recorte", default="", help="prefixo IBGE; vazio = país inteiro")
    ap.add_argument("--modo", choices=["compativel", "completo"], default="completo")
    ap.add_argument("--trilhas", choices=["todas", "baselines", "gnn"], default="todas")
    ap.add_argument("--epocas", type=int, default=150)
    ap.add_argument("--paciencia", type=int, default=15)
    ap.add_argument("--passos", type=int, default=20, help="passos por transição, por época")
    ap.add_argument("--lote", type=int, default=2_000_000)
    ap.add_argument("--validar-cada", type=int, default=1,
                    help="valida a cada k épocas; a paciência conta validações")
    ap.add_argument("--sem-amp", action="store_true")
    ap.add_argument("--sem-retomar", action="store_true",
                    help="ignora o checkpoint e recomeça o treino do zero")
    ap.add_argument("--permitir-cpu", action="store_true")
    ap.add_argument("--permitir-maquina-pequena", action="store_true",
                    help="ignora a guarda de RAM; só para dado sintético, nunca "
                         "para a camada primária real")
    ap.add_argument("--pasta-primaria", type=Path, default=None,
                    help="camada primária alternativa; usada no smoke fora do servidor")
    ap.add_argument("--reusar-grafos", action="store_true",
                    help="carrega da camada 05 em vez de montar")
    ap.add_argument("--semente", type=int, default=42,
                    help="varia inicialização e sorteio de lote; repetir com "
                         "sementes diferentes é o que mede a banda de ruído")
    ap.add_argument("--excluir-pandemia", action="store_true",
                    help="descarta toda transição que toque 202001 ou 202101; é o "
                         "experimento de controle da seção 4.1 da metodologia")
    args = ap.parse_args()

    recorte = args.recorte or None
    dispositivo = exigir_cuda(permitir_cpu=args.permitir_cpu)
    perfil = perfil_maquina()
    semente_global(args.semente)

    pasta_primaria = args.pasta_primaria or primary_folder()
    periodos = periodos_disponiveis(pasta_primaria)
    particao = particionar(periodos, excluir_pandemia=args.excluir_pandemia)

    PASTA_RESULTADOS.mkdir(parents=True, exist_ok=True)
    variante = "sem-pandemia" if args.excluir_pandemia else "com-pandemia"
    saida = PASTA_RESULTADOS / (
        f"{date.today()}-hpc-{recorte or 'pais'}-{args.modo}"
        f"-{variante}-s{args.semente}.json"
    )
    resultados: dict = {
        "experimento": "aquisicao de equipamento — pipeline do servidor",
        "data": str(date.today()),
        "recorte": recorte,
        "modo": args.modo,
        "excluir_pandemia": args.excluir_pandemia,
        "semente": args.semente,
        "snapshots": periodos,
        "dispositivo": dispositivo,
        "maquina": perfil.como_dict(),
        "particao": {
            conjunto: [t.destino for t in grupo]
            for conjunto, grupo in particao.conjuntos.items()
        },
    }

    def salvar() -> None:
        """
        Grava o JSON de resultados agora, sobrescrevendo.

        Chamado depois de cada etapa: uma queda no meio preserva o que já foi
        medido, e no cluster, sem escalonador, isso é a diferença entre perder uma
        etapa e perder a execução.
        """
        saida.write_text(
            json.dumps(resultados, indent=2, ensure_ascii=False, default=float),
            encoding="utf-8",
        )

    log(f"host {perfil.host} | dispositivo {dispositivo} | modo {args.modo}")
    log(f"recorte {recorte or 'país'} | {len(periodos)} snapshots | "
        f"{variante} | semente {args.semente}")

    # ---------------------------------------------------------------- tarefa
    t0 = time.time()
    tarefa = tarefa_hpc.tarefa_aquisicao(
        particao,
        recorte=recorte,
        modo=args.modo,
        pasta=pasta_primaria,
        permitir_maquina_pequena=args.permitir_maquina_pequena,
    )
    resultados["tarefa"] = {
        "linhas": len(tarefa.df),
        "positivos": int(tarefa.df["rotulo"].sum()),
        "memoria_gb": round(tarefa.memoria_gb(), 3),
        "negativos_por_positivo": 200 if args.modo == "compativel" else None,
        "segundos": round(time.time() - t0),
    }
    log(
        f"tarefa: {len(tarefa.df):,} linhas, {tarefa.memoria_gb():.2f} GB, "
        f"{int(tarefa.df['rotulo'].sum()):,} positivos"
    )
    salvar()

    # ----------------------------------------------------------------- nós
    db = graph.montar_db(
        recorte=recorte,
        pasta=pasta_primaria,
        colunas=graph.colunas_minimas_para_grafo(),
    )
    unidades = sorted(
        set(db.table_dict[graph.TABELA_RAIZ].df[graph.COL_ENTIDADE].to_pylist())
    )
    itens = sorted(tarefa.df[tarefa.col_item].cat.categories)
    indice = IndicePares.de(unidades, itens)
    posicionaveis = set(graph.coordenadas_por_unidade(db)[graph.COL_ENTIDADE])
    log(
        f"{len(unidades):,} estabelecimentos, {len(itens)} itens, "
        f"{len(posicionaveis):,} posicionáveis "
        f"({100 * len(posicionaveis) / len(unidades):.1f}%)"
    )
    del db
    gc.collect()

    itens_do_teste = tarefa.por_conjunto("teste")[tarefa.col_item]

    def avaliar(previsao, nome, modelo=None, curva=None, hiper=None) -> None:
        """
        Mede nas duas visões, grava o pacote e atualiza o JSON.

        Args:
            previsao: `Previsao` a avaliar.
            nome: rótulo do modelo na tabela de resultados.
            modelo: modelo treinado. `None` para baseline, que não tem pesos.
            curva: histórico de treino.
            hiper: hiperparâmetros, para a procedência do manifesto.

        A visão pareada restringe todas as trilhas aos posicionáveis, que é a
        única comparação legítima quando a trilha geográfica está envolvida (D-15).
        """
        completo = metrics.avaliar_classificacao(
            previsao.y, previsao.escore, previsao.entidades, k=10
        )
        dentro = previsao.mascara_de_entidades(posicionaveis)
        pareado = metrics.avaliar_classificacao(
            previsao.y[dentro], previsao.escore[dentro], previsao.entidades[dentro], k=10
        )
        resultados.setdefault("teste_completo", {})[nome] = completo
        resultados.setdefault("teste_pareado", {})[nome] = pareado
        log(
            f"{nome}: AP={completo['average_precision']:.5f} "
            f"MAP@10={completo['map@10']:.4f} | pareada "
            f"AP={pareado['average_precision']:.5f} MAP@10={pareado['map@10']:.4f}"
        )
        pacote = artefatos.salvar_execucao(
            nome,
            previsao,
            {"teste_completo": completo, "teste_pareado": pareado},
            escopo=recorte,
            modo=args.modo,
            variante=variante,
            semente=args.semente,
            modelo=modelo,
            unidades=indice.unidades if modelo is not None else None,
            itens_indice=indice.itens if modelo is not None else None,
            itens_por_exemplo=itens_do_teste,
            historico=curva,
            particao=particao,
            hiperparametros=hiper or {},
            extra={"pipeline": "hpc (servidor)", "maquina": perfil.como_dict()},
        )
        resultados.setdefault("pacotes", {})[nome] = pacote.name
        log(f"{nome}: pacote em {pacote}")
        salvar()

    # -------------------------------------------------------------- trilha 1
    if args.trilhas in ("todas", "baselines"):
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

    if args.trilhas == "baselines":
        log("--trilhas baselines: encerrando antes da GNN")
        return 0

    # ------------------------------------------------------- grafo e trilha 2
    conjunto = nome_do_conjunto(recorte, args.modo)
    # A variante de pandemia muda a partição, e a partição muda o corte de cada
    # grafo — reusar os grafos da outra variante seria vazamento silencioso.
    conjunto = f"{conjunto}-{variante}"
    caminho_grafos = grafos_folder(criar=True) / conjunto / "grafos.pt"
    if args.reusar_grafos and caminho_grafos.exists():
        log(f"carregando grafos de {caminho_grafos}")
        grafos = carregar_grafos(caminho_grafos)
    else:
        t0 = time.time()
        materializar(
            recorte=recorte,
            modo=args.modo,
            pasta_primaria=pasta_primaria,
            destino=caminho_grafos.parent,
            permitir_maquina_pequena=args.permitir_maquina_pequena,
            excluir_pandemia=args.excluir_pandemia,
        )
        grafos = carregar_grafos(caminho_grafos)
        log(f"grafos montados em {time.time() - t0:.0f}s")

    resultados["grafos"] = {
        "n": grafos.n_grafos,
        "por_origem": grafos.resumo,
        "com_atributos": args.modo == "completo",
    }
    salvar()

    # O índice do treino precisa ser o dos nós do grafo, na ordem em que ele os
    # tem — a mesma razão de `IndicePares` existir (D-35).
    indice = IndicePares.de(grafos.unidades, itens)

    hiper = {
        "epocas": args.epocas,
        "paciencia": args.paciencia,
        "passos_por_transicao": args.passos,
        "lote": args.lote,
        "validar_cada": args.validar_cada,
        "amp": not args.sem_amp,
        "modo": args.modo,
        "semente": args.semente,
        "excluir_pandemia": args.excluir_pandemia,
        "negativos_por_positivo": 200 if args.modo == "compativel" else None,
    }

    # A semente entra no nome do checkpoint: sem ela, a execução da semente 43
    # retomaria o treino da 42 e as duas mediriam a mesma coisa.
    checkpoint = artefatos.MODELS_DIR / f"parcial-{conjunto}-s{args.semente}.pt"

    t0 = time.time()
    modelo, curva = treino_hpc.treinar(
        tarefa,
        particao,
        grafos,
        indice,
        dispositivo=dispositivo,
        epocas=args.epocas,
        paciencia=args.paciencia,
        passos_por_epoca=args.passos,
        lote=args.lote,
        validar_cada=args.validar_cada,
        amp=not args.sem_amp,
        checkpoint_em=checkpoint,
        retomar=not args.sem_retomar,
    )
    checkpoint.unlink(missing_ok=True)
    resultados.setdefault("treino", {})["gnn_temporal"] = {
        "segundos": round(time.time() - t0),
        "melhor_epoca": curva["melhor_epoca"],
        "ap_validacao": curva["melhor_ap_validacao"],
        "epocas_rodadas": curva["epocas_rodadas"],
        "retomado_da_epoca": curva["retomado_da_epoca"],
        "validar_cada": curva["validar_cada"],
        "passos_por_epoca": curva["passos_por_epoca"],
        "grafos_na_gpu": curva["grafos_na_gpu"],
        "amp": curva["amp"],
    }
    log(
        f"treino em {time.time() - t0:.0f}s | melhor época {curva['melhor_epoca']} | "
        f"AP validação {curva['melhor_ap_validacao']:.5f}"
    )
    salvar()

    previsao = treino_hpc.prever(
        modelo, tarefa, particao, grafos, indice, "teste",
        "gnn_temporal" if args.modo == "completo" else "gnn_relacional",
        dispositivo=dispositivo,
    )
    avaliar(
        previsao,
        previsao.modelo,
        modelo=modelo,
        curva=curva["historico"],
        hiper=hiper,
    )

    print(f"\n{'=' * 78}\nPAREADA — {len(posicionaveis):,} posicionáveis\n{'=' * 78}")
    print(metrics.tabela_de_resultados(resultados["teste_pareado"]).to_string())
    log(f"escrito: {saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
