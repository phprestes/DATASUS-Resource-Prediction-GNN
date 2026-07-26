# Metodologia

Documento de referência do desenho experimental. Define a pergunta de pesquisa,
como escassez é medida, qual é a amostra, como o tempo é tratado, quais modelos
competem e sob qual protocolo de avaliação.

Complementa [`01-selecao-tabelas.md`](01-selecao-tabelas.md), que define *quais
dados* entram, e [`03-decisoes.md`](03-decisoes.md), que registra *por que* cada
escolha aqui foi feita e o que foi descartado.

## 1. Pergunta de pesquisa

> Dado o estado observável da rede de saúde de um município, é possível
> identificar onde faltam recursos assistenciais — e antecipar onde essa falta
> será suprida no período seguinte?

A hipótese de trabalho é que a resposta depende da **estrutura da rede**, e não
apenas dos atributos isolados de cada estabelecimento. Um hospital sem
tomógrafo num bairro cercado de hospitais com tomógrafo é um caso
qualitativamente diferente de um hospital sem tomógrafo isolado a 40 km do
próximo. Nenhum modelo que trate estabelecimentos como linhas independentes de
uma tabela consegue distinguir os dois. Testar se essa distinção importa é o
objeto do trabalho.

## 2. Definição operacional de escassez

Escassez não é observável no CNES. O registro diz o que **existe**; não diz o
que era **necessário**. Não há coluna de demanda, fila, ou população atendida.
Qualquer definição operacional é, portanto, uma inferência — e precisa ser
declarada como tal.

### 2.1 Alvo primário: evento de aquisição

Sobre o grafo bipartido **estabelecimento × tipo de equipamento**, prever:

> O estabelecimento `u`, que não possui equipamento do tipo `k` no snapshot
> `t`, passa a possuí-lo no snapshot `t+1`?

Rótulo binário, derivado dos eventos de mudança de
[`src/etl/changes.py`](../src/etl/changes.py). É a formulação que melhor casa com o
dado disponível, por três razões:

1. **Usa o sinal que existe.** `rlEstabEquipamento` cresce 67% entre 2017 e
   2025 (747.500 para 1.247.979 linhas). Aquisição é o fenômeno mais frequente
   e mais bem registrado da tabela.
2. **É uma tarefa nativa de grafo.** Predição de aresta futura num grafo
   bipartido é exatamente onde uma GNN tem vantagem estrutural sobre um modelo
   tabular, o que torna a comparação entre trilhas informativa em vez de
   arbitrária.
3. **Produz o sinal de escassez como subproduto.** Um par `(u, k)` ao qual o
   modelo atribui alta probabilidade e que **não** se concretiza é um candidato
   a necessidade latente não suprida: a rede se comporta como se aquele
   equipamento devesse estar ali, e ele não está.

O ponto 3 é a ponte entre a tarefa mensurável e a pergunta de pesquisa, e é
uma **inferência, não uma medição**. O modelo aprende a regularidade da rede,
não a necessidade clínica. Um falso positivo pode ser escassez real, ou pode ser
uma peculiaridade legítima daquele estabelecimento. A leitura de escassez é uma
hipótese a ser discutida, nunca um resultado a ser reportado como fato.

### 2.2 Alvo secundário: regressão de quantidade

Prever `qt_existente` por par `(estabelecimento, tipo de equipamento)` em
`t+1`. Serve para duas coisas: comparabilidade com a literatura, que costuma
tratar capacidade como regressão, e para verificar se o ganho estrutural
observado na tarefa primária sobrevive a uma mudança de formulação.

### 2.3 O que foi descartado

**Taxa de utilização** `qt_uso / qt_existente` — descartada por degeneração
empírica. As duas colunas têm moda 1 em cerca de 69% das linhas, logo a razão é
1,0 na maioria dos casos e a variável quase não tem variância. Medido em
`docs/relatorio_analise_dados.md`, competência 202501.

**Predição de leitos** (`rlEstabComplementar.qt_exist`) — era o alvo do código
anterior, rebaixado a alvo de controle opcional. Leitos existem em cerca de 11
mil dos 560 mil estabelecimentos e a tabela cresce 12% em oito anos, contra 67%
de equipamentos. Rótulo esparso e quase estático: a baseline de persistência
ingênua é quase imbatível por construção, o que torna o resultado
não-informativo sobre a qualidade do modelo. Registro completo em
[`03-decisoes.md`](03-decisoes.md).

**Escassez per capita** — exigiria dado populacional externo (IBGE) por área de
abrangência. Fora do escopo desta iteração; anotado como extensão possível.

## 3. Amostra

- **Recorte espacial:** estabelecimentos do **estado de São Paulo**, prefixo
  `35` de `co_municipio_gestor`, 645 municípios e cerca de 146 mil
  estabelecimentos. O projeto original recortava só a capital; a expansão está
  em D-21 e foi feita porque quase triplica os eventos de aquisição (12.081 para
  40.880 nas nove transições) e porque um único município deixa a população do
  IBGE com variância
  zero, inutilizável como atributo. O recorte é um **prefixo de código IBGE**,
  então `'355030'` recupera a capital e `None` dá o país. O filtro é empurrado
  para dentro da leitura Parquet, não aplicado depois.
- **Recorte temporal:** snapshots anuais de janeiro, 01/2017 a 01/2026, dez
  pontos — eram nove até 202601 entrar (D-29), e a série cresce um janeiro por
  ano. Nada no código conta snapshots à mão: quem precisa da lista usa
  `changes.periodos_disponiveis()`, e a amostra canônica é
  `src.etl.extract.PERIODOS_ANUAIS`. O projeto original previa cinco snapshots bienais; a densidade foi
  dobrada porque cinco pontos com dois anos de intervalo não sustentam nenhuma
  afirmação sobre dinâmica temporal. A densidade final é confirmada
  empiricamente pelo `notebook/00_analise_alvo.ipynb`, que mede a taxa de
  mudança real por tabela.
- **Fonte:** banco de produção federal, via os ZIP de competência publicados em
  `cnes.datasus.gov.br`. Não se usa TABNET nem a API ElasticCNES: as duas
  entregam dados já agregados ou recortados, e a integridade relacional
  necessária para montar o grafo só existe nos microdados brutos.

## 4. Tempo: o que um snapshot é e o que ele não é

Esta seção existe porque a leitura ingênua da coluna de data produz um erro
silencioso, e o código anterior o cometia.

Cada ZIP de competência é uma **fotografia do estado atual** do banco de
produção, não um log de eventos. Para cada linha, ele traz apenas a **última**
`dt_atualizacao`. Consequências:

- A coluna `to_chardt_atualizacaoddmmyyyy` é um valor **censurado à direita**.
  Ela informa quando aquela linha mudou por último antes da extração, não a
  história da linha. Usá-la diretamente como `time_col` de um grafo temporal
  atribui a cada linha um instante que depende de quando o snapshot foi tirado.
- Toda alteração intermediária entre dois snapshots é **irrecuperável**. Se um
  equipamento foi adquirido em março de 2019 e removido em agosto de 2020,
  snapshots de 01/2019 e 01/2021 não registram nem a entrada nem a saída.
- A resolução temporal real do estudo é, portanto, o **espaçamento entre
  snapshots** — um ano — e não a granularidade diária da coluna de data.

Daí a unidade de análise ser a **transição** `t → t+1`, materializada por
[`src/etl/changes.py`](../src/etl/changes.py), e não a linha individual. Com dez
snapshots há nove transições, rotuladas pelo ano de destino: 2018 a 2026.

O filtro "somente linhas que sofreram alteração", previsto no projeto original,
é aplicado aqui como consequência dessa definição: uma linha inalterada entre
dois snapshots não constitui evento e não gera exemplo de treino.

### 4.1 Ressalva: o choque da pandemia

As transições 2020 e 2021 atravessam a pandemia de covid-19, que alterou de
forma abrupta e não estacionária a aquisição de equipamentos — respiradores e
leitos de UTI em particular. Isso viola a suposição de que as transições são
amostras de um mesmo processo. Duas obrigações decorrem disso:

1. Reportar métricas por transição, além do agregado, para que o efeito fique
   visível em vez de diluído.
2. Rodar uma variante do experimento excluindo as transições 2020 e 2021, e
   relatar se a conclusão muda.

## 5. As quatro trilhas

Cada trilha isola uma fonte distinta de poder preditivo. Elas não são
alternativas de implementação: são os termos de uma comparação, e o resultado do
trabalho é a diferença entre elas.

| Trilha | Entrada | O que isola |
|---|---|---|
| **1. Baselines tabulares** | features achatadas por estabelecimento, sem relações | quanto do fenômeno se explica sem estrutura nenhuma |
| **2. RDL relacional** | grafo do schema CNES inteiro (44 tabelas, pkey/fkey) | ganho de usar a estrutura relacional completa |
| **3. GNN geográfica** | somente estabelecimentos e proximidade espacial | ganho da vizinhança física, sem o schema |
| **4. Análise exploratória** | a série inteira de snapshots | não é modelo: fixa alvo e parâmetros por evidência |

### Trilha 1 — Baselines tabulares

Módulo [`src/ml/baselines.py`](../src/ml/baselines.py). Quatro modelos, na ordem em
que o projeto original os previa:

1. **Persistência ingênua.** O estado em `t+1` é igual ao de `t`. Nenhum
   parâmetro. É o piso: qualquer modelo que não o supere não aprendeu nada.
2. **Modelo geral tabular.** Gradient boosting sobre features agregadas por
   estabelecimento, usando todas as transições de treino. Implementado com
   `HistGradientBoosting` do scikit-learn, que já está no ambiente.
3. **Modelo com apenas o último snapshot.** Idêntico ao anterior, treinado só
   na transição mais recente do conjunto de treino. Mede se a série histórica
   acrescenta algo ou se o estado presente basta.
4. **Modelo por entidade.** Um modelo por estabelecimento. Mede quanta
   heterogeneidade existe entre estabelecimentos, ou seja, quanto se perde ao
   assumir um processo único para toda a rede.

### Trilha 2 — RDL relacional

Módulo [`src/ml/graph.py`](../src/ml/graph.py), sobre RelBench. O grafo vem do
`fkey_col_to_pkey_table` derivado de
[`01-selecao-tabelas.md`](01-selecao-tabelas.md), com `tbEstabelecimento` como
tabela raiz.

**Eixo temporal.** O `time_col` é a data do snapshot — 1º de janeiro do ano da
competência — e não `to_chardt_atualizacaoddmmyyyy`. A distinção importa: a data
do snapshot é conhecida exatamente e vale para toda linha daquele arquivo,
enquanto a coluna de atualização é censurada à direita (seção 4). Uma linha
presente no snapshot de 01/2021 significa "este fato valia em 01/2021", que é
exatamente a semântica que um grafo temporal precisa.

Cada tabela é portanto o empilhamento de todos os snapshots disponíveis, com o
período como eixo. O grafo carrega o **estado** da rede em cada instante; os eventos de
`changes.py` fornecem os **rótulos** e, como variante de ablação, o filtro que
mantém apenas linhas alteradas. Usar só os eventos para montar o grafo perderia
o estado, e sem o estado não há vizinhança para a GNN observar.

O filtro por município é empurrado para dentro da leitura: filtra-se a raiz por
`co_municipio_gestor`, e o conjunto de `co_unidade` resultante vira predicado
`isin` no scan de cada tabela filha. Sem esse empurrão, montar o grafo exige
carregar o país inteiro na memória para depois descartar 98% dele.

### Trilha 3 — GNN geográfica

Módulo [`src/ml/graph.py`](../src/ml/graph.py). Nós são estabelecimentos; arestas são
proximidade espacial derivada de `nu_latitude` e `nu_longitude`, por k-vizinhos
mais próximos ou por raio fixo. Ignora deliberadamente a estrutura de tabelas.

É a trilha conceitualmente mais próxima da pergunta de pesquisa — escassez como
fenômeno de vizinhança — e a mais frágil quanto a dados: depende do
preenchimento e da sanidade das coordenadas, que o notebook 00 verifica antes de
a trilha ser considerada viável.

### Trilha 4 — Análise exploratória

`notebook/00_analise_alvo.ipynb`. Não produz modelo. Produz as decisões que as
outras três consomem: qual alvo, qual densidade de snapshot, quais colunas
sobrevivem ao filtro empírico em toda a série, e se a trilha 3 é viável.
Roda antes das trilhas 1 a 3 e é ponto de decisão bloqueante.

## 6. Protocolo de avaliação

### 6.1 Partição temporal

Definida em [`src/ml/splits.py`](../src/ml/splits.py), módulo único consumido pelas
três trilhas de modelagem. Partição por **transição**, nunca por linha:

| Conjunto | Transições | Snapshots envolvidos |
|---|---|---|
| Treino | 2018, 2019, 2020, 2021, 2022, 2023 | 01/2017 a 01/2023 |
| Validação | 2024, 2025 | 01/2023 a 01/2025 |
| Teste | 2026 | 01/2025 a 01/2026 |

A tabela é consequência, não configuração: `particionar` toma a transição mais
recente para teste, as duas anteriores para validação, e o resto treina. Cada
competência nova **move a janela** um ano adiante. Os resultados de D-24 e D-26
foram medidos com teste em 2025 e validação em 2023–2024; comparar com número
novo exige reexecutar o experimento, não reler a tabela.

Regras que a implementação precisa garantir, e que os testes verificam:

- Nenhum par `(entidade, transição)` aparece em mais de uma partição.
- Nenhuma informação de snapshot posterior ao fim da janela de treino é visível
  durante o treino, incluindo features agregadas.
- Baselines e GNNs recebem exatamente a mesma partição. Sem isso os números não
  são comparáveis, e comparar é o objetivo.

### 6.2 Métricas

Tarefa primária, classificação binária com desbalanceamento severo. Medido no
gate: **prevalência de 0,065%**, ou um positivo a cada 1.530 candidatos — 18,5
milhões de exemplos para 12 mil eventos de aquisição. Duas restrições do espaço
de candidatos foram testadas e rejeitadas, então o desbalanceamento é tratado
como característica do problema, não como defeito a corrigir (D-19).

- **MAP@k por estabelecimento** é a métrica de destaque. Ela responde à pergunta
  que o trabalho de fato faz — quais equipamentos este estabelecimento
  provavelmente deveria ter — ranqueando os 99 tipos dentro de cada
  estabelecimento, onde o desbalanceamento global não distorce a escala.
- **Average precision (AP)** para comparar modelos entre si. Preferida à AUC-ROC,
  que é otimista sob desbalanceamento severo. Mas o seu valor absoluto não é
  interpretável aqui: com linha de base em 0,00065, um AP de 0,02 é trinta vezes
  a prevalência e ainda assim parece próximo de zero. Sempre reportado com a
  prevalência ao lado.
- **AUC-ROC** como terciária, por comparabilidade com a literatura.

Tarefa secundária, regressão: **RMSE** e **MAE**.

### 6.3 Regra de reporte

**Nenhum resultado de GNN é reportado sem a baseline de persistência na mesma
tabela.** Uma métrica de GNN isolada não é interpretável: não se sabe se ela
mede aprendizado ou a inércia do fenômeno. Esta regra existe porque o resultado
anterior do projeto violou-a de forma silenciosa — a função de teste em
`src/model.py` usava a máscara de treino, e portanto o número reportado como
desempenho de teste não era desempenho de teste.

Toda tabela de resultado deve trazer, no mínimo: persistência ingênua, modelo
geral tabular, RDL relacional e GNN geográfica, sobre a mesma partição, com a
métrica principal e o número de exemplos de cada conjunto.
