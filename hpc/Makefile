# Makefile do pipeline do servidor. Isolado do Makefile da raiz de propósito:
# são duas máquinas, e um alvo do servidor não deve estar a um TAB de distância
# de quem só quer rodar o experimento no notebook.
#
# ============================================================================
# ORDEM DE EXECUÇÃO NUMA MÁQUINA NOVA DO CLUSTER
# ============================================================================
#
#     export IC_HPC_DATA=/var/fasttmp/$USER/ic   # fora do repositório, sempre
#     make -f hpc/Makefile ambiente              # confere RAM, GPU, VRAM, CUDA
#     screen -S etl && make -f hpc/Makefile etl  # horas
#     screen -S bateria
#     make -f hpc/Makefile plano                 # o que vai rodar, sem rodar
#     make -f hpc/Makefile tudo                  # a bateria completa
#
# Da raiz, os mesmos alvos aparecem com prefixo: `make hpc-ambiente`,
# `make hpc-etl`, `make hpc-plano`, `make hpc-tudo`.
#
# O cluster do IME NÃO tem escalonador: rode sob `screen`, porque processo acima
# de 168 h pode ser morto e a sessão SSH cai bem antes disso. O ETL pula
# competência já convertida e o treino grava checkpoint por época, então relançar
# retoma em vez de recomeçar.
# ============================================================================

PY  := .venv/bin/python

# --- Escopo e técnica -------------------------------------------------------
# Recorte espacial: prefixo IBGE. Vazio = país inteiro, que é o ponto do servidor.
RECORTE ?=

# `compativel` replica as limitações da máquina de 9 GB em qualquer escopo;
# `completo` usa grafo por transição, atributo de aresta e negativos completos.
# As duas metades da matriz de D-34 saem daqui. É condição experimental, não
# compatibilidade de código.
MODO    ?= completo

EPOCAS  ?= 150
TRILHAS ?= todas
SEMENTE ?= 42

# --- Variante de pandemia ---------------------------------------------------
# Vazio = série completa. Qualquer valor = controle sem as transições que tocam
# 202001 ou 202101 (metodologia, seção 4.1).
SEM_PANDEMIA ?=
FLAG_PANDEMIA := $(if $(SEM_PANDEMIA),--excluir-pandemia,)

# --- Bateria completa -------------------------------------------------------
# Repetições por célula. 1 desliga a banda de ruído; 3 a mede. Duas execuções
# idênticas já divergiram 15% em AP de baseline, então sem repetição nenhuma
# diferença entre células é interpretável.
SEMENTES ?= 1

# Quais pipelines a bateria inclui: src | hpc | ambos.
SO ?= ambos

# --- Guardas ----------------------------------------------------------------
# Deixa o pipeline cair em CPU. Só para exercitar o caminho de código fora do
# servidor: o número não é comparável.
PERMITIR_CPU ?=
FLAG_CPU := $(if $(PERMITIR_CPU),--permitir-cpu,)

# Ignora a guarda de RAM de 64 GB. Existe porque a guarda é deliberada: rodar
# este pipeline numa estação de trabalho de 9 GB já travou a sessão do usuário
# uma vez. Não use com dado real fora do servidor.
PERMITIR_PEQUENA ?=
FLAG_PEQUENA := $(if $(PERMITIR_PEQUENA),--permitir-maquina-pequena,)

# Raiz de dados do servidor. Fora do repositório, obrigatoriamente: apontar para
# data/ sobrescreveria a camada primária do notebook.
IC_HPC_DATA ?= /var/fasttmp/$(USER)/ic
export IC_HPC_DATA

PERIODOS ?=

.DEFAULT_GOAL := help
.PHONY: help ambiente etl etl-de-zips grafos experimento matriz plano tudo \
        smoke limpar-intermediario

help:  ## Lista os alvos do pipeline do servidor
	@echo "======================================================================"
	@echo " Pipeline do servidor — escopo nacional, CUDA, sem as limitações de 9 GB"
	@echo "======================================================================"
	@echo ""
	@echo " Ordem numa máquina nova:"
	@echo "   export IC_HPC_DATA=/var/fasttmp/\$$USER/ic"
	@echo "   make -f hpc/Makefile ambiente"
	@echo "   make -f hpc/Makefile etl        # sob screen, horas"
	@echo "   make -f hpc/Makefile plano      # confere o que vai rodar"
	@echo "   make -f hpc/Makefile tudo       # sob screen, a bateria completa"
	@echo ""
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Variáveis:"
	@echo "  RECORTE=$(RECORTE)             prefixo IBGE; vazio = país inteiro"
	@echo "  MODO=$(MODO)          compativel | completo"
	@echo "  EPOCAS=$(EPOCAS)             máximo de épocas"
	@echo "  SEMENTE=$(SEMENTE)            semente de uma execução isolada"
	@echo "  SEMENTES=$(SEMENTES)           repetições por célula na bateria"
	@echo "  SEM_PANDEMIA=       qualquer valor liga o controle sem 2020/2021"
	@echo "  SO=$(SO)            bateria: src | hpc | ambos"
	@echo "  IC_HPC_DATA=$(IC_HPC_DATA)"
	@echo "  PERMITIR_CPU=       aceita CPU; o número deixa de ser comparável"
	@echo "  PERMITIR_PEQUENA=   ignora a guarda de 64 GB (não use com dado real)"
	@echo ""
	@echo "Rode sob screen: o cluster mata processo acima de 168 h."

# ============================================================ ambiente e ETL

ambiente:  ## Imprime o perfil da máquina: RAM, GPUs, VRAM, CUDA e raiz de dados
	$(PY) -m hpc.config.ambiente

etl:  ## ETL nacional, paralelo por competência, intermediário no SSD
	$(PY) -m hpc.etl.pipeline --periodos $(PERIODOS)

etl-de-zips:  ## Idem, partindo de ZIPs já enviados por rsync (sem baixar nada)
	$(PY) -m hpc.etl.pipeline --pular-download --periodos $(PERIODOS)

# ============================================================ modelagem

grafos:  ## Materializa os tensores de grafo por transição em 05_grafos
	$(PY) -m hpc.etl.grafo_store --recorte "$(RECORTE)" --modo $(MODO) \
		$(FLAG_PANDEMIA) $(FLAG_CPU) $(FLAG_PEQUENA)

experimento:  ## Uma célula: RECORTE, MODO e SEM_PANDEMIA escolhem qual
	@echo "recorte '$(RECORTE)' | modo $(MODO) | épocas $(EPOCAS) | semente $(SEMENTE)"
	$(PY) -m hpc.ml.experimento --recorte "$(RECORTE)" --modo $(MODO) \
		--epocas $(EPOCAS) --trilhas $(TRILHAS) --semente $(SEMENTE) \
		$(FLAG_PANDEMIA) $(FLAG_CPU) $(FLAG_PEQUENA)

matriz:  ## As quatro células de D-34 (técnica × escopo), série completa
	@echo "Quatro execuções em série, só o pipeline do servidor, só com pandemia."
	@echo "Para a bateria inteira — os dois pipelines, três escopos, duas"
	@echo "variantes — use 'tudo'."
	$(MAKE) -f hpc/Makefile experimento RECORTE=35 MODO=compativel
	$(MAKE) -f hpc/Makefile experimento RECORTE=   MODO=compativel
	$(MAKE) -f hpc/Makefile experimento RECORTE=35 MODO=completo
	$(MAKE) -f hpc/Makefile experimento RECORTE=   MODO=completo

# ============================================================ bateria completa

plano:  ## Imprime o que a bateria vai rodar, e o que já existe, sem rodar nada
	$(PY) -m hpc.roda_tudo --seco --so $(SO) --sementes $(SEMENTES) \
		--pasta-primaria $(IC_HPC_DATA)/03_primary

tudo:  ## BATERIA COMPLETA: 2 pipelines × 3 escopos × 2 variantes (retomável)
	@echo "======================================================================"
	@echo " Bateria completa. Rode sob screen: são muitas horas."
	@echo ""
	@echo " Cada execução é um subprocesso: uma queda perde só a execução em"
	@echo " curso, e relançar pula o que já tem resultado em docs/resultados/."
	@echo "======================================================================"
	$(PY) -m hpc.roda_tudo --so $(SO) --sementes $(SEMENTES) --epocas $(EPOCAS) \
		--pasta-primaria $(IC_HPC_DATA)/03_primary

# ============================================================ verificação

smoke:  ## Caminho completo na capital, em CPU (exige >= 64 GB de RAM)
	@echo "A guarda de RAM vai recusar em máquina pequena, e isso é intencional:"
	@echo "este caminho toca a camada primária inteira. Para exercitar a lógica sem"
	@echo "dado real, rode os testes sintéticos: pytest tests/test_hpc_*.py -q"
	$(MAKE) -f hpc/Makefile experimento RECORTE=355030 MODO=completo \
		EPOCAS=3 PERMITIR_CPU=1

limpar-intermediario:  ## Apaga a camada 02 da raiz do servidor (descartável)
	rm -rf $(IC_HPC_DATA)/02_intermediate/* $(IC_HPC_DATA)/temp_extract/*
	@echo "camada intermediária limpa em $(IC_HPC_DATA)"
