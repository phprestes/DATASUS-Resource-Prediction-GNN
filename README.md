# Escassez de recursos em redes de saúde: estrutura importa?

Projeto de Iniciação Científica sobre microdados do **CNES** (Cadastro Nacional
de Estabelecimentos de Saúde, DATASUS).

**Pedro H. S. Prestes** · orientação: Alexandre C. B. Delbem, Eric K. Tokuda

---

## 1. Introdução

### A pergunta

> Dado o estado observável da rede de saúde, é possível identificar onde faltam
> recursos assistenciais — e antecipar onde essa falta será suprida no período
> seguinte?

A hipótese é que a resposta depende da **estrutura da rede**, e não apenas dos
atributos isolados de cada estabelecimento. Um hospital sem tomógrafo cercado de
hospitais com tomógrafo é um caso qualitativamente diferente de um hospital sem
tomógrafo isolado a 40 km do próximo. Nenhum modelo que trate estabelecimentos
como linhas independentes de uma tabela distingue os dois.

Testar se essa distinção importa é o objeto do trabalho.

### O que isto é e o que não é

A contribuição **não** é uma rede neural de grafos. É a **diferença medida entre
três abordagens** que veem o mesmo rótulo com informação estrutural diferente:
nenhuma, relacional, geográfica. A GNN é instrumento de medição.

Isso tem uma consequência que orienta todo o desenho: **resultado negativo é
publicável**. Se as GNNs empatarem com o modelo tabular, a conclusão honesta é
que a estrutura do CNES não acrescenta poder preditivo para esta tarefa — e o
experimento foi montado para que essa afirmação possa ser feita com segurança,
em vez de confundida com falha de implementação.

### A limitação central, declarada

**Escassez não é observável no CNES.** O registro diz o que *existe*; não diz o
que era *necessário*. Não há coluna de demanda, fila ou população atendida.

A definição operacional adotada — predizer aquisição de equipamento — é uma
inferência sobre a regularidade da rede, não uma medição de necessidade clínica.
Um par (estabelecimento, equipamento) que o modelo prevê com alta probabilidade e
que não se concretiza é *candidato* a necessidade latente. É hipótese a discutir,
nunca resultado a reportar como fato.

---

## 2. Metodologia

Detalhamento completo em [`docs/02-metodologia.md`](docs/02-metodologia.md). O
racional de cada escolha, com o que foi rejeitado, está nas 25 decisões numeradas
de [`docs/03-decisoes.md`](docs/03-decisoes.md).

### 2.1 Amostra

| | |
|---|---|
| **Recorte espacial** | Estado de São Paulo — prefixo `35`, 645 municípios, ~136 mil estabelecimentos |
| **Recorte temporal** | Nove snapshots anuais de janeiro, 01/2017 a 01/2025 |
| **Fonte** | Banco de produção federal, ZIPs de competência de `cnes.datasus.gov.br` |

Não se usa TABNET nem a API ElasticCNES: as duas entregam dados agregados ou
recortados, e a integridade relacional necessária para montar o grafo só existe
nos microdados brutos.

### 2.2 O tempo é a parte sutil

Um ZIP de competência é uma **fotografia do estado atual**, não um log de
eventos, e guarda apenas a **última** `dt_atualizacao` de cada linha. Três
consequências que o código anterior ignorava:

- `to_chardt_atualizacaoddmmyyyy` é **censurada à direita**. Usá-la como eixo
  temporal atribui a cada linha um instante que depende de quando o snapshot foi
  tirado.
- Alterações entre dois snapshots são **irrecuperáveis**.
- A resolução temporal real do estudo é o **espaçamento entre snapshots**, não a
  granularidade diária da coluna de data.

Daí a unidade de análise ser a **transição** `t → t+1`, não a linha. Nove
snapshots dão oito transições. O eixo temporal do grafo é a **data do snapshot**
(1º de janeiro), que é exata e uniforme.

### 2.3 A tarefa

**Primária.** Classificação binária de aquisição, sobre o grafo bipartido
estabelecimento × tipo de equipamento:

> O estabelecimento `u`, que **não** possui equipamento do tipo `k` em `t`, passa
> a possuí-lo em `t+1`?

Escolhida por três razões: usa o sinal que de fato existe (`rlEstabEquipamento`
cresce 67% na série), é tarefa nativa de grafo — predição de aresta futura, onde
uma GNN tem vantagem estrutural real sobre um modelo tabular —, e produz o sinal
de escassez como subproduto.

**Secundária.** Regressão de `qt_existente`, para verificar se o ganho estrutural
sobrevive a uma mudança de formulação.

**Descartadas.** Taxa de utilização `qt_uso / qt_existente`, degenerada (moda 1
em ~69% das linhas nas duas colunas). Predição de leitos, alvo do código
anterior: 2.718 eventos contra 34.571 de equipamentos.

### 2.4 As três trilhas

Cada trilha isola uma fonte distinta de poder preditivo. Todas consomem **a mesma
tabela de rótulos e a mesma partição temporal**, e devolvem o mesmo tipo
`Previsao` — é o que torna a comparação pareada e não apenas justaposta.

| Trilha | Entrada | O que isola |
|---|---|---|
| **1. Baselines tabulares** | features achatadas, sem relação | quanto se explica sem estrutura nenhuma |
| **2. GNN relacional** | grafo do schema CNES | ganho da estrutura relacional |
| **3. GNN geográfica** | proximidade física apenas | ganho da vizinhança espacial |

**Trilha 1** tem cinco modelos: persistência ingênua, popularidade do item,
gradient boosting geral, gradient boosting só com o último snapshot, e um modelo
por entidade. Nenhum vê relação nem vizinhança — é esse o ponto.

**Trilha 2** monta o grafo tratando as tabelas de fato como **listas de arestas**,
não como tabelas de entidade. Uma linha de `rlEstabEquipamento` não é um objeto:
é a afirmação de que um estabelecimento tem um *tipo* de equipamento. Modelar um
nó por linha daria 76 milhões de nós e, pior, não criaria vizinho compartilhado
entre estabelecimentos com o mesmo equipamento — exatamente a estrutura que a
trilha existe para testar.

**Trilha 3** usa k-vizinhos mais próximos por distância de grande círculo sobre
`nu_latitude`/`nu_longitude`, simetrizado. Alcança 85,7% dos estabelecimentos; a
comparação com as outras trilhas é sempre feita **sobre o mesmo subconjunto de
nós**, senão mede diferença de amostra em vez de diferença de estrutura.

### 2.5 Protocolo de avaliação

**Partição temporal**, por transição e nunca sorteada — a tarefa é prever o
período seguinte, então divisão aleatória permitiria treinar no futuro:

| Conjunto | Transições |
|---|---|
| Treino | 2018, 2019, 2020, 2021, 2022 |
| Validação | 2023, 2024 |
| Teste | 2025 |

**Métricas.** A prevalência é 0,047% — um positivo a cada ~2.100 candidatos, 73
milhões de pares para 34 mil eventos.

- **MAP@10 por estabelecimento** é a métrica de destaque. Responde à pergunta que
  o trabalho faz — quais equipamentos este estabelecimento provavelmente deveria
  ter — ranqueando os 99 tipos dentro de cada unidade, onde o desbalanceamento
  global não distorce a escala.
- **Average precision** para comparar modelos. Preferida à AUC-ROC, que é
  otimista sob desbalanceamento severo. Seu valor absoluto **não** é
  interpretável aqui: com linha de base em 0,00047, um AP de 0,02 é quarenta
  vezes a prevalência e ainda parece zero. Sempre reportada com a prevalência ao
  lado.
- **AUC-ROC** como terciária, por comparabilidade com a literatura.

**Regra de reporte.** Nenhuma métrica de GNN é reportada sem a baseline de
persistência na mesma tabela. A versão anterior do projeto avaliava sobre
`train_mask` e reportava desempenho de treino como desempenho de teste; nada
detectou.

### 2.6 Três armadilhas que custaram correção

Vale registrar, porque cada uma produziria um resultado plausível e errado.

**Vazamento no grafo estático.** O grafo é único para treino, validação e teste.
Cortá-lo no fim da janela de treino deixa a última transição de treino com o
rótulo escrito no próprio grafo — a aresta estabelecimento↔equipamento em `t+1`
*é* o alvo. O corte correto é anterior a **todos** os rótulos.

**Amostragem de negativos.** Aplicada apenas ao **treino** (200:1). Validação e
teste ficam completos, senão a prevalência medida é artificial e o AP deixa de
significar o que diz significar.

**Empates em MAP@k.** Desfeitos aleatoriamente. Sem isso, um modelo de escore
constante — a persistência — herdaria a ordem das linhas da tabela como se fosse
capacidade preditiva.

---

## 3. Resultados

Conjunto de teste: transição 2025, 11.671.480 exemplos, 4.994 positivos,
prevalência 0,0428%.

<!-- RESULTADOS -->

---

## 4. Stack

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
| Testes | `pytest` 9.0.2 | 64 testes |

`pyg-lib`, `torch-scatter` e `torch-sparse` não existem no PyPI e exigem o índice
de wheels casado com a versão do torch — instruções no cabeçalho de
[`requirements.txt`](requirements.txt).

**Restrição de hardware que moldou o código:** a máquina de desenvolvimento tem
9 GB de RAM. A tabela de tarefa no recorte estadual custava 3,2 GB e derrubou o
ambiente; foi reduzida a 0,32 GB com codificação categórica compartilhada e Arrow
com dicionário. Código novo que toque a tabela não deve materializar `co_unidade`
como string nem copiar o frame inteiro.

---

## 5. Estrutura do projeto

```
docs/                        o contrato do projeto — o código é downstream daqui
  01-selecao-tabelas.md      FONTE DA VERDADE do schema; schema.py a lê no import
  02-metodologia.md          desenho experimental
  03-decisoes.md             25 decisões numeradas, com evidência e o rejeitado
  04-dados-externos.md       critério de admissão para fontes do SUS e do IBGE

src/
  paths.py                   localização das camadas de dados
  schema.py                  parser estrito de 01-selecao-tabelas.md
  extract.py                 estágio 1 — download dos ZIPs
  to_sql.py                  estágio 2 — CSV para DuckDB
  to_parquet.py              estágio 3 — DuckDB para Parquet tipado
  changes.py                 diff entre snapshots, eventos de mudança
  pipeline.py                orquestra o ETL competência por competência
  splits.py                  a partição temporal única
  tasks.py                   tabelas de rótulo: aquisição e quantidade
  baselines.py               trilha 1
  graph.py                   trilhas 2 e 3 — Database e grafo geográfico
  gnn.py                     encoders, decoder compartilhado, laço de treino
  metrics.py                 AP, AUC, MAP@k, RMSE/MAE

notebook/
  00_analise_alvo            gate empírico — executado, cinco vereditos fechados
  01_perfil_dados            perfil da camada primária
  02_relacoes                grafo do schema, derivado de schema.py
  03_modelagem               as três trilhas na mesma tabela
  04_recorte_e_dados_externos  recorte espacial e pré-requisitos do IBGE

tests/                       64 testes
tools/                       migrador de uso único, mantido como procedência
archieved/                   código pré-refatoração, API RelBench morta
data/                        nada versionado; reprodutível do estágio 1
```

### Camadas de dados

```
data/01_raw          BASE_DE_DADOS_CNES_{YYYYMM}.ZIP        ~2,9 GB
data/02_intermediate sql_cnes_{YYYYMM}.duckdb               descartável
data/03_primary      {YYYYMM}/{tabela}.parquet              ~2,7 GB
data/04_feature      changes/{tabela}/{periodo}.parquet     eventos de mudança
```

A competência `YYYYMM` é a chave de partição em toda parte.

### O ponto de projeto que organiza o resto

`docs/01-selecao-tabelas.md` é lido por [`src/schema.py`](src/schema.py) em tempo
de import e dele derivam `FACT_TABLES`, `CNES_USEFUL_COLUMNS`, `CNES_DTYPES`,
`CNES_PKEY`, `CNES_NATURAL_KEY` e `CNES_FKEY`. **Editar aquele Markdown muda o
pipeline.** Não existe segunda lista em código para manter em sincronia — a
divergência entre duas listas paralelas foi o bug que a refatoração eliminou.

---

## 6. Como rodar

### Instalação

```bash
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e .

# Extensões compiladas do PyG, fora do PyPI:
uv pip install pyg-lib torch-scatter torch-sparse \
  --find-links https://data.pyg.org/whl/torch-2.9.0+cpu.html
```

### ETL

O caminho recomendado é o orquestrador, que processa uma competência por vez e
descarta o DuckDB intermediário — o pico de disco fica em uma competência em vez
de nove, e a execução é retomável:

```bash
python -m src.pipeline                      # série canônica: 9 snapshots anuais
python -m src.pipeline --periodos 202401 202501
python -m src.pipeline --pular-download     # se os ZIPs já estão em disco
```

Estágios individuais, se preciso:

```bash
python -m src.extract      # ZIPs        -> data/01_raw
python -m src.to_sql       # CSV         -> data/02_intermediate
python -m src.to_parquet   # DuckDB      -> data/03_primary
python -m src.changes      # diffs       -> data/04_feature
```

Todos os estágios usam `reprocess=False` por padrão: a série tem vários GB e
rebaixar por acidente é caro.

### Testes

```bash
python -m pytest tests/ -q

# O teste que garante o invariante central do schema:
python -m pytest tests/test_schema.py::test_fact_tables_e_useful_columns_nao_podem_divergir
```

### Notebooks

Rodam a partir de `notebook/`, na ordem:

```bash
jupyter lab notebook/
```

`00_analise_alvo` é **ponto de decisão bloqueante** — as trilhas não devem rodar
antes dele estar executado e com os vereditos preenchidos.

### Modelagem por script

```python
from src import baselines, changes, graph, gnn, metrics, tasks
from src.splits import particionar

particao = particionar(changes.periodos_disponiveis())
tarefa = tasks.tarefa_aquisicao(particao, recorte=graph.RECORTE_PADRAO)

# Trilha 1
previsoes = baselines.rodar_todas(tarefa, particao, conjunto="teste")

# Trilha 2 — atenção ao corte do grafo
db = graph.montar_db(recorte=graph.RECORTE_PADRAO)
unidades = sorted(set(db.table_dict["tbEstabelecimento"].df["co_unidade"].to_pylist()))
indice = gnn.IndicePares.de(unidades, sorted(tarefa.df["co_equipamento"].cat.categories))
features = gnn.features_de_estabelecimento(db, unidades, ate_periodo=particao.antes_de_todos_os_rotulos)
dados = gnn.grafo_relacional_para_data(db, unidades, features,
                                       ate_periodo=particao.antes_de_todos_os_rotulos)
modelo, historico = gnn.treinar_aquisicao(tarefa, particao, dados, indice)
```

`ate_periodo` deve ser `antes_de_todos_os_rotulos`, **não** `fim_do_treino`. Usar
o segundo coloca o rótulo dentro do grafo; a função recusa a chamada sem o
parâmetro justamente por isso.

### Mudar o recorte

O recorte é um **prefixo de código IBGE**, hierárquico:

```python
graph.montar_db(recorte="35")       # estado de São Paulo (padrão)
graph.montar_db(recorte="355030")   # município da capital
graph.montar_db(recorte=None)       # país inteiro — exige memória de sobra
```

---

## 7. Conclusão

<!-- CONCLUSAO -->

---

## Licença e dados

Os microdados do CNES são públicos, publicados pelo DATASUS/Ministério da Saúde.
Nada sob `data/` é versionado; tudo é reprodutível a partir do estágio 1 do ETL.
