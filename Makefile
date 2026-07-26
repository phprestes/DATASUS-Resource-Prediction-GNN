# Makefile do projeto — atalhos documentados para o que se roda com frequência.
#
# Toda receita usa o Python do .venv diretamente, sem depender de `activate`:
# `make` abre um shell por linha, então um `source .venv/bin/activate` não
# sobreviveria até a linha seguinte.
#
# Convenções:
#   - `make` sem argumento lista os alvos (help).
#   - Variáveis com `?=` podem ser sobrescritas na linha de comando:
#         make experimento RECORTE=355030 MEM=4G
#   - Alvos que gastam horas ou gigabytes avisam antes do que vão fazer.

PY       := .venv/bin/python
PIP      := VIRTUAL_ENV=.venv uv pip

# Recorte espacial: prefixo de código IBGE. '35' = estado de São Paulo,
# '355030' = município da capital, vazio = país inteiro (exige memória de sobra).
RECORTE  ?= 35

# Teto de memória do experimento.
MEM      ?= 7G

# Competências a processar no ETL. Vazio = série canônica de src/etl/extract.py.
PERIODOS ?=

# Tabelas a reprocessar em `reprocessar-tabelas`. Sem default de propósito.
TABELAS  ?=
PERIODO  ?=

# Pacote de modelo a validar. Vazio = o mais recente de models/.
RUN      ?=

EPOCAS   ?= 150

# Envolve o comando num cgroup com teto de memória, se systemd-run existir.
LIMITADOR := $(shell command -v systemd-run >/dev/null 2>&1 && echo "systemd-run --user --scope -p MemoryMax=$(MEM) -q")

.DEFAULT_GOAL := help
.PHONY: help setup etl etl-periodo mudancas reprocessar-tabelas testes teste-schema \
        verificar experimento experimento-baselines experimento-capital resultados \
        modelos validar notebooks limpar-intermediario limpar-cache

# ---------------------------------------------------------------- ambiente

help:  ## Lista os alvos disponíveis
	@echo "Alvos:"
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[1m%-24s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Variáveis (sobrescreva na linha de comando):"
	@echo "  RECORTE=$(RECORTE)      prefixo IBGE do recorte espacial"
	@echo "  MEM=$(MEM)         teto de memória do experimento (cgroup)"
	@echo "  PERIODOS=           competências do ETL; vazio = série canônica"
	@echo "  EPOCAS=$(EPOCAS)        máximo de épocas no treino"
	@echo ""
	@echo "Exemplos:"
	@echo "  make etl-periodo PERIODOS=202601"
	@echo "  make experimento RECORTE=355030"
	@echo "  make reprocessar-tabelas TABELAS=tbEstabelecimento PERIODO=202601"

setup:  ## Cria o .venv, instala o pacote e as extensões compiladas do PyG
	uv venv --python 3.12
	$(PIP) install -e .
	@echo ""
	@echo "As três extensões do PyG não existem no PyPI e precisam do índice"
	@echo "casado com a versão do torch:"
	$(PIP) install pyg-lib torch-scatter torch-sparse \
		--find-links https://data.pyg.org/whl/torch-2.9.0+cpu.html

# --------------------------------------------------------------------- ETL

etl:  ## ETL completo, competência por competência (baixa ~3,6 GB de ZIP; horas)
	@echo "Série canônica completa. Cada competência baixa, ingere e converte,"
	@echo "e o DuckDB intermediário é apagado ao fim de cada uma."
	$(PY) -m src.etl.pipeline

etl-periodo:  ## ETL de competências específicas (use PERIODOS="202501 202601")
	@test -n "$(PERIODOS)" || { echo "erro: informe PERIODOS, ex: make etl-periodo PERIODOS=202601"; exit 1; }
	$(PY) -m src.etl.pipeline --periodos $(PERIODOS)

mudancas:  ## Recalcula os eventos de mudança entre snapshots consecutivos
	@echo "Reprocessa o diff de todas as tabelas. Necessário depois de mexer em"
	@echo "chave natural ou em tipagem — ver D-27 e D-30."
	$(PY) -c "from src.etl.changes import detectar_mudancas, taxa_de_mudanca; \
		detectar_mudancas(reprocess=True); \
		t = taxa_de_mudanca(); \
		print(t[t.tabela == 'rlEstabEquipamento'][['periodo_destino','taxa_mudanca','chave_declarada']].to_string(index=False))"

reprocessar-tabelas:  ## Regera só algumas tabelas na camada primária (TABELAS=a,b PERIODO=YYYYMM)
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

# ----------------------------------------------------------------- testes

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

# ------------------------------------------------------------- experimento

experimento:  ## As três trilhas, com teto de memória (~55 min no estado, pico 6,3 GB)
	@echo "Recorte $(RECORTE), teto $(MEM). Resultado gravado incrementalmente em"
	@echo "docs/resultados/. Se o teto estourar, morre o experimento e não o ambiente."
	$(LIMITADOR) $(PY) -m tools.roda_experimento --recorte $(RECORTE) --epocas $(EPOCAS)

experimento-baselines:  ## Só a trilha 1, sem GNN (~15 min)
	$(LIMITADOR) $(PY) -m tools.roda_experimento --recorte $(RECORTE) --pular-gnn

experimento-capital:  ## As três trilhas no município da capital (barato, para depuração)
	$(MAKE) experimento RECORTE=355030 MEM=4G

resultados:  ## Mostra a tabela pareada do resultado mais recente
	@$(PY) -c "import json, pathlib; \
		arquivos = sorted(pathlib.Path('docs/resultados').glob('*-trilhas-*.json')); \
		print('nenhum resultado em docs/resultados/') if not arquivos else None; \
		d = json.loads(arquivos[-1].read_text()) if arquivos else {}; \
		print(f\"{arquivos[-1].name}  |  teste {d['particao']['teste']}\") if arquivos else None; \
		[print(f\"{n:20s} AP {m['average_precision']:.5f}  AUC {m['auc_roc']:.3f}  MAP@10 {m['map@10']:.4f}\") \
		 for n, m in sorted(d.get('teste_pareado', {}).items(), key=lambda x: -x[1]['average_precision'])]"

# --------------------------------------------------------------- artefatos

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

# ------------------------------------------------------------------- resto

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
