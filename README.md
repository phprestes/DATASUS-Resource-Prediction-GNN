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
| **Recorte espacial** | Estado de São Paulo — prefixo `35`, 645 municípios, ~146 mil estabelecimentos em 01/2026 |
| **Recorte temporal** | Dez snapshots anuais de janeiro, 01/2017 a 01/2026 (D-29) |
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

Daí a unidade de análise ser a **transição** `t → t+1`, não a linha. Dez
snapshots dão nove transições. O eixo temporal do grafo é a **data do snapshot**
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
anterior: 3.062 eventos contra 40.880 de equipamentos, somando as nove transições.

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
`nu_latitude`/`nu_longitude`, simetrizado. Alcança 87,3% dos estabelecimentos em
01/2026; a
comparação com as outras trilhas é sempre feita **sobre o mesmo subconjunto de
nós**, senão mede diferença de amostra em vez de diferença de estrutura.

### 2.5 Protocolo de avaliação

**Partição temporal**, por transição e nunca sorteada — a tarefa é prever o
período seguinte, então divisão aleatória permitiria treinar no futuro:

| Conjunto | Transições |
|---|---|
| Treino | 2018, 2019, 2020, 2021, 2022, 2023 |
| Validação | 2024, 2025 |
| Teste | 2026 |

A janela é derivada da série, não configurada: a transição mais recente testa, as
duas anteriores validam, o resto treina. Cada competência nova desloca tudo um ano
adiante — os resultados abaixo foram medidos com **teste em 2025**, sob a série de
nove snapshots, e continuam válidos para aquela divisão.

**Métricas.** A prevalência é 0,0472% — um positivo a cada ~2.100 candidatos, 86,7
milhões de pares para 40,9 mil eventos.

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

A tabela que vale é a **pareada**: só ela compara as três trilhas sobre o mesmo
conjunto de nós. A trilha 3 alcança apenas os estabelecimentos com coordenada, e
comparar métricas em populações diferentes mediria diferença de amostra, não de
estrutura.

**Teste 2026 · 127.868 estabelecimentos posicionáveis · 11.411.933 exemplos ·
6.309 positivos · prevalência 0,0553%** — série de dez snapshots (D-29).

| Modelo | Trilha | AP | AUC-ROC | MAP@10 |
|---|---|---|---|---|
| `gnn_relacional` | 2 | **0,01061** | **0,849** | **0,3000** |
| `gnn_geografica` | 3 | 0,00490 | 0,816 | 0,2745 |
| `gbdt_geral` | 1 | 0,00355 | 0,766 | 0,2567 |
| `popularidade_item` | 1 | 0,00220 | 0,700 | 0,2714 |
| `persistencia` | 1 | 0,00055 | 0,500 | 0,0324 |

Custo: 1.668 s de treino na trilha 2, com melhor época em 99; 160 s na trilha 3,
melhor época em 26. Grafo relacional com 25 tipos de nó e 48 relações; grafo
geográfico com 127.868 nós e 1.913.816 arestas.

A execução anterior, sob teste 2025 e nove snapshots, está em D-26 e continua
válida para aquela divisão. A comparação entre as duas aparece abaixo, com a
ressalva de que três coisas mudaram junto.

### O arcabouço está calibrado

`persistencia` devolve AP **exatamente** igual à prevalência e AUC **exatamente**
0,500. Não é coincidência — é o que a construção exige, e serve de verificação de
que o pipeline de avaliação não se quebrou ao mudar de série, de partição e de
subconjunto. Se um dia divergir, o erro está no arcabouço, não no modelo.

### A estrutura acrescenta, e agora nas duas dimensões

A GNN relacional entrega **19,2 vezes a prevalência** em AP, contra 6,4 do
gradient boosting tabular; em AUC, 0,849 contra 0,766. E, diferente da execução
de D-26, ela também lidera **MAP@10**: 0,300 contra 0,271 de `popularidade_item`.

Isso responde afirmativamente à pergunta de pesquisa nas duas dimensões que as
métricas separam. **AP e AUC** são globais e ordenam todos os pares juntos, onde
acertar *quais estabelecimentos* adquirem muito já melhora a ordenação. **MAP@10**
fixa o estabelecimento e ordena os 99 equipamentos dentro dele, onde o componente
"qual estabelecimento" some por construção e sobra o de item — que era exatamente
onde D-26 registrou derrota para o modelo mais simples de todos.

### O que mudou desde D-26, e por que a atribuição não é limpa

| Modelo | AP em D-26 | AP agora | MAP@10 em D-26 | MAP@10 agora |
|---|---|---|---|---|
| `gnn_relacional` | 0,00478 | **0,01061** | 0,2133 | **0,3000** |
| `gnn_geografica` | 0,00378 | 0,00490 | 0,2077 | 0,2745 |
| `gbdt_geral` | 0,00280 | 0,00355 | 0,2520 | 0,2567 |
| `popularidade_item` | 0,00215 | 0,00220 | **0,2957** | 0,2714 |
| `persistencia` | 0,00051 | 0,00055 | 0,0354 | 0,0324 |

As baselines mexeram pouco; as duas GNNs mexeram muito, e a relacional mais que
dobrou em AP. Três mudanças entraram ao mesmo tempo e **nenhum ablation foi
rodado**, então o ganho não é atribuível a uma só:

1. **A partição andou um ano.** Teste 2026 em vez de 2025, e seis transições de
   treino em vez de cinco.
2. **O grafo relacional ficou correto.** D-28 removeu 33 chaves estrangeiras que
   não juntavam nada — medido, zero valores casando — e devolveu
   `rlEstabEquipeProf`, uma tabela de 815 mil linhas, para a raiz; antes ela era
   a única tabela de fato sem aresta para `tbEstabelecimento`.
3. **O treino foi mais longe.** Melhor época 99 contra 47, com os mesmos
   hiperparâmetros — a parada antecipada só disparou depois, porque a validação
   continuou melhorando.

O terceiro item enfraquece a leitura de D-26 sobre a dimensão de item: a hipótese
lá era que o decoder não convergia no componente de item, e o treino mais longo é
consistente com isso.

### Relacional supera geográfica com folga

AP de 0,01061 contra 0,00490 e AUC de 0,849 contra 0,816. Em D-26 as duas
empatavam em AUC e a diferença de AP era pequena, o que sustentava a leitura de
que a proximidade física capturava quase todo o sinal estrutural. Com o grafo
relacional corrigido, essa leitura cai: a estrutura do schema rende mais que a
vizinhança geográfica — a um custo de treino dez vezes maior, 1.668 s contra 160 s.

### O subconjunto posicionável não é aleatório

A prevalência sobe de 0,0478% no conjunto completo para **0,0553%** no pareado. O
motivo é mais forte do que em D-26: os **6.309 positivos do teste estão todos em
estabelecimentos posicionáveis**. Quem adquire equipamento está georreferenciado,
sem exceção nesta transição. Reforça a obrigação de comparar pareado — sem isso a
trilha 3 pareceria melhor do que é apenas por avaliar numa população mais fácil.

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
| Testes | `pytest` 9.0.2 | 67 testes |

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

tests/                       67 testes
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
da série inteira, e a execução é retomável:

```bash
python -m src.pipeline                      # série canônica: 10 snapshots anuais
python -m src.pipeline --periodos 202501 202601
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

### Reproduzir o experimento completo

```bash
python -m tools.roda_experimento                      # as três trilhas
python -m tools.roda_experimento --pular-gnn          # só as baselines (~10 min)
python -m tools.roda_experimento --recorte 355030     # só a capital
```

Escreve `docs/resultados/{data}-trilhas-{recorte}.json` **incrementalmente**, a
cada modelo — uma queda no meio da trilha 3 preserva o que a 1 e a 2 já mediram.
Leva cerca de 45 minutos no estado, com pico de 5,1 GB de RAM.

O resultado da execução documentada na seção 3 está em
[`docs/resultados/2026-07-25-trilhas-estado-sp.json`](docs/resultados/2026-07-25-trilhas-estado-sp.json).

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

### A resposta, com a ressalva junto

**A estrutura da rede carrega informação sobre onde recursos serão adquiridos.**
A GNN relacional entrega 19,2 vezes a prevalência em average precision, contra
6,4 do melhor modelo sem estrutura, e AUC de 0,849 contra 0,766.

**E agora vence também em MAP@10**, a métrica que reflete o uso pretendido —
ranquear equipamentos dentro de um estabelecimento: 0,300 contra 0,271 do modelo
que só conhece a popularidade de cada tipo. Sob a execução anterior (D-26,
teste 2025) essa comparação era o contrário, e a derrota em MAP@10 era o resultado
mais desconfortável do trabalho.

**A ressalva é de atribuição, não de medição.** Três coisas mudaram entre as duas
execuções — a partição andou um ano, o grafo relacional foi corrigido (D-28, com
33 chaves estrangeiras que não juntavam nada e uma tabela de 815 mil linhas
reconectada à raiz) e o treino foi até a época 99 em vez de parar na 47. Nenhum
ablation foi rodado, então o quanto cada uma contribuiu continua aberto. O que se
pode afirmar é que as baselines quase não se moveram e as duas GNNs se moveram
muito, o que aponta para as mudanças estruturais e não para a troca de ano.

### O que o trabalho estabeleceu, além do número

O desenho experimental é a contribuição mais sólida desta iteração:

- **A comparação é pareada de verdade.** As três trilhas consomem a mesma tabela
  de rótulos, a mesma partição temporal, e são avaliadas sobre o mesmo
  subconjunto de nós.
- **O piso é verificável.** A baseline de persistência devolve AP exatamente
  igual à prevalência e AUC exatamente 0,500. Qualquer desvio denuncia erro no
  arcabouço.
- **Os vieses estão quantificados, não mencionados.** O subconjunto com
  coordenada tem prevalência 16% maior que a população — e concentra **todos** os
  6.309 positivos do teste; está escrito ao lado do resultado.
- **As decisões estão auditáveis.** Trinta e duas entradas em
  [`docs/03-decisoes.md`](docs/03-decisoes.md), cada uma com a evidência que a
  motivou e o que foi rejeitado.

### Erros encontrados e corrigidos ao longo do caminho

Vale listar, porque cada um teria produzido um resultado plausível e errado:

| Erro | Efeito se não corrigido |
|---|---|
| `test()` avaliava sobre `train_mask` | desempenho de treino reportado como de teste |
| Grafo estático cortado no fim do treino | rótulo dentro do grafo na última transição de treino |
| Um nó por linha de tabela de fato | 76 milhões de nós, e nenhum vizinho compartilhado entre unidades com o mesmo equipamento |
| Chave estrangeira apontando para tabela não materializada | referência pendurada no grafo do RelBench |
| Teto de coordenada medido em 6 de 9 snapshots | 57% em vez dos 87,3% reais; trilha 3 quase descartada |
| Chave estrangeira transcrita coluna a coluna de uma FK composta | 33 declarações com zero valores casando, e a tabela de profissionais das equipes sem aresta para a raiz |
| `CHAR(n)` do Oracle comparado sem normalizar | `'1'` contra `'1 '` em 202601: tabela do alvo inteira contada como substituída |
| Diff usando a lista de colunas de um lado só | três transições desaparecendo do resumo de mudança sem erro visível |
| Empates de MAP@k desfeitos pela ordem das linhas | escore constante parecendo ranqueador competente |

### Limites que continuam de pé

**Escassez continua inferida.** O resultado é sobre *aquisição*, não sobre
*necessidade*. A ponte entre as duas é hipótese declarada, e só dado de demanda —
a produção ambulatorial do SIA/SUS é a fonte candidata — pode fechá-la.

**O grafo é estático, e as features também.** Cortado em 2017 para não vazar
rótulo, ele descreve uma rede nove anos mais velha que o conjunto de teste. Pior:
as features de nó saem do mesmo corte, e o recorte tinha 80.073 estabelecimentos
em 2017 contra 146.679 na série — **45% dos nós entram com vetor de features
vazio**. Um grafo temporal com visibilidade por exemplo é a extensão de maior
valor para as trilhas estruturais.

**O grafo relacional é topologia pura.** A projeção mínima que faz a montagem
caber em 9 GB entrega cada tabela filha como duas colunas, então 298 das 368
colunas `util` das tabelas de fato ficam fora — a GNN sabe que a unidade *tem*
um tipo de equipamento e não sabe quantos, nem se está disponível ao SUS, nem
desde quando.

**Um estado, e uma virada sem ablation.** A generalização para outros estados não
foi testada. E a inversão do resultado de MAP@10 entre duas execuções que mudaram
três coisas ao mesmo tempo é exatamente o tipo de achado que pede decomposição
antes de virar afirmação forte.

### Próximos passos, em ordem de valor sobre custo

1. **Ablation da virada.** Rodar o teste 2026 com as chaves estrangeiras antigas,
   e o teste 2025 com o grafo corrigido, separa o efeito da partição do efeito da
   estrutura. É a única pendência que hoje impede uma afirmação forte.
2. **Peso na aresta e features no fim do treino.** As duas devolvem informação
   que a projeção mínima e o corte de vazamento hoje descartam, e nenhuma exige
   arquitetura nova.
3. **Modelo combinado GNN + popularidade do item.** Ainda vale medir: se o
   combinado superar 0,300 em MAP@10, o componente de item continua subaproveitado.
4. **Grafo temporal.** Remove o handicap de nove anos imposto às trilhas
   estruturais pela correção de vazamento.
5. **População municipal do IBGE.** Desbloqueada pela expansão para o estado —
   645 municípios dão variância onde um só dava constante.
6. **Produção ambulatorial do SIA/SUS.** A única fonte que transformaria escassez
   inferida em escassez com demanda observada. Também a mais cara, e sujeita ao
   viés de cobertura descrito em
   [`docs/04-dados-externos.md`](docs/04-dados-externos.md).

---

## Licença e dados

Os microdados do CNES são públicos, publicados pelo DATASUS/Ministério da Saúde.
Nada sob `data/` é versionado; tudo é reprodutível a partir do estágio 1 do ETL.
