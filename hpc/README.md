# Pipeline do servidor

Como rodar o experimento no cluster do IME, do zero. Este pacote existe separado de
[`src/`](../src/) porque as duas coisas rodam em máquinas diferentes: `src/` é o que
roda no notebook do pesquisador, sob 9 GB de RAM; `hpc/` é o que roda no servidor, com
CUDA e recorte nacional. Ver D-34 em [`docs/03-decisoes.md`](../docs/03-decisoes.md).

**Não rode este pipeline numa estação de trabalho.** O código recusa abaixo de 64 GB
de RAM, e a recusa é deliberada: a tentativa de exercitar o caminho completo numa
máquina de 9 GB esgotou a memória do sistema e do editor. Para exercitar a lógica sem
dado real, use os testes sintéticos: `pytest tests/test_hpc_*.py -q`.

## Máquina

| Host | CPU | RAM | GPU |
|---|---|---|---|
| `brucutu` | 2× Xeon Gold 6148 | 512 GB | — |
| `brucutuvi` | 2× Xeon Gold 6148 | 512 GB | 1× Tesla V100 |
| `brucutuvii` | Threadripper PRO 7955WX | 440 GB | 2× RTX A6000 |

`brucutuvii` é a recomendada para treino, pela VRAM. `brucutu` serve para o ETL, que
não usa GPU. Três coisas do ambiente que o código trata em vez de assumir: a wiki não
documenta VRAM (medida em tempo de execução), não documenta acesso à internet no nó
(há alvo que parte de ZIPs enviados) e **não há escalonador** — processo acima de 168 h
pode ser morto, então rode sob `screen` e conte com o checkpoint por época.

## Do zero

```bash
# 1. Ambiente. Apptainer é a saída recomendada pela wiki quando as dependências
#    conflitam com o Debian do sistema.
uv venv --python 3.12 && source .venv/bin/activate
uv pip install -e .
uv pip install -r requirements-hpc.txt   # torch e PyG com índice CUDA

# 2. Onde os dados vão morar. Fora do repositório, obrigatoriamente: o código
#    recusa uma raiz dentro de data/, senão o servidor sobrescreveria a camada
#    primária do notebook.
export IC_HPC_DATA=/var/fasttmp/$USER/ic

# 3. Confirme o que a máquina tem antes de gastar horas nela.
make -f hpc/Makefile ambiente

# 4. ETL nacional. Sob screen: são horas.
screen -S etl
make -f hpc/Makefile etl
#    Sem internet no nó? Envie os ZIPs e use:
#    rsync -av data/01_raw/ servidor:$IC_HPC_DATA/01_raw/
#    make -f hpc/Makefile etl-de-zips

# 5. Confira que a camada produzida é a mesma do notebook, se tiver as duas.
python -m hpc.etl.pipeline --pular-download --conferir-contra /caminho/para/data/03_primary

# 6. As quatro células da matriz, em série.
screen -S matriz
make -f hpc/Makefile matriz
```

Da raiz do repositório os mesmos alvos aparecem com prefixo: `make hpc-ambiente`,
`make hpc-etl`, `make hpc-experimento RECORTE= MODO=completo`, `make hpc-matriz`.

## A matriz que este pipeline existe para medir

| | Escopo São Paulo | Escopo nacional |
|---|---|---|
| **`--modo compativel`** | célula A — reproduz o resultado do notebook | célula B |
| **`--modo completo`** | célula C | célula D |

O modo compatível replica **de propósito** as limitações de 9 GB: grafo estático
cortado antes de todos os rótulos, projeção de duas colunas por tabela filha,
negativos de treino a 200:1 e um passo de gradiente por época. Sem ele, a diferença
entre o número do notebook e o do servidor misturaria efeito de técnica com efeito de
escopo, e nenhum dos dois seria atribuível.

O modo completo levanta as quatro limitações:

| Limitação | Decisão | O que o modo completo faz |
|---|---|---|
| Recorte estadual | D-21 | `--recorte ""` roda o país: 602 mil estabelecimentos, 375 M pares |
| Grafo estático, 45% dos nós sem feature | D-25 | um grafo por transição, cortado na origem |
| 298 de 368 colunas fora do grafo | D-23 | projeção completa, vocabulário por coluna e peso na aresta |
| 200:1, validação amostrada, um passo por época | D-23 | negativos completos, validação completa, 120 passos |

## Camadas de dados

```
$IC_HPC_DATA/01_raw           ZIP de competência
$IC_HPC_DATA/02_intermediate  DuckDB por competência (descartável)
$IC_HPC_DATA/03_primary       Parquet tipado
$IC_HPC_DATA/04_feature       eventos de mudança
$IC_HPC_DATA/05_grafos        tensores de grafo por transição, por escopo e modo
```

A camada 05 é derivada e descartável, mas caro de recomputar: no recorte nacional são
nove grafos, e as células da matriz reusam os mesmos por escopo e modo. `make -f
hpc/Makefile grafos` materializa; `--reusar-grafos` no experimento carrega.

## O que sai de cada execução

Dois artefatos, e nenhum deles fica preso ao servidor:

- `docs/resultados/<data>-hpc-<escopo>-<modo>.json` — resumo com métricas, partição,
  perfil da máquina e tempos.
- `models/<data>-<trilha>-<escopo>-<modo>/` — pacote de modelo no **mesmo formato** do
  pipeline local: `state_dict` em CPU, manifesto, índice de nós e itens, histórico de
  treino e escore por exemplo. Ver [`models/README.md`](../models/README.md).

De volta no notebook, `make validar RUN=models/<pacote>` recomputa AP, AUC e MAP@10 a
partir do escore salvo, **sem GPU e sem camada de dados**, e confere contra o
manifesto. É o que torna verificável um número produzido no cluster.

## Se algo der errado

| Sintoma | Causa provável |
|---|---|
| `CUDA indisponível nesta máquina` | rodando fora do servidor, ou GPU ocupada; `--permitir-cpu` só para depurar |
| `pede ao menos 64 GB de RAM` | a guarda de máquina pequena; é intencional |
| `está dentro do repositório` | `IC_HPC_DATA` apontando para `data/`; escolha um caminho fora |
| processo morto sem log | corte de 168 h; retome — o ETL pula competência pronta e o treino tem checkpoint |
| ETL sem baixar nada | nó sem internet; use `etl-de-zips` com os ZIPs enviados |
