# Esboço do artigo

Documento de redação do trabalho. Registra a estrutura do texto a ser submetido, o
conteúdo já sustentado por medição e a marcação explícita do que permanece
pendente. O README descreve o repositório; este documento organiza o argumento
científico.

As fontes primárias são os demais documentos de `docs/`: a metodologia detalhada em
[`02-metodologia.md`](02-metodologia.md), o racional de cada escolha nas 44 entradas
de [`03-decisoes.md`](03-decisoes.md), a especificação do schema em
[`01-selecao-tabelas.md`](01-selecao-tabelas.md) e o critério de admissão de fontes
externas em [`04-dados-externos.md`](04-dados-externos.md). O segundo pipeline, que
levanta as limitações de hardware, está descrito em
[`06-pipeline-hpc.md`](06-pipeline-hpc.md).

**Estado da redação.** As seções 1, 3, 4, 5 e 7 dispõem de conteúdo medido e podem
ser redigidas na forma final. A seção 2 (trabalhos relacionados) constitui a principal
lacuna. Os valores da seção 5 provêm da primeira execução posterior à correção de
reprodutibilidade (D-44) e são reprodutíveis, o que é distinto de serem estáveis entre
sementes: a bateria com repetição está pendente e, até lá, o trabalho reporta ponto sem
intervalo.

O trabalho reporta **um** resultado, não a trajetória que levou até ele. Execuções
anteriores à série de dez competências correspondem a configurações defeituosas —
grafo com chaves estrangeiras sem correspondência, série interrompida antes da
competência final — e não constituem condições experimentais alternativas (D-39).
Não são citadas.

---

## Sumário de figuras e tabelas

Todas as figuras residem em [`figuras/`](figuras/), nomeadas
`fig-NN-descricao.png`. A convenção de geração e as diretrizes de formato estão em
[`figuras/README.md`](figuras/README.md). Cada slot abaixo já tem legenda redigida e
a linha de inclusão pronta, comentada até que o arquivo exista.

| # | Figura | Seção | Origem | Situação |
|---|---|---|---|---|
| 1 | Arquitetura do pipeline, das três camadas de dados às três trilhas | 4.2 | diagrama a desenhar | pendente |
| 2 | As três trilhas diante do mesmo rótulo | 4.2 | diagrama a desenhar | pendente |
| 3 | Série de eventos de aquisição por transição | 3.4 | `notebook/00_analise_alvo` | pendente |
| 4 | Cobertura de coordenada por competência | 3.4 | `notebook/00_analise_alvo` | pendente |
| 5 | Curvas de precisão–revocação das cinco previsões | 5.2 | `models/*/previsoes/` | desbloqueada por D-35 |
| 6 | MAP@10 por previsão | 5.2 | `models/*/previsoes/` | pendente |
| 7 | Recorte do grafo relacional em torno de um estabelecimento | 4.2 | `notebook/02_relacoes` | pendente |
| 8 | Distribuição espacial dos estabelecimentos posicionáveis | 5.4 | `notebook/04_recorte_e_dados_externos` | pendente |

| # | Tabela | Seção | Situação |
|---|---|---|---|
| 1 | Composição da amostra | 3.1 | escrita |
| 2 | As três trilhas e o que cada uma isola | 4.2 | escrita |
| 3 | Partição temporal | 4.3 | escrita |
| 4 | Desempenho comparado das cinco previsões | 5.1 | escrita |
| 5 | Matriz técnica × escopo | 5.3 | pendente de execução (D-36) |
| 6 | Hiperparâmetros e semente | 4.6 | pendente |
| 7 | Modos de falha identificados e corrigidos | 4.7 | escrita |

---

## Título

**Escassez de recursos em redes de saúde: a estrutura da rede acrescenta poder
preditivo?**

Título alternativo, mais aderente ao resultado obtido: *A estrutura da rede informa
onde, e não o quê: um resultado divergente entre métricas na predição de aquisição de
equipamento médico no CNES*.

**Autoria.** Pedro H. S. Prestes. Orientação: Alexandre C. B. Delbem e
Eric K. Tokuda.

## Resumo

O Cadastro Nacional de Estabelecimentos de Saúde (CNES) registra os recursos que
cada estabelecimento possui, e não os que necessitaria possuir. Este trabalho
investiga se a estrutura da rede assistencial — as relações de proximidade física e
de compartilhamento de recursos entre estabelecimentos — carrega informação
preditiva sobre onde recursos serão adquiridos, além daquela contida nos atributos
isolados de cada unidade. A tarefa operacional consiste em predizer a aquisição de
equipamento médico entre dois instantes anuais consecutivos, sobre dez competências
do CNES (janeiro de 2017 a janeiro de 2026) no estado de São Paulo, totalizando
146.679 estabelecimentos, 99 tipos de equipamento e 40.880 eventos de aquisição em
nove transições, com prevalência de 0,047%. Três abordagens observam o mesmo rótulo
sob informação estrutural distinta — ausente, relacional e geográfica —, submetidas à
mesma partição temporal e avaliadas sobre o mesmo subconjunto de nós. **O resultado é
duplo e divergente.** Na ordenação global, a informação estrutural acrescenta poder
preditivo: a rede neural de grafos relacional alcança precisão média (AP) de 0,0065 e
AUC-ROC de 0,841, contra 0,0029 e 0,751 do modelo de gradient boosting sem informação
estrutural. Na ordenação interna a cada estabelecimento, medida por MAP@10, a relação
se inverte: uma previsão baseada exclusivamente na frequência histórica de aquisição de
cada tipo de equipamento alcança 0,2725, contra 0,2533 da abordagem relacional. A
estrutura da rede informa **onde** uma aquisição ocorrerá, e não **qual** equipamento
será adquirido. A contribuição metodológica reside no desenho que torna a comparação
interpretável: piso de desempenho verificável, viés de seleção quantificado e corte
temporal que impede a presença do rótulo na estrutura observada pelo modelo.

**Palavras-chave:** CNES; redes de saúde; aprendizado profundo relacional; redes
neurais de grafos; predição de aquisição de recursos.

---

## 1. Introdução

### 1.1 Formulação do problema

> Dado o estado observável da rede de saúde, é possível identificar onde faltam
> recursos assistenciais e antecipar onde essa falta será suprida no período
> subsequente?

A hipótese central é que a resposta depende da **estrutura da rede**, e não apenas
dos atributos isolados de cada estabelecimento. Um hospital desprovido de tomógrafo
situado entre hospitais equipados constitui caso qualitativamente distinto de um
hospital igualmente desprovido, porém isolado a algumas dezenas de quilômetros do
serviço mais próximo. Modelos que tratam estabelecimentos como observações
independentes de uma tabela não distinguem as duas situações.

Verificar se essa distinção tem efeito mensurável constitui o objeto deste trabalho.

### 1.2 Natureza da contribuição

A contribuição não é a rede neural de grafos, mas a **diferença mensurada entre três
abordagens** que observam o mesmo rótulo sob informação estrutural distinta: ausente,
relacional e geográfica. A rede neural atua como instrumento de medição.

Essa definição orienta o desenho experimental em um aspecto decisivo: **o resultado
negativo é igualmente publicável**. Caso as redes de grafos apresentassem desempenho
equivalente ao do modelo tabular, a conclusão pertinente seria que a estrutura
registrada no CNES não acrescenta poder preditivo para esta tarefa. O experimento foi
construído para que tal afirmação pudesse ser sustentada com segurança, em vez de
confundida com deficiência de implementação.

### 1.3 Limitação central, declarada de saída

**A escassez não é diretamente observável no CNES.** O registro informa o que
existe; não informa o que seria necessário. Não há campo de demanda, fila de espera
ou população efetivamente atendida.

A definição operacional adotada — predizer a aquisição de equipamento — constitui
inferência sobre a regularidade da rede, e não medição de necessidade clínica. Um par
(estabelecimento, equipamento) ao qual o modelo atribui alta probabilidade e que não
se concretiza é **candidato** a necessidade latente: hipótese a discutir, e não
resultado a reportar como fato estabelecido. A decisão está registrada em D-02.

### 1.4 Contribuições

1. Desenho experimental que isola o efeito da informação estrutural em uma tarefa de
   predição sobre rede de saúde, com piso de desempenho verificável e viés de seleção
   quantificado.
2. Medição, sobre dez anos de registro no estado de São Paulo, de que a estrutura
   relacional supera tanto o modelo tabular quanto a vizinhança geográfica.
3. Catálogo de modos de falha metodológica identificados no percurso, com o efeito de
   cada um sobre o número reportado (seção 4.7 e as 44 entradas de
   [`03-decisoes.md`](03-decisoes.md)).

---

## 2. Trabalhos relacionados

**Seção não redigida.** Constitui a principal lacuna do texto. Os blocos previstos e
a função de cada um na argumentação:

| Bloco | Função no texto |
|---|---|
| Aprendizado profundo relacional | Fundamenta a formulação de tarefas preditivas diretamente sobre schema relacional (base da trilha 2) e justifica não achatar as 44 tabelas em matriz única |
| Redes neurais de grafos em dados de saúde | Situa a originalidade: o grafo aqui é de **recurso instalado**, e não de paciente, referência clínica ou coautoria |
| Predição de demanda e alocação no SUS | Demonstra que a literatura nacional trata predominantemente produção e faturamento, raramente a estrutura da rede como objeto |
| Aprendizado sobre grafos geográficos | Fundamenta a trilha 3, que é o controle mais informativo do desenho |
| Métricas sob desbalanceamento extremo | Sustenta a escolha de métrica de destaque quando a prevalência é da ordem de 10⁻⁴ (seção 4.5) |

---

## 3. Dados

### 3.1 Fonte e recorte

Utilizam-se os microdados do CNES, distribuídos pelo DATASUS como arquivos
compactados por competência, extraídos do banco de produção federal. Descartaram-se
o TABNET e a API ElasticCNES: ambos entregam dados agregados ou previamente
recortados, e a integridade relacional necessária à construção do grafo existe apenas
nos microdados brutos.

**Tabela 1 — Composição da amostra.**

| Dimensão | Valor |
|---|---|
| Recorte espacial | Estado de São Paulo (prefixo IBGE `35`), 645 municípios, 146.679 estabelecimentos |
| Recorte temporal | Dez competências anuais de janeiro, de 01/2017 a 01/2026 |
| Escopo do schema | 44 tabelas, 393 colunas aprovadas em dois filtros independentes |
| Alvo | `rlEstabEquipamento`, 99 tipos de equipamento |
| Eventos de aquisição | 40.880 em nove transições |

O recorte espacial é um prefixo hierárquico de código IBGE: `355030` restringe o
estudo à capital, e a ausência de prefixo abrange o país. O trabalho iniciou-se
restrito à capital e foi ampliado ao estado, decisão registrada em D-21, por
aproximadamente triplicar o número de eventos de aquisição e conferir variância a
atributos de nível municipal.

### 3.2 Semântica temporal

Cada arquivo de competência é uma **fotografia do estado corrente** do cadastro, e
não um registro de eventos, preservando apenas a última data de atualização de cada
linha. Decorrem três consequências metodológicas:

1. A coluna de atualização é **censurada à direita**. Empregá-la como eixo temporal
   atribuiria a cada linha um instante dependente da data de extração do arquivo.
2. Alterações ocorridas entre duas competências são **irrecuperáveis**.
3. A resolução temporal efetiva do estudo é o **espaçamento entre competências**, e
   não a granularidade diária da coluna de data.

Adota-se, por conseguinte, a **transição** `t → t+1` como unidade de análise, e a
data da competência — exata e uniforme para todas as linhas do arquivo — como eixo
temporal do grafo. A decisão está registrada em D-08.

### 3.3 Seleção de tabelas e colunas

A especificação do schema reside em documento Markdown versionado, lido pelo código
em tempo de importação, de modo que não existe segunda lista a manter em sincronia
(D-05). Uma coluna é admitida somente se aprovada em dois filtros independentes: o
**semântico**, que exige pertinência à pergunta de pesquisa, e o **empírico**, que
exige não degeneração nos dados observados (D-06).

Duas propriedades do dado, identificadas por medição, merecem registro no artigo por
serem generalizáveis a qualquer trabalho sobre o CNES:

- **Instabilidade do schema.** Quatro tabelas apresentam colunas que desaparecem e
  retornam entre competências, com 201901 como competência anômala (D-20).
- **Preenchimento variável de colunas `CHAR(n)`.** Colunas de largura fixa chegam
  preenchidas com espaços, e o preenchimento se altera quando o CNES amplia a
  largura da coluna. Em 202601 o código de tipo de equipamento passou de um para dois
  caracteres, e o valor `'1'` tornou-se `'1 '`, o que fez a totalidade da tabela do
  alvo ser contabilizada como substituída antes da correção (D-30).

### 3.4 Caracterização da amostra

<!-- ![Eventos de aquisição por transição](figuras/fig-03-eventos-por-transicao.png) -->

**Figura 3 — Eventos de aquisição por transição.** Contagem de aquisições de
equipamento em cada uma das nove transições, no recorte estadual. A série é
estável, entre 3,4 e 6,3 mil eventos por transição, sem concentração associada ao
período pandêmico. Sustenta a densidade anual de amostragem discutida em D-10.

<!-- ![Cobertura de coordenada por competência](figuras/fig-04-cobertura-coordenada.png) -->

**Figura 4 — Cobertura de coordenada geográfica por competência.** Proporção de
estabelecimentos com latitude e longitude plausíveis, de 1,1% em 201701 a 87,3% em
202601, com degrau acentuado em 2020. Motiva a restrição da trilha 3 ao subconjunto
posicionável e, por consequência, a obrigatoriedade da comparação pareada
(seção 5.4).

---

## 4. Metodologia

O detalhamento completo consta de [`02-metodologia.md`](02-metodologia.md). Esta
seção reúne o que o artigo precisa afirmar.

### 4.1 Definição da tarefa

Adota-se classificação binária de **aquisição** sobre o grafo bipartido
estabelecimento × tipo de equipamento: dado que a unidade `u` não possui equipamento
do tipo `k` no instante `t`, ela passa a possuí-lo em `t+1`?

A formulação como predição de aresta futura é deliberada: é o regime em que uma rede
neural de grafos apresenta vantagem estrutural sobre um modelo tabular, o que confere
significado à comparação entre abordagens. A regressão da quantidade existente foi
medida e **rejeitada** como tarefa secundária: 1,119% dos pares persistentes mudam de
quantidade entre competências, e prever zero tem RMSE igual ao desvio padrão do alvo
(D-37). O evento raro tem formulação binária, que é a adotada.

O regime é de desbalanceamento extremo: 86,7 milhões de pares candidatos para 40.880
eventos, prevalência de 0,047%. Duas restrições do espaço de candidatos foram
avaliadas e rejeitadas, por descartarem positivos relevantes ou por efeito
desprezível (D-19).

### 4.2 As três abordagens

<!-- ![Arquitetura do pipeline](figuras/fig-01-arquitetura-pipeline.png) -->

**Figura 1 — Arquitetura do pipeline.** Fluxo desde os arquivos de competência até as
três abordagens de modelagem, passando pelas quatro camadas de dados (bruta,
intermediária, primária e de atributos derivados) e pelos módulos de construção de
rótulo, partição temporal e montagem de grafo. Evidencia que as três abordagens
compartilham a tabela de rótulos e a partição, divergindo apenas no codificador.

<!-- ![As três trilhas diante do mesmo rótulo](figuras/fig-02-tres-trilhas.png) -->

**Figura 2 — As três abordagens diante do mesmo rótulo.** Representação esquemática
da informação disponível a cada abordagem: atributos achatados por estabelecimento
na primeira; grafo heterogêneo do schema, com nós de categoria compartilhados, na
segunda; grafo de proximidade física entre estabelecimentos na terceira. O
decodificador é idêntico nas duas últimas.

**Tabela 2 — As três abordagens e o que cada uma isola.**

| Abordagem | Informação de entrada | O que isola |
|---|---|---|
| 1 — modelos tabulares | atributos achatados por estabelecimento, sem relações | parcela do fenômeno explicável sem informação estrutural |
| 2 — relacional | grafo do schema CNES, 25 tipos de nó e 48 relações | ganho atribuível à estrutura relacional |
| 3 — geográfica | estabelecimentos e proximidade física (kNN, k = 10) | ganho atribuível à vizinhança física, sem o schema |

O **decodificador é idêntico** nas abordagens 2 e 3: ambas produzem uma
representação vetorial por estabelecimento e a combinam com uma representação
aprendida do tipo de equipamento. Apenas o codificador difere. Sem essa restrição,
uma diferença de desempenho entre as duas poderia originar-se do decodificador, e não
da estrutura.

A abordagem 1 mantém-se deliberadamente livre de agregados de vizinhança. Sua
inclusão a converteria em versão empobrecida da abordagem 2 e suprimiria a diferença
que o experimento se propõe a medir.

<!-- ![Recorte do grafo relacional](figuras/fig-07-recorte-grafo-relacional.png) -->

**Figura 7 — Recorte do grafo relacional em torno de um estabelecimento.**
Vizinhança de raio dois de uma unidade, com os nós de categoria que a conectam a
outras unidades. Ilustra o mecanismo pelo qual duas unidades geograficamente
distantes, porém dotadas do mesmo equipamento, tornam-se vizinhas de segunda ordem —
propriedade ausente do grafo geográfico.

### 4.3 Partição temporal

A partição opera por **transição**, nunca por linha, e nunca por sorteio.

**Tabela 3 — Partição temporal.**

| Conjunto | Transições | Instantes envolvidos |
|---|---|---|
| Treino | 2018, 2019, 2020, 2021, 2022, 2023 | 01/2017 a 01/2023 |
| Validação | 2024, 2025 | 01/2023 a 01/2025 |
| Teste | 2026 | 01/2025 a 01/2026 |

A divisão é derivada da série, e não configurada: a transição mais recente compõe o
teste, as duas anteriores a validação, e as remanescentes o treino. Cada competência
acrescentada desloca a janela em um ano, do que decorre que a série de dez
competências é parte da especificação do resultado, e não um parâmetro de execução.

### 4.4 Prevenção de vazamento

Três precauções, todas motivadas por falhas efetivamente observadas:

1. **Corte do grafo anterior a todos os rótulos.** A estrutura relacional é estática:
   uma única realização serve treino, validação e teste. Cortá-la ao fim da janela de
   treino inscreveria o rótulo na própria estrutura, pois a aresta entre
   estabelecimento e equipamento em `t+1` é o alvo (D-25).
2. **Atributos calculados até o fim da janela de treino.** Agregados sobre a série
   completa contaminam o treino mesmo quando os rótulos estão corretamente divididos.
3. **Amostragem de negativos restrita ao treino** (razão 200:1). Validação e teste
   permanecem completos; subamostrá-los tornaria artificial a prevalência medida.

### 4.5 Métricas

- **MAP@10 por estabelecimento** é a métrica de destaque. Responde à pergunta que o
  trabalho formula — quais equipamentos determinada unidade provavelmente deveria
  possuir — ordenando os 99 tipos no interior de cada unidade.
- **Precisão média (AP)** é a métrica global, interpretável em relação à prevalência:
  com linha de base em 0,00055, o valor de 0,0106 corresponde a dezenove vezes o
  desempenho aleatório.
- **AUC-ROC** é reportada por comparabilidade com a literatura, com a ressalva de ser
  otimista sob desbalanceamento extremo.
- **Piso verificável.** A previsão por persistência retorna AP exatamente igual à
  prevalência e AUC exatamente 0,500. Qualquer desvio indica erro no arcabouço de
  avaliação, e não no modelo. A propriedade confirmou-se em três execuções sucessivas
  (D-24, D-26, D-32).

### 4.6 Configuração experimental

**Tabela 6 — Hiperparâmetros e semente.** Pendente. Deve reunir: dimensão das
representações, número de camadas, taxa de aprendizado, tamanho de minilote, critério
de parada antecipada, semente aleatória, versões de biblioteca e especificação da
máquina.

### 4.7 Modos de falha identificados

Cada item a seguir produziria resultado plausível e incorreto. O catálogo integra a
contribuição do trabalho, e não apenas a documentação do repositório.

**Tabela 7 — Modos de falha identificados e corrigidos.**

| Modo de falha | Efeito, se não corrigido |
|---|---|
| Avaliação sobre a máscara de treino | desempenho de treino reportado como desempenho de teste (D-11) |
| Grafo estático cortado ao fim do treino | rótulo inscrito na estrutura na última transição de treino (D-25) |
| Um nó por linha de tabela de fato | 76 milhões de nós e ausência de vizinho compartilhado entre unidades com o mesmo equipamento (D-25) |
| Chave estrangeira composta transcrita coluna a coluna | 33 declarações sem qualquer valor correspondente no destino (D-28) |
| Comparação de colunas `CHAR(n)` sem normalizar preenchimento | tabela do alvo integralmente contabilizada como substituída (D-30) |
| Diferenciação entre competências pela lista de colunas de um único lado | três transições ausentes do resumo, sem erro visível (D-31) |
| Empates de MAP@k desfeitos pela ordem das linhas | previsão de escore constante aparentando capacidade de ordenação |

---

## 5. Resultados

### 5.1 Desempenho comparado

Recorte estadual, transição de teste 2026. A tabela pertinente é a **pareada**,
restrita aos 127.868 estabelecimentos posicionáveis: 11.411.933 exemplos, 6.309
positivos, prevalência de 0,0553%. Somente a comparação pareada é legítima, pois a
abordagem 3 alcança apenas as unidades dotadas de coordenada, e a avaliação sobre
populações distintas mediria diferença de amostra em lugar de diferença de estrutura.

**Tabela 4 — Desempenho comparado das sete previsões.** Ver D-44.

| Previsão | Abordagem | AP | AUC-ROC | MAP@10 |
|---|---|---|---|---|
| `gnn_relacional` | 2 | **0,00650** | **0,841** | 0,2533 |
| `gnn_geografica` | 3 | 0,00493 | 0,800 | 0,2665 |
| `por_entidade` | 1 | 0,00335 | 0,737 | 0,1580 |
| `gbdt_geral` | 1 | 0,00289 | 0,751 | 0,1910 |
| `gbdt_ultimo_snapshot` | 1 | 0,00230 | 0,744 | 0,1859 |
| `popularidade_item` | 1 | 0,00220 | 0,699 | **0,2725** |
| `persistencia` | 1 | 0,00055 | 0,500 | 0,0333 |

Custo computacional: 12 min de treino na abordagem 2, com melhor época em 28 de 49;
12 min na abordagem 3, com melhor época em 46. Execução completa em 1 h 12, com
consumo máximo de 6,95 GB.

Estes valores são os da primeira execução posterior à correção de reprodutibilidade
descrita em 4.7. Execuções anteriores construíam a tabela de rótulos em ordem não
determinística e produziram, para a mesma configuração, MAP@10 entre 0,189 e 0,300;
nenhuma delas é citável.

### 5.2 Leitura das métricas

<!-- ![Curvas de precisão–revocação](figuras/fig-05-precisao-revocacao.png) -->

**Figura 5 — Curvas de precisão–revocação das cinco previsões.** Escala logarítmica
no eixo de precisão, com a prevalência marcada como linha de base. Torna visível que
a vantagem das abordagens estruturais se concentra na região de alta precisão e baixa
revocação, que é a faixa de interesse para uso operacional.

<!-- ![MAP@10 por modelo](figuras/fig-06-map10-por-modelo.png) -->

**Figura 6 — AP e MAP@10 por previsão, em painéis lado a lado.** Torna visível a
inversão de ordenação entre as duas métricas: a abordagem relacional lidera o painel
de AP e ocupa a terceira posição no de MAP@10. É a figura que sustenta a leitura 3.

Três leituras decorrem da Tabela 4, e a terceira é a mais importante do trabalho.

1. **A estrutura acrescenta poder preditivo de ordenação global.** A abordagem
   relacional atinge 11,7 vezes a prevalência em AP, contra 5,2 vezes do gradient
   boosting tabular — uma razão de 2,3 entre as duas. Em AUC-ROC, 0,841 contra 0,751.
2. **A estrutura relacional supera a geográfica.** AP de 0,00650 contra 0,00493, AUC
   de 0,841 contra 0,800. A hipótese de que a proximidade física capturaria quase todo
   o sinal estrutural não se sustenta: o esquema relacional rende mais, ainda que ao
   custo de igual tempo de treino.
3. **As duas métricas discordam, e a discordância é o resultado.** Em MAP@10 a
   ordenação se inverte: `popularidade_item` alcança 0,2725, a abordagem geográfica
   0,2665 e a relacional 0,2533. Uma previsão que ignora inteiramente o
   estabelecimento — baseada exclusivamente na frequência histórica de aquisição de
   cada tipo de equipamento — ordena melhor **no interior** de cada unidade que ambas
   as redes de grafos.

As duas afirmações são compatíveis, pois as métricas medem dimensões distintas do
mesmo escore: AP avalia a ordenação global e MAP@k a ordenação interna à entidade. A
informação estrutural mostra-se útil para determinar **onde**, na rede, uma aquisição
ocorrerá, e não para determinar **qual** equipamento uma unidade específica adquirirá.

Este é o resultado que o trabalho reporta, e ele não é o esperado. A hipótese candidata
para a discordância é que o componente de item do decodificador convirja mais
lentamente que o componente de nó, sendo `popularidade_item` precisamente um modelo
composto apenas do primeiro. A verificação é direta e está registrada em 6.1.

### 5.3 Matriz técnica × escopo

As limitações de hardware descritas na seção 7 foram levantadas em um segundo pipeline,
executado em servidor de 440 GB com GPU (D-34). Como técnica e escopo deixam de estar
amarrados, o trabalho passa a reportar quatro células em vez de um número:

**Tabela 5 — Matriz técnica × escopo.** Pendente de execução; ver D-36.

| | Escopo São Paulo | Escopo nacional |
|---|---|---|
| **Técnica limitada** — grafo estático em 201701, projeção mínima, negativos 200:1, um passo por época | célula A, reproduz a Tabela 4 | célula B |
| **Técnica completa** — grafo por transição, atributo e peso na aresta, negativos completos | célula C | célula D |

A decomposição é o objetivo: **B menos A** isola o efeito do escopo com a técnica
constante, **C menos A** isola o efeito da técnica com o escopo constante, e a célula A
serve de controle — rodada no servidor, deve reproduzir a Tabela 4 dentro do ruído de
semente, e qualquer divergência aponta para o código novo em lugar do hardware.

A célula C responde diretamente à questão levantada em 7: quanto das limitações de
memória custou em desempenho, medido sem trocar de amostra.

### 5.4 Viés do subconjunto de avaliação

<!-- ![Distribuição espacial dos posicionáveis](figuras/fig-08-distribuicao-espacial.png) -->

**Figura 8 — Distribuição espacial dos estabelecimentos posicionáveis.** Densidade de
unidades com coordenada plausível no estado, com destaque para a região
metropolitana. Auxilia a caracterizar a natureza não aleatória do subconjunto sobre o
qual a comparação pareada é conduzida.

A prevalência eleva-se de 0,0478% no conjunto completo para 0,0553% no subconjunto
pareado, e os 6.309 positivos da transição de teste situam-se **integralmente** em
estabelecimentos com coordenada plausível. Unidades que adquiriram equipamento na
transição de teste estão, sem exceção, georreferenciadas, o que torna a comparação
não pareada enganosa por construção.

---

## 6. Discussão

### 6.1 Questões a desenvolver

- **Divergência entre AP e MAP@10, que é o resultado principal.** As duas métricas
  medem dimensões distintas do mesmo escore — ordenação global contra ordenação no
  interior do estabelecimento — e a abordagem relacional lidera a primeira e perde a
  segunda. A explicação candidata é a convergência mais lenta do componente de item do
  decodificador, sendo `popularidade_item` um modelo composto apenas desse componente.
  **Verificação direta:** um escore que combine a saída relacional com a frequência de
  item; se superar 0,2725 em MAP@10, a hipótese se sustenta e o componente de item está
  subaproveitado. Se não superar, a explicação é outra.
- **Superioridade do schema sobre a geografia.** Hipótese: o nó de categoria
  compartilhado conecta unidades distantes com perfil semelhante, o que a proximidade
  física não realiza por construção.
- **Interpretação da predição não realizada.** É o ponto em que a ponte com a
  escassez latente teria de ser argumentada, sob a cautela estabelecida em D-02.

---

## 7. Limitações

- **A escassez permanece inferida.** O resultado refere-se a aquisição, e não a
  necessidade. Apenas dados de demanda — a produção ambulatorial do SIA/SUS é a fonte
  candidata — permitiriam fechar essa lacuna.
- **A estrutura e os atributos são estáticos.** O grafo é cortado em 2017 para evitar
  vazamento, descrevendo uma rede nove anos anterior ao conjunto de teste. Os
  atributos de nó derivam do mesmo corte, e o recorte contava 80.073 estabelecimentos
  em 2017 contra 146.679 na série completa, de modo que **45% dos nós ingressam com
  vetor de atributos vazio**. *Levantada no pipeline do servidor por um grafo por
  transição; efeito a medir na célula C da Tabela 5.*
- **O grafo relacional é topologia sem atributo.** A projeção que viabiliza a
  montagem em 9 GB de memória retém duas colunas por tabela filha, de forma que 273
  das 343 colunas aprovadas nas tabelas filhas permanecem fora do grafo: as arestas
  não carregam peso nem atributo. *Levantada no modo completo, com vocabulário por
  coluna e peso agregado por par.*
- **Um estado e uma transição de avaliação.** A generalização para outras unidades
  federativas não foi verificada, e o resultado repousa sobre uma única transição de
  teste. *O recorte nacional entra nas células B e D.*
- **As limitações acima são de hardware, não de método.** O trabalho as reporta como
  tal, e a Tabela 5 existe para quantificar o que cada uma custou — em lugar de
  deixá-las como ressalva qualitativa.
- **A variância entre execuções ainda não está caracterizada.** A fonte dominante de
  irreprodutibilidade foi identificada e corrigida (D-43), mas resta variação de
  inicialização, que só a repetição por semente quantifica. Enquanto a bateria com
  `SEMENTES=3` não for executada, o trabalho reporta ponto sem intervalo, e isso é
  declarado.

---

## 8. Conclusão e trabalhos futuros

A estrutura da rede carrega informação sobre onde recursos serão adquiridos, e a
estrutura relacional carrega mais informação do que a proximidade física. O
resultado, contudo, é menos firme do que o **desenho** que o produziu: comparação
efetivamente pareada, piso de desempenho verificável, viés de seleção quantificado e
decisões auditáveis.

Trabalhos futuros, ordenados por razão entre valor esperado e custo:

1. **Peso e atributo nas arestas, e atributos calculados até o fim da janela de
   treino**, que restituem informação hoje descartada pela projeção mínima e pelo
   corte de vazamento, sem alteração de arquitetura.
2. **Escore combinado entre a rede relacional e a popularidade do item**: é a
   verificação direta da leitura 3 da seção 5.2. Superar 0,2725 em MAP@10 indicaria que
   o componente de item permanece subaproveitado no decodificador; não superar indicaria
   que a explicação da divergência entre métricas é outra.
3. **Grafo temporal com visibilidade por exemplo**, que elimina a defasagem de nove
   anos imposta às abordagens estruturais.
4. **Produção ambulatorial do SIA/SUS**, única fonte capaz de converter escassez
   inferida em escassez com demanda observada, e a de maior custo.

A integração de fontes externas ao CNES — da qual a população municipal do IBGE é o
caso mais barato — constitui linha de continuação própria, e não etapa deste
trabalho. O critério de admissão está escrito em
[`04-dados-externos.md`](04-dados-externos.md); a avaliação de que nenhum papel
previsto para a população municipal tem consumidor no desenho atual está em D-40.

---

## Referências

A redigir em conjunto com a seção 2, cobrindo os cinco blocos ali especificados.

## Pendências de redação

- [ ] Seção 2 integral, com as referências correspondentes.
- [ ] **Bateria com `SEMENTES=3` executada, e a Tabela 4 refeita com intervalo em vez
      de ponto.** Bloqueia a seção 5 (D-42).
- [ ] Figuras 1 a 8 geradas e inseridas (remover o comentário da linha de inclusão).
- [ ] Tabela 6, de hiperparâmetros e semente.
- [ ] Execução das quatro células da Tabela 5 no servidor, e a leitura da decomposição.
- [ ] Definição do veículo de submissão e adequação ao formato exigido.
