# Esboço do artigo

Documento de redação do trabalho. Registra a estrutura do texto a ser submetido, o
conteúdo já sustentado por medição e a marcação explícita do que permanece
pendente. O README descreve o repositório; este documento organiza o argumento
científico.

As fontes primárias são os demais documentos de `docs/`: a metodologia detalhada em
[`02-metodologia.md`](02-metodologia.md), o racional de cada escolha nas 32 entradas
de [`03-decisoes.md`](03-decisoes.md), a especificação do schema em
[`01-selecao-tabelas.md`](01-selecao-tabelas.md) e o critério de admissão de fontes
externas em [`04-dados-externos.md`](04-dados-externos.md).

**Estado da redação.** As seções 1, 3, 4, 5 e 7 dispõem de conteúdo medido e podem
ser redigidas na forma final. A seção 2 (trabalhos relacionados) constitui a
principal lacuna. A seção 6 depende do experimento de ablação descrito em 6.1.

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
| 5 | Curvas de precisão–revocação das cinco previsões | 5.2 | `docs/resultados/*.json` | pendente |
| 6 | MAP@10 por modelo, com intervalo entre execuções | 5.2 | `docs/resultados/*.json` | pendente |
| 7 | Recorte do grafo relacional em torno de um estabelecimento | 4.2 | `notebook/02_relacoes` | pendente |
| 8 | Distribuição espacial dos estabelecimentos posicionáveis | 5.4 | `notebook/04_recorte_e_dados_externos` | pendente |

| # | Tabela | Seção | Situação |
|---|---|---|---|
| 1 | Composição da amostra | 3.1 | escrita |
| 2 | As três trilhas e o que cada uma isola | 4.2 | escrita |
| 3 | Partição temporal | 4.3 | escrita |
| 4 | Desempenho comparado das cinco previsões | 5.1 | escrita |
| 5 | Comparação entre execuções sucessivas | 5.3 | escrita |
| 6 | Hiperparâmetros e semente | 4.6 | pendente |
| 7 | Modos de falha identificados e corrigidos | 4.7 | escrita |

---

## Título

**Escassez de recursos em redes de saúde: a estrutura da rede acrescenta poder
preditivo?**

Título alternativo, mais aderente ao resultado obtido: *Estrutura relacional supera
proximidade geográfica na predição de aquisição de equipamento médico no CNES*.

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
sob informação estrutural distinta — ausente, relacional e geográfica —, submetidas
à mesma partição temporal e avaliadas sobre o mesmo subconjunto de nós. A rede
neural de grafos relacional alcança precisão média (AP) de 0,0106 e MAP@10 de 0,300,
contra 0,0036 e 0,257 do modelo de gradient boosting sem informação estrutural,
superando também a variante puramente geográfica (0,0049 e 0,274). A contribuição
metodológica reside no desenho que torna a comparação interpretável: piso de
desempenho verificável, viés de seleção quantificado e corte temporal que impede a
presença do rótulo na estrutura observada pelo modelo.

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
   cada um sobre o número reportado (seção 4.7 e as 32 entradas de
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
significado à comparação entre abordagens. A regressão da quantidade existente
permanece como tarefa secundária.

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
acrescentada desloca a janela em um ano, do que decorre que resultados de execuções
distintas só são comparáveis sob a mesma série (D-29).

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

**Tabela 4 — Desempenho comparado das cinco previsões.**

| Previsão | Abordagem | AP | AUC-ROC | MAP@10 |
|---|---|---|---|---|
| `gnn_relacional` | 2 | **0,01061** | **0,849** | **0,3000** |
| `gnn_geografica` | 3 | 0,00490 | 0,816 | 0,2745 |
| `gbdt_geral` | 1 | 0,00355 | 0,766 | 0,2567 |
| `popularidade_item` | 1 | 0,00220 | 0,700 | 0,2714 |
| `persistencia` | 1 | 0,00055 | 0,500 | 0,0324 |

Custo computacional: 1.668 s de treino na abordagem 2, com melhor época em 99; 160 s
na abordagem 3, com melhor época em 26. Consumo máximo de memória de 6,3 GB.

### 5.2 Leitura das métricas

<!-- ![Curvas de precisão–revocação](figuras/fig-05-precisao-revocacao.png) -->

**Figura 5 — Curvas de precisão–revocação das cinco previsões.** Escala logarítmica
no eixo de precisão, com a prevalência marcada como linha de base. Torna visível que
a vantagem das abordagens estruturais se concentra na região de alta precisão e baixa
revocação, que é a faixa de interesse para uso operacional.

<!-- ![MAP@10 por modelo](figuras/fig-06-map10-por-modelo.png) -->

**Figura 6 — MAP@10 por previsão, com a variação observada entre execuções.**
Contrapõe os valores da execução sob teste 2025 (D-26) e sob teste 2026 (D-32),
evidenciando que as previsões sem informação estrutural permaneceram estáveis
enquanto as duas abordagens estruturais se deslocaram.

Três leituras decorrem da Tabela 4:

1. **A estrutura acrescenta poder preditivo.** A abordagem relacional atinge 19,2
   vezes a prevalência em AP, contra 6,4 vezes do gradient boosting tabular.
2. **O ganho manifesta-se também na métrica de destaque.** MAP@10 de 0,300 contra
   0,271 da previsão que considera exclusivamente a frequência de aquisição de cada
   tipo de equipamento. Na execução anterior a relação era inversa.
3. **A estrutura relacional supera a geográfica.** AP de 0,0106 contra 0,0049. Na
   execução anterior as duas praticamente se igualavam em AUC, o que sustentava a
   interpretação de que a proximidade física capturaria quase todo o sinal
   estrutural; com o grafo relacional corrigido, essa interpretação não se sustenta.

### 5.3 Comparação entre execuções sucessivas

**Tabela 5 — Comparação entre execuções.** Coluna esquerda: teste 2025, série de nove
competências (D-26). Coluna direita: teste 2026, série de dez competências (D-32).

| Previsão | AP (2025) | AP (2026) | MAP@10 (2025) | MAP@10 (2026) |
|---|---|---|---|---|
| `gnn_relacional` | 0,00478 | 0,01061 | 0,2133 | 0,3000 |
| `gnn_geografica` | 0,00378 | 0,00490 | 0,2077 | 0,2745 |
| `gbdt_geral` | 0,00280 | 0,00355 | 0,2520 | 0,2567 |
| `popularidade_item` | 0,00215 | 0,00220 | 0,2957 | 0,2714 |
| `persistencia` | 0,00051 | 0,00055 | 0,0354 | 0,0324 |

As previsões sem informação estrutural apresentaram variação reduzida; as duas
abordagens estruturais apresentaram variação substancial, com a relacional mais que
dobrando em AP. A interpretação dessa diferença exige o experimento de ablação
descrito em 6.1.

### 5.4 Viés do subconjunto de avaliação

<!-- ![Distribuição espacial dos posicionáveis](figuras/fig-08-distribuicao-espacial.png) -->

**Figura 8 — Distribuição espacial dos estabelecimentos posicionáveis.** Densidade de
unidades com coordenada plausível no estado, com destaque para a região
metropolitana. Auxilia a caracterizar a natureza não aleatória do subconjunto sobre o
qual a comparação pareada é conduzida.

A prevalência eleva-se de 0,0478% no conjunto completo para 0,0553% no subconjunto
pareado. O efeito é mais acentuado do que na execução anterior: os 6.309 positivos da
transição de teste situam-se **integralmente** em estabelecimentos com coordenada
plausível. Unidades que adquiriram equipamento entre 2025 e 2026 estão, sem exceção,
georreferenciadas, o que torna a comparação não pareada enganosa por construção.

---

## 6. Discussão

### 6.1 Experimento de ablação, pendente

Três alterações foram introduzidas entre as duas execuções comparadas na Tabela 5: a
partição deslocou-se em um ano; o grafo relacional foi corrigido, com a remoção de 33
declarações de chave estrangeira sem correspondência e a reconexão de uma tabela de
815 mil linhas à raiz (D-28); e o treino avançou até a época 99, em lugar de
interromper-se na 47.

A estabilidade das previsões sem informação estrutural, contrastada com o
deslocamento das duas abordagens estruturais, sugere que o efeito predominante é o da
correção do grafo. A afirmação, entretanto, requer decomposição. O experimento é de
baixo custo: executar o teste 2026 com as declarações antigas de chave estrangeira e
o teste 2025 com o grafo corrigido.

### 6.2 Questões a desenvolver

- **Divergência e posterior convergência entre AP e MAP@10.** As duas métricas medem
  dimensões distintas do mesmo escore — ordenação global contra ordenação no interior
  do estabelecimento. A convergência tardia da componente de item é a explicação
  candidata.
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
  vetor de atributos vazio**.
- **O grafo relacional é topologia sem atributo.** A projeção que viabiliza a
  montagem em 9 GB de memória retém duas colunas por tabela filha, de forma que 298
  das 368 colunas aprovadas nas tabelas de fato permanecem fora do grafo: as arestas
  não carregam peso nem atributo.
- **Um estado e uma transição de avaliação.** A generalização para outras unidades
  federativas não foi verificada, e o resultado repousa sobre uma única transição de
  teste.
- **A inversão do resultado de MAP@10 não está decomposta.** Ver seção 6.1.

---

## 8. Conclusão e trabalhos futuros

A estrutura da rede carrega informação sobre onde recursos serão adquiridos, e a
estrutura relacional carrega mais informação do que a proximidade física. O
resultado, contudo, é menos firme do que o **desenho** que o produziu: comparação
efetivamente pareada, piso de desempenho verificável, viés de seleção quantificado e
decisões auditáveis.

Trabalhos futuros, ordenados por razão entre valor esperado e custo:

1. **Ablação da inversão observada**, que separa o efeito da partição do efeito da
   correção estrutural.
2. **Peso e atributo nas arestas, e atributos calculados até o fim da janela de
   treino**, que restituem informação hoje descartada pela projeção mínima e pelo
   corte de vazamento, sem alteração de arquitetura.
3. **Escore combinado entre a rede relacional e a popularidade do item**: superação
   de 0,300 em MAP@10 indicaria que a componente de item permanece subaproveitada.
4. **Grafo temporal com visibilidade por exemplo**, que elimina a defasagem de nove
   anos imposta às abordagens estruturais.
5. **População municipal do IBGE**, viabilizada pela ampliação do recorte ao estado.
6. **Produção ambulatorial do SIA/SUS**, única fonte capaz de converter escassez
   inferida em escassez com demanda observada, e a de maior custo.

---

## Referências

A redigir em conjunto com a seção 2, cobrindo os cinco blocos ali especificados.

## Pendências de redação

- [ ] Seção 2 integral, com as referências correspondentes.
- [ ] Ablação executada e seção 6.1 reescrita com o resultado.
- [ ] Figuras 1 a 8 geradas e inseridas (remover o comentário da linha de inclusão).
- [ ] Tabela 6, de hiperparâmetros e semente.
- [ ] Revisão do resumo após a conclusão da ablação.
- [ ] Definição do veículo de submissão e adequação ao formato exigido.
