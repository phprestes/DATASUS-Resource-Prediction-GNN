# Makefile do projeto. `make` sem argumento lista tudo.
#
# ============================================================================
# LEIA ISTO SE É A PRIMEIRA VEZ
# ============================================================================
#
# O projeto tem DOIS pipelines, que rodam em máquinas diferentes e são isolados
# de propósito (D-34):
#
#   src/   máquina pessoal. 9 GB de RAM, sem GPU, recorte estadual.
#          Alvos SEM prefixo: `setup`, `etl`, `experimento`, `testes`.
#
#   hpc/   cluster do IME (`brucutuvii`: 440 GB, 2x RTX A6000). Escopo nacional,
#          CUDA obrigatório. Alvos com prefixo `hpc-`.
#
# Os alvos `hpc-*` RECUSAM rodar abaixo de 64 GB de RAM. A guarda é deliberada:
# uma tentativa de exercitar o caminho completo numa máquina de 9 GB esgotou a
# memória do sistema e do editor.
#
# Caminho mínimo numa máquina nova:
#
#     make setup                 # cria o .venv e instala tudo
#     make testes                # confirma que o ambiente está de pé
#     make etl                   # baixa e converte os dados (horas, ~3,6 GB)
#     make experimento           # as três trilhas (~55 min, pico 6,3 GB)
#     make resultados            # imprime a tabela do que acabou de rodar
#
# Caminho mínimo no cluster: veja `make hpc-ajuda` e hpc/README.md.
#
# ----------------------------------------------------------------------------
# Convenções
#
#   - Variáveis com `?=` são sobrescritas na linha de comando:
#         make experimento RECORTE=355030 MEM=4G
#   - Toda receita chama o Python do .venv diretamente. `make` abre um shell por
#     linha, então um `source .venv/bin/activate` não sobreviveria à linha
#     seguinte.
#   - Alvos que gastam horas ou gigabytes avisam antes do que vão fazer.
# ============================================================================

PY       := .venv/bin/python
PIP      := VIRTUAL_ENV=.venv uv pip

# --- Recorte espacial -------------------------------------------------------
# Prefixo de código IBGE, que é hierárquico. Não há caso especial: município é
# apenas o prefixo completo.
#     355030  município de São Paulo     35  estado       (vazio)  país inteiro
RECORTE  ?= 35

# --- Teto de memória --------------------------------------------------------
# O experimento local roda dentro de um cgroup. Se estourar, morre o
# experimento e não a sessão do usuário.
MEM      ?= 7G

# --- ETL --------------------------------------------------------------------
PERIODOS ?=              # competências a processar; vazio = série canônica
TABELAS  ?=              # tabelas de `reprocessar-tabelas`; sem default
PERIODO  ?=              # competência de `reprocessar-tabelas`

# --- Modelagem --------------------------------------------------------------
# Época e paciência são os de D-44; menores não reproduzem o resultado.
EPOCAS    ?= 200
PACIENCIA ?= 20
SEMENTE   ?= 42
RUN      ?=              # pacote a validar; vazio = o mais recente de models/

# `compativel` replica as quatro limitações da máquina de 9 GB em qualquer
# escopo; `completo` as levanta. É condição experimental, não compat de código.
MODO     ?= completo

# Variante de pandemia. Vazio = série completa; qualquer valor = controle sem
# as transições que tocam 202001 ou 202101.
SEM_PANDEMIA ?=
FLAG_PANDEMIA := $(if $(SEM_PANDEMIA),--excluir-pandemia,)

# Envolve o comando num cgroup com teto de memória, se systemd-run existir.
LIMITADOR := $(shell command -v systemd-run >/dev/null 2>&1 && echo "systemd-run --user --scope -p MemoryMax=$(MEM) -p MemorySwapMax=$(MEM) -q")

.DEFAULT_GOAL := help
.PHONY: help setup etl etl-periodo mudancas reprocessar-tabelas testes teste-schema \
        verificar experimento experimento-baselines experimento-capital \
        experimento-sem-pandemia resultados modelos validar notebooks \
        limpar-intermediario limpar-cache \
        hpc-ambiente hpc-etl hpc-grafos hpc-experimento hpc-matriz hpc-tudo \
        hpc-plano hpc-ajuda

# ============================================================ ajuda

help:  ## Lista os alvos disponíveis
	@echo ""
	@echo "\033[1mPRIMEIROS PASSOS\033[0m  (máquina pessoal)"
	@echo "  make setup   ->  make testes  ->  make etl  ->  make experimento"
	@echo ""
	@echo "\033[1mPIPELINE LOCAL (src/)\033[0m — 9 GB, sem GPU:"
	@grep -hE '^[a-z0-9][a-zA-Z0-9_-]*:.*?## ' $(firstword $(MAKEFILE_LIST)) \
		| grep -v '^hpc-' \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[1m%-26s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "\033[36mPIPELINE DO SERVIDOR (hpc/)\033[0m — NÃO rodar aqui; exige 64 GB e CUDA:"
	@grep -hE '^hpc-[a-zA-Z0-9_-]*:.*?## ' $(firstword $(MAKEFILE_LIST)) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-26s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "\033[1mVARIÁVEIS\033[0m (sobrescreva na linha de comando):"
	@echo "  RECORTE=$(RECORTE)              prefixo IBGE: 355030 capital, 35 estado, vazio país"
	@echo "  MEM=$(MEM)                 teto de memória do experimento (cgroup)"
	@echo "  EPOCAS=$(EPOCAS)             máximo de épocas no treino"
	@echo "  SEMENTE=$(SEMENTE)              varia a inicialização; repita para medir ruído"
	@echo "  SEM_PANDEMIA=            qualquer valor liga o controle sem 2020/2021"
	@echo "  MODO=$(MODO)           servidor: compativel replica as limitações de 9 GB"
	@echo "  PERIODOS=                competências do ETL; vazio = série canônica"
	@echo ""
	@echo "\033[1mEXEMPLOS\033[0m"
	@echo "  make etl-periodo PERIODOS=202601"
	@echo "  make experimento RECORTE=355030 MEM=4G"
	@echo "  make experimento SEM_PANDEMIA=1"
	@echo "  make reprocessar-tabelas TABELAS=tbEstabelecimento PERIODO=202601"
	@echo "  make hpc-plano                     # no servidor: o que a bateria vai rodar"
	@echo "  make hpc-tudo                      # no servidor: a bateria completa"
	@echo ""

# ============================================================ ambiente

setup:  ## Cria o .venv, instala o pacote e as extensões compiladas do PyG
	uv venv --python 3.12
	$(PIP) install -e .
	@echo ""
	@echo "As três extensões do PyG não existem no PyPI e precisam do índice"
	@echo "casado com a versão do torch:"
	$(PIP) install pyg-lib torch-scatter torch-sparse \
		--find-links https://data.pyg.org/whl/torch-2.9.0+cpu.html

# ============================================================ dados

etl:  ## ETL completo, competência por competência (baixa ~3,6 GB de ZIP; horas)
	@echo "Série canônica completa. Cada competência baixa, ingere e converte,"
	@echo "e o DuckDB intermediário é apagado ao fim de cada uma. Retomável:"
	@echo "competência já convertida é pulada."
	$(PY) -m src.etl.pipeline

etl-periodo:  ## ETL de competências específicas (PERIODOS="202501 202601")
	@test -n "$(PERIODOS)" || { echo "erro: informe PERIODOS, ex: make etl-periodo PERIODOS=202601"; exit 1; }
	$(PY) -m src.etl.pipeline --periodos $(PERIODOS)

mudancas:  ## Recalcula os eventos de mudança entre snapshots consecutivos
	@echo "Reprocessa o diff de todas as tabelas. Necessário depois de mexer em"
	@echo "chave natural ou em tipagem — ver D-27, D-30 e D-38."
	$(PY) -c "from src.etl.changes import detectar_mudancas, taxa_de_mudanca; \
		detectar_mudancas(reprocess=True); \
		t = taxa_de_mudanca(); \
		print(t[t.tabela == 'rlEstabEquipamento'][['periodo_destino','taxa_mudanca','chave_declarada']].to_string(index=False))"

reprocessar-tabelas:  ## Regera só algumas tabelas (TABELAS=a,b PERIODO=YYYYMM)
	@test -n "$(TABELAS)" || { echo "erro: informe TABELAS, ex: TABELAS=tbEstabelecimento"; exit 1; }
	@test -n "$(PERIODO)" || { echo "erro: informe PERIODO, ex: PERIODO=202601"; exit 1; }
	@echo "Caminho para quando 01-selecao-tabelas.md admite coluna nova: reprocessa"
	@echo "só o necessário, e apaga o DuckDB parcial no fim."
	$(PY) -c "from src.etl.to_sql import process_cnes_zip; from src.etl.to_parquet import clean_cnes_data; \
		from src.config.paths import INTERMEDIATE_FOLDER; from pathlib import Path; \
		tabelas = '$(TABELAS)'.split(','); \
		process_cnes_zip(['$(PERIODO)'], reprocess=True, tabelas=tabelas); \
		clean_cnes_data(['$(PERIODO)'], reprocess=True, tabelas=tabelas); \
		d = INTERMEDIATE_FOLDER / 'sql_cnes_$(PERIODO).duckdb'; \
		[p.unlink() for p in (d, Path(str(d) + '.wal')) if p.exists()]; \
		print('intermediário parcial removido')"

# ============================================================ qualidade

testes:  ## Roda a suíte completa
	$(PY) -m pytest tests/ -q

teste-schema:  ## Roda só o invariante central do schema
	$(PY) -m pytest tests/test_schema.py -q

verificar:  ## Testes + resumo do schema derivado de docs/01-selecao-tabelas.md
	$(PY) -m pytest tests/ -q
	@echo ""
	$(PY) -c "from src.config import schema; \
		tabelas, fora = schema.carregar(); \
		util = sum(len(t.por_classificacao('util')) for t in tabelas); \
		print(f'tabelas incluídas: {len(schema.FACT_TABLES)} | fora: {len(fora)}'); \
		print(f'colunas util: {util} | chaves naturais: {len(schema.CNES_NATURAL_KEY)}'); \
		print(f'fkeys declaradas: {sum(len(v) for v in schema.CNES_FKEY.values())}')"

# ============================================================ experimento

experimento:  ## As três trilhas, sob cgroup (~1h12 no estado, pico 6,95 GB)
	@echo "Recorte $(RECORTE), teto $(MEM), semente $(SEMENTE). Resultado gravado"
	@echo "incrementalmente em docs/resultados/. Se o teto estourar, morre o"
	@echo "experimento e não o ambiente."
	@echo "O pico de D-44 foi 6,95 GB dentro do teto de 7 GB: feche o navegador."
	$(LIMITADOR) $(PY) -m tools.roda_experimento \
		--recorte $(RECORTE) --epocas $(EPOCAS) --paciencia $(PACIENCIA) \
		--semente $(SEMENTE) $(FLAG_PANDEMIA)

experimento-baselines:  ## Só a trilha 1, as cinco baselines, sem GNN (~25 min)
	$(LIMITADOR) $(PY) -m tools.roda_experimento \
		--recorte $(RECORTE) --semente $(SEMENTE) $(FLAG_PANDEMIA) --pular-gnn

experimento-capital:  ## As três trilhas na capital (barato, para depuração)
	$(MAKE) experimento RECORTE=355030 MEM=4G

experimento-sem-pandemia:  ## Controle: descarta as transições que tocam 2020/2021
	@echo "Variante exigida pela seção 4.1 da metodologia: a conclusão sobrevive"
	@echo "ao choque de covid-19?"
	$(MAKE) experimento SEM_PANDEMIA=1

resultados:  ## Mostra a tabela pareada do resultado mais recente
	@$(PY) -c "import json, pathlib; \
		arquivos = sorted(pathlib.Path('docs/resultados').glob('*-trilhas-*.json')); \
		print('nenhum resultado em docs/resultados/') if not arquivos else None; \
		d = json.loads(arquivos[-1].read_text()) if arquivos else {}; \
		print(f\"{arquivos[-1].name}  |  teste {d['particao']['teste']}\") if arquivos else None; \
		[print(f\"{n:20s} AP {m['average_precision']:.5f}  AUC {m['auc_roc']:.3f}  MAP@10 {m['map@10']:.4f}\") \
		 for n, m in sorted(d.get('teste_pareado', {}).items(), key=lambda x: -x[1]['average_precision'])]"

# ============================================================ artefatos

modelos:  ## Lista os pacotes de modelo em models/, do mais recente ao mais antigo
	@$(PY) -c "from src.ml.artefatos import listar_execucoes; \
		pacotes = listar_execucoes(); \
		print('nenhum pacote em models/ — rode make experimento') if not pacotes else None; \
		[print(f\"{p.nome:52s} {p.manifesto.get('modo','?'):11s} \" \
		       f\"{'com pesos' if p.manifesto.get('modelo_salvo') else 'sem pesos'}\") \
		 for p in pacotes]"

validar:  ## Recomputa as métricas de um pacote sem GPU e sem data/ (RUN=models/...)
	@echo "Confere o manifesto contra as previsões salvas. É o que permite validar"
	@echo "em qualquer máquina um modelo treinado no servidor (D-35)."
	@$(PY) -c "import sys; \
		from src.ml.artefatos import carregar_execucao, conferir, listar_execucoes, recomputar_metricas; \
		alvo = '$(RUN)'; \
		pacotes = listar_execucoes(); \
		p = carregar_execucao(alvo) if alvo else (pacotes[0] if pacotes else None); \
		sys.exit('nenhum pacote em models/ — rode make experimento') if p is None else None; \
		print(f'pacote: {p.nome}'); \
		print(f\"escopo {p.manifesto.get('escopo')} | modo {p.manifesto.get('modo')} | \" \
		      f\"commit {p.manifesto.get('procedencia',{}).get('commit')}\"); \
		m = recomputar_metricas(p)['teste_completo']; \
		print(f\"recomputado: AP {m['average_precision']:.5f}  AUC {m['auc_roc']:.3f}  \" \
		      f\"MAP@10 {m['map@10']:.4f}  prevalência {100*m['prevalencia']:.4f}%\"); \
		problemas = conferir(p); \
		print('manifesto confere com as previsões') if not problemas else [print(f'  DIVERGE {x}') for x in problemas]; \
		sys.exit(1 if problemas else 0)"

# ============================================ pipeline do servidor (hpc/)
#
# Delegação para hpc/Makefile, que é a fonte da verdade dos alvos do servidor.
# Existem aqui para que `make` mostre os dois pipelines de uma vez.

hpc-ajuda:  ## Alvos do pipeline do servidor, com as variáveis dele
	$(MAKE) -f hpc/Makefile help

hpc-ambiente:  ## Perfil da máquina como o servidor a vê (roda em qualquer lugar)
	$(MAKE) -f hpc/Makefile ambiente

hpc-etl:  ## [servidor] ETL nacional, paralelo por competência
	$(MAKE) -f hpc/Makefile etl

hpc-grafos:  ## [servidor] Materializa os grafos por transição na camada 05
	$(MAKE) -f hpc/Makefile grafos RECORTE=$(RECORTE) MODO=$(MODO)

hpc-experimento:  ## [servidor] Uma célula: RECORTE, MODO e SEM_PANDEMIA escolhem qual
	$(MAKE) -f hpc/Makefile experimento RECORTE=$(RECORTE) MODO=$(MODO) SEM_PANDEMIA=$(SEM_PANDEMIA)

hpc-matriz:  ## [servidor] As quatro células de D-34, série completa, em série
	$(MAKE) -f hpc/Makefile matriz

hpc-plano:  ## [servidor] Imprime o que a bateria completa vai rodar, sem rodar
	$(MAKE) -f hpc/Makefile plano

hpc-tudo:  ## [servidor] BATERIA COMPLETA: 2 pipelines x 3 escopos x 2 variantes
	$(MAKE) -f hpc/Makefile tudo

hpc-tudo-do-zero:  ## [servidor] UM COMANDO: ambiente + ETL nacional + bateria
	$(MAKE) -f hpc/Makefile tudo-do-zero

# ============================================================ resto

notebooks:  ## Abre o Jupyter Lab na pasta de notebooks
	@echo "00_analise_alvo é ponto de decisão bloqueante: as trilhas não devem"
	@echo "rodar antes dele estar executado com os vereditos preenchidos."
	.venv/bin/jupyter lab notebook/

limpar-intermediario:  ## Apaga data/02_intermediate (descartável, reprodutível)
	rm -f data/02_intermediate/*.duckdb data/02_intermediate/*.duckdb.wal
	@echo "camada intermediária limpa; camada primária intacta"

limpar-cache:  ## Remove __pycache__, .pytest_cache e caches do RelBench
	find . -type d -name __pycache__ -not -path './.venv/*' -exec rm -rf {} +
	rm -rf .pytest_cache
