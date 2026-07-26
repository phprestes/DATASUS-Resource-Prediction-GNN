# CNES — escassez de recursos em redes de saúde

Projeto de Iniciação Científica sobre microdados do **CNES** (Cadastro Nacional de
Estabelecimentos de Saúde, DATASUS). Mede se a **estrutura** de uma rede de saúde
— quem está perto de quem, quem compartilha o quê — carrega informação sobre onde
recursos serão adquiridos, além do que os atributos isolados de cada
estabelecimento explicam.

Três trilhas veem o mesmo rótulo com informação estrutural diferente: **nenhuma**
(baselines tabulares), **relacional** (grafo do schema CNES) e **geográfica**
(vizinhança física), sob a mesma partição temporal e o mesmo subconjunto de nós. A
contribuição é a diferença medida entre elas; a rede neural de grafos é instrumento
de medição.

**Pedro H. S. Prestes** · orientação: Alexandre C. B. Delbem, Eric K. Tokuda

> O argumento científico — pergunta, hipótese, metodologia, resultados e conclusão
> em formato de artigo — está em
> [`docs/05-esboco-artigo.md`](docs/05-esboco-artigo.md). Este README descreve o
> repositório.

## Sumário

- [Resultado atual](#resultado-atual)
- [Stack](#stack)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Arquitetura](#arquitetura)
- [Como rodar](#como-rodar)
- [Testes](#testes)
- [Documentação](#documentação)
- [Licença e dados](#licença-e-dados)

## Resultado atual

Recorte estadual (São Paulo), transição de teste 2026, tabela **pareada** sobre os
127.868 estabelecimentos posicionáveis — 11.411.933 exemplos, 6.309 positivos,
prevalência 0,0553%:

| Modelo | Trilha | AP | AUC-ROC | MAP@10 |
|---|---|---|---|---|
| `gnn_relacional` | 2 | **0,01061** | **0,849** | **0,3000** |
| `gnn_geografica` | 3 | 0,00490 | 0,816 | 0,2745 |
| `gbdt_geral` | 1 | 0,00355 | 0,766 | 0,2567 |
| `popularidade_item` | 1 | 0,00220 | 0,700 | 0,2714 |
| `persistencia` | 1 | 0,00055 | 0,500 | 0,0324 |

A GNN relacional lidera as duas métricas, com 19,2 vezes a prevalência em AP contra
6,4 do gradient boosting tabular. **A atribuição não é limpa:** três mudanças
entraram entre esta execução e a anterior, e o ablation que as separa está pendente
— leia D-32 antes de citar o número.

`persistencia` devolve AP exatamente igual à prevalência e AUC exatamente 0,500. É o
piso verificável do arcabouço: se um dia divergir, o erro está na avaliação e não no
modelo.

Interpretação completa em [`docs/05-esboco-artigo.md`](docs/05-esboco-artigo.md) e
em D-32 de [`docs/03-decisoes.md`](docs/03-decisoes.md). Resultados brutos em
[`docs/resultados/`](docs/resultados/); `make resultados` imprime o mais recente.

## Stack

Python 3.12 em `.venv`, gerenciado por **uv**.

| Camada | Ferramenta | Papel |
|---|---|---|
| ETL | `requests`, `duckdb` 1.5.2 | download e ingestão dos ZIPs de competência |
| Armazenamento | `pyarrow` 23.0.1 (Parquet) | camada primária tipada e comprimida |
| Manipulação | `pandas` 3.0.2 | tabelas de tarefa e features |
| Modelagem clássica | `scikit-learn` 1.6.1 | `HistGradientBoosting`, métricas |
| Grafos | `relbench` 2.1.1, `torch-geometric` 2.7.0 | `Database` relacional e camadas GNN |
| Deep learning | `torch` 2.9.1 | treino |
| Análise | `matplotlib`, `seaborn`, `networkx`, `jupyter` | notebooks |
| Testes | `pytest` 9.0.2 | 67 testes |

`pyg-lib`, `torch-scatter` e `torch-sparse` não existem no PyPI e exigem o índice de
wheels casado com a versão do torch — `make setup` resolve, e o cabeçalho de
[`requirements.txt`](requirements.txt) documenta.

## Estrutura do projeto

```
Makefile                     atalhos documentados; `make` lista tudo

docs/                        o contrato do projeto — o código é downstream daqui
  01-selecao-tabelas.md      FONTE DA VERDADE do schema; schema.py a lê no import
  02-metodologia.md          desenho experimental detalhado
  03-decisoes.md             32 decisões numeradas, com evidência e o rejeitado
  04-dados-externos.md       critério de admissão para fontes do SUS e do IBGE
  05-esboco-artigo.md        estrutura do artigo e o que falta escrever
  resultados/                JSON de cada execução das trilhas
  DICIONARIO_DE_DADOS.pdf    dicionário do DATASUS (descreve o Oracle, não o CSV)

src/
  paths.py                   localização das camadas de dados
  schema.py                  parser estrito de 01-selecao-tabelas.md
  extract.py                 estágio 1 — download dos ZIPs
  to_sql.py                  estágio 2 — CSV para DuckDB
  to_parquet.py              estágio 3 — DuckDB para Parquet tipado
  pipeline.py                orquestra o ETL competência por competência
  changes.py                 diff entre snapshots, eventos de mudança
  splits.py                  a partição temporal única
  tasks.py                   tabelas de rótulo: aquisição e quantidade
  baselines.py               trilha 1
  graph.py                   trilhas 2 e 3 — Database e grafo geográfico
  gnn.py                     encoders, decoder compartilhado, laço de treino
  metrics.py                 AP, AUC, MAP@k, RMSE/MAE

notebook/
  00_analise_alvo            gate empírico — bloqueante, cinco vereditos fechados
  01_perfil_dados            perfil da camada primária
  02_relacoes                grafo do schema, derivado de schema.py
  03_modelagem               as três trilhas na mesma tabela
  04_recorte_e_dados_externos  recorte espacial e pré-requisitos do IBGE

tests/                       67 testes
tools/                       roda_experimento.py e o migrador de procedência
archieved/                   código pré-refatoração, API RelBench morta
data/                        nada versionado; reprodutível do estágio 1
```

## Arquitetura

### Camadas de dados

```
data/01_raw          BASE_DE_DADOS_CNES_{YYYYMM}.ZIP        ~3,6 GB
data/02_intermediate sql_cnes_{YYYYMM}.duckdb               descartável
data/03_primary      {YYYYMM}/{tabela}.parquet              ~2,7 GB
data/04_feature      changes/{tabela}/{periodo}.parquet     eventos de mudança
```

Cada estágio lê a camada anterior e escreve a seguinte. A competência `YYYYMM` é a
chave de partição em toda parte. A amostra canônica são dez snapshots anuais de
janeiro, 01/2017 a 01/2026 — nove transições.

### O ponto de projeto que organiza o resto

[`docs/01-selecao-tabelas.md`](docs/01-selecao-tabelas.md) é lido por
[`src/schema.py`](src/schema.py) em tempo de import, e dele derivam `FACT_TABLES`,
`CNES_EXTRACT_COLUMNS`, `CNES_USEFUL_COLUMNS`, `CNES_DTYPES`, `CNES_PKEY`,
`CNES_NATURAL_KEY` e `CNES_FKEY`.

**Editar aquele Markdown muda o pipeline.** Não existe segunda lista em código para
manter em sincronia — a divergência entre duas listas paralelas foi o bug que a
refatoração eliminou (D-05). Admitir uma coluna nova exige regerar a camada
primária: `make reprocessar-tabelas` faz isso só nas tabelas afetadas.

### O tempo é a parte sutil

Um ZIP de competência é **fotografia do estado atual**, não log de eventos, e guarda
apenas a **última** data de atualização de cada linha. Portanto:

- A coluna de atualização é **censurada à direita**; usá-la como eixo temporal
  atribui a cada linha um instante que depende de quando o snapshot foi tirado.
- Alteração entre dois snapshots é **irrecuperável**.
- A resolução temporal real é o **espaçamento entre snapshots**, não a granularidade
  diária da coluna de data.

Daí a unidade de análise ser a **transição** `t → t+1`
([`src/changes.py`](src/changes.py)), e o eixo temporal do grafo ser a data do
snapshot, exata e uniforme. Eventos dão os rótulos; snapshots dão o estado (D-08).

### Comparabilidade é o que o desenho protege

As três trilhas consomem a mesma `TabelaTarefa`, a mesma `ParticaoTemporal` e
devolvem o mesmo tipo `Previsao`, de modo que [`src/metrics.py`](src/metrics.py)
coloca tudo numa tabela só. Duas regras que não se negociam:

- **Nunca reportar número de GNN sem a baseline de persistência ao lado** (D-11).
- **A trilha 1 fica livre de feature relacional ou espacial.** Agregado de
  vizinhança nas baselines apagaria a diferença que o experimento existe para medir.

### Restrição de hardware que moldou o código

A máquina de referência tem 9 GB de RAM. A tabela de tarefa no recorte estadual
custava 3,2 GB e derrubou o ambiente; foi reduzida a 0,32 GB com codificação
categórica compartilhada e Arrow com dicionário (D-23). O experimento completo pica
em 6,3 GB, e por isso `make experimento` roda dentro de um cgroup com teto: se
estourar, morre o experimento e não a sessão do usuário.

Código novo que toque a tabela de tarefa não deve materializar `co_unidade` como
string nem copiar o frame inteiro — use `TabelaTarefa.codigos()` e
`Previsao.mascara_de_entidades()`.

## Como rodar

Tudo passa pelo Makefile. `make` sem argumento lista os alvos, as variáveis e
exemplos de uso:

```bash
make
```

| Alvo | O que faz |
|---|---|
| `make setup` | cria o `.venv`, instala o pacote e as extensões do PyG |
| `make etl` | ETL completo da série canônica (horas, ~3,6 GB de download) |
| `make etl-periodo PERIODOS=202601` | ETL de competências específicas |
| `make mudancas` | recalcula os eventos de mudança entre snapshots |
| `make reprocessar-tabelas TABELAS=… PERIODO=…` | regera só as tabelas afetadas por uma coluna nova |
| `make testes` | suíte completa |
| `make verificar` | testes mais o resumo do schema derivado do doc |
| `make experimento` | as três trilhas, com teto de memória (~55 min) |
| `make experimento-baselines` | só a trilha 1 (~15 min) |
| `make experimento-capital` | as três trilhas na capital, barato para depuração |
| `make resultados` | imprime a tabela pareada do resultado mais recente |
| `make notebooks` | abre o Jupyter Lab |
| `make limpar-intermediario` | apaga a camada 02, que é descartável |

Variáveis sobrescrevíveis: `RECORTE` (prefixo IBGE, padrão `35`), `MEM` (teto de
memória, padrão `7G`), `EPOCAS`, `PERIODOS`, `TABELAS`, `PERIODO`.

### Primeira execução, do zero

```bash
make setup
make etl                # ou: make etl-periodo PERIODOS="202501 202601"
make mudancas
make testes
make notebooks          # rode 00_analise_alvo antes de qualquer modelagem
make experimento
```

O ETL é **retomável** e todos os estágios usam `reprocess=False` por padrão: a série
tem vários gigabytes e rebaixar por acidente é caro.

### Recorte espacial

Prefixo hierárquico de código IBGE, aceito pelo `make` e pelas funções:

```bash
make experimento RECORTE=35        # estado de São Paulo (padrão)
make experimento RECORTE=355030    # município da capital
```

```python
graph.montar_db(recorte="35")       # estado
graph.montar_db(recorte=None)       # país inteiro — exige memória de sobra
```

### Uso por script

```python
from src import baselines, changes, graph, gnn, tasks
from src.splits import particionar

particao = particionar(changes.periodos_disponiveis())
tarefa = tasks.tarefa_aquisicao(particao, recorte=graph.RECORTE_PADRAO)

# Trilha 1
previsoes = baselines.rodar_todas(tarefa, particao, conjunto="teste")

# Trilha 2 — atenção ao corte do grafo
db = graph.montar_db(recorte=graph.RECORTE_PADRAO,
                     colunas=graph.colunas_minimas_para_grafo())
unidades = sorted(set(db.table_dict["tbEstabelecimento"].df["co_unidade"].to_pylist()))
indice = gnn.IndicePares.de(unidades, sorted(tarefa.df["co_equipamento"].cat.categories))
corte = particao.antes_de_todos_os_rotulos
features = gnn.features_de_estabelecimento(db, unidades, ate_periodo=corte)
dados = gnn.grafo_relacional_para_data(db, unidades, features, ate_periodo=corte)
modelo, historico = gnn.treinar_aquisicao(tarefa, particao, dados, indice)
```

`ate_periodo` deve ser `antes_de_todos_os_rotulos`, **não** `fim_do_treino`: o
segundo coloca o rótulo dentro do grafo, e a função recusa a chamada sem o parâmetro
justamente por isso (D-25).

## Testes

```bash
make testes          # 67 testes
make teste-schema    # só o invariante central do schema
```

Os testes são deliberadamente **negativos**: existem para que a partição temporal, o
schema e o diff entre snapshots **falhem** em vez de produzir silenciosamente um
número bonito e errado. Cada modo de falha coberto já ocorreu ao menos uma vez neste
projeto.

## Documentação

Os cinco documentos de `docs/` são o contrato do projeto — não são resumo do código,
o código é que é downstream deles.

| Documento | Papel |
|---|---|
| [`01-selecao-tabelas.md`](docs/01-selecao-tabelas.md) | fonte da verdade do schema; editar muda o pipeline |
| [`02-metodologia.md`](docs/02-metodologia.md) | pergunta, definição operacional, trilhas, protocolo |
| [`03-decisoes.md`](docs/03-decisoes.md) | 32 decisões numeradas, com evidência e o que foi rejeitado |
| [`04-dados-externos.md`](docs/04-dados-externos.md) | teste de admissão para fonte externa |
| [`05-esboco-artigo.md`](docs/05-esboco-artigo.md) | estrutura do artigo e checklist de redação |

Quando algo no código parecer surpreendente, a razão costuma estar numa entrada
`D-nn` de `03-decisoes.md`.

## Licença e dados

Os dados do CNES são públicos, publicados pelo DATASUS. Nada sob `data/` é
versionado: tudo é reprodutível a partir do estágio 1 do ETL.
