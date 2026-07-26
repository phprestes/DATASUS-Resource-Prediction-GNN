# Makefile do pipeline do servidor. Isolado do Makefile da raiz de propósito:
# são duas máquinas, e um alvo do servidor não deve estar a um TAB de distância
# de quem só quer rodar o experimento no notebook.
#
# Uso, sempre da raiz do repositório:
#     make -f hpc/Makefile
#     make -f hpc/Makefile ambiente
#     make -f hpc/Makefile experimento RECORTE= MODO=completo
#
# O cluster do IME não tem escalonador: rode sob `screen`, porque processo acima
# de 168 h pode ser morto e a sessão SSH cai antes disso.

PY  := .venv/bin/python

# Recorte espacial: prefixo IBGE. Vazio = país inteiro, que é o ponto do servidor.
RECORTE ?=

# `compativel` replica as limitações da máquina de 9 GB em qualquer escopo;
# `completo` usa grafo por transição, atributo de aresta e negativos completos.
# As duas metades da matriz de D-34 saem daqui.
MODO    ?= completo

EPOCAS  ?= 150
TRILHAS ?= todas

# Deixa o pipeline cair em CPU. Só para exercitar o caminho de código fora do
# servidor: o número não é comparável.
PERMITIR_CPU ?=
FLAG_CPU := $(if $(PERMITIR_CPU),--permitir-cpu,)

# Raiz de dados do servidor. Fora do repositório, obrigatoriamente.
IC_HPC_DATA ?= /var/fasttmp/$(USER)/ic
export IC_HPC_DATA

.DEFAULT_GOAL := help
.PHONY: help ambiente etl etl-de-zips grafos experimento matriz smoke limpar-intermediario

help:  ## Lista os alvos do pipeline do servidor
	@echo "======================================================================"
	@echo " Pipeline do servidor — recorte nacional, CUDA, sem as limitações de 9 GB"
	@echo "======================================================================"
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Variáveis:"
	@echo "  RECORTE=$(RECORTE)             prefixo IBGE; vazio = país inteiro"
	@echo "  MODO=$(MODO)          compativel | completo"
	@echo "  EPOCAS=$(EPOCAS)             máximo de épocas"
	@echo "  IC_HPC_DATA=$(IC_HPC_DATA)"
	@echo ""
	@echo "Rode sob screen: o cluster mata processo acima de 168 h."

ambiente:  ## Imprime o perfil da máquina: RAM, GPUs, VRAM, CUDA e raiz de dados
	$(PY) -m hpc.config.ambiente

etl:  ## ETL nacional, paralelo por competência, intermediário no SSD
	$(PY) -m hpc.etl.pipeline --periodos $(PERIODOS)

etl-de-zips:  ## Idem, partindo de ZIPs já enviados por rsync (sem baixar nada)
	$(PY) -m hpc.etl.pipeline --pular-download --periodos $(PERIODOS)

grafos:  ## Materializa os tensores de grafo por transição em 05_grafos
	$(PY) -m hpc.etl.grafo_store --recorte "$(RECORTE)" $(FLAG_CPU)

experimento:  ## Roda as trilhas no escopo e modo pedidos, salvando em models/
	@echo "recorte '$(RECORTE)' | modo $(MODO) | épocas $(EPOCAS)"
	$(PY) -m hpc.ml.experimento --recorte "$(RECORTE)" --modo $(MODO) \
		--epocas $(EPOCAS) --trilhas $(TRILHAS) $(FLAG_CPU)

matriz:  ## As quatro células de D-34: técnica × escopo, uma após a outra
	@echo "Quatro execuções em série. Rode sob screen."
	$(MAKE) -f hpc/Makefile experimento RECORTE=35 MODO=compativel
	$(MAKE) -f hpc/Makefile experimento RECORTE=   MODO=compativel
	$(MAKE) -f hpc/Makefile experimento RECORTE=35 MODO=completo
	$(MAKE) -f hpc/Makefile experimento RECORTE=   MODO=completo

smoke:  ## Caminho completo no recorte da capital, em CPU, para depurar fora do servidor
	$(MAKE) -f hpc/Makefile experimento RECORTE=355030 MODO=completo \
		EPOCAS=3 PERMITIR_CPU=1

limpar-intermediario:  ## Apaga a camada 02 da raiz do servidor (descartável)
	rm -rf $(IC_HPC_DATA)/02_intermediate/* $(IC_HPC_DATA)/temp_extract/*
	@echo "camada intermediária limpa em $(IC_HPC_DATA)"
