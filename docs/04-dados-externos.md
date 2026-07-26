# Dados externos: critério de admissão e avaliação das fontes

O CNES registra o que **existe**. Não registra o que era **necessário**. Não há
coluna de demanda, de fila, ou de população atendida. Toda a definição
operacional de escassez em [`02-metodologia.md`](02-metodologia.md) é, por isso,
uma inferência sobre a regularidade da rede — não uma medição de necessidade.

Fontes externas do SUS e do IBGE podem fechar essa lacuna. Este documento define
**sob que condições** uma fonte entra, avalia as candidatas contra essas
condições, e registra o que foi aceito, adiado e rejeitado.

O princípio que organiza tudo abaixo: incorporar dado externo é barato de propor
e caro de defender. Um dado mal integrado não deixa o trabalho neutro — deixa
pior, porque acrescenta uma fonte de erro que não se sabe medir.

## 1. Critério de admissão

Uma fonte só entra se responder às seis perguntas abaixo com resposta
verificável. Uma resposta "provavelmente dá" reprova.

### C1 — Chave de junção determinística

Existe uma chave que ligue a fonte ao CNES sem heurística? Junção por nome de
estabelecimento, por endereço textual ou por aproximação geográfica introduz erro
de pareamento que se propaga para o rótulo e não é mensurável sem verdade de
referência — que não existe.

Chaves aceitáveis: `co_cnes` (7 dígitos), `co_unidade`, `co_municipio_gestor`,
`co_cep`. Mediação geográfica é aceitável apenas se a taxa de sucesso do
pareamento for medida e reportada.

### C2 — Alinhamento temporal

A fonte cobre 2017–2025 com granularidade de pelo menos um ano, e a semântica do
seu recorte temporal é compatível com a de uma competência do CNES?

Isso reprova fontes censitárias com dois pontos na década: interpolar população
entre 2010 e 2022 e usar o resultado como denominador de uma série anual embute
uma suavização que o modelo pode confundir com sinal.

### C3 — Papel declarado: rótulo, atributo ou denominador

Três papéis, com consequências muito diferentes:

- **Atributo** (feature de entrada) — não muda a pergunta de pesquisa. Menor
  risco.
- **Denominador** (normalização para interpretação) — não muda o que o modelo
  aprende, só como o resultado é lido. Risco baixo, valor alto.
- **Rótulo** — **muda a pergunta de pesquisa**. Refaz toda a comparação entre
  trilhas, que é a contribuição do trabalho.

**Nenhuma fonte externa entra como rótulo nesta iteração.** A tarefa de aquisição
é medida inteiramente dentro do CNES, e é isso que torna as trilhas 1, 2 e 3
comparáveis. Trocar o rótulo por um derivado de dado externo é outro trabalho,
não uma melhoria deste.

### C4 — Ausência de vazamento temporal

Um atributo referente ao período `t+1` não pode entrar na predição de `t+1`.
Isso é especialmente traiçoeiro em dados de produção: o número de procedimentos
realizados em 2025 é altamente informativo sobre o equipamento existente em 2025,
e usá-lo para prever a aquisição de 2025 seria prever o presente com o presente.

Fontes de produção só entram defasadas, com o corte explicitado por
`src/ml/splits.py`.

### C5 — Viés de cobertura mensurável

A fonte cobre o mesmo universo que o CNES? Se não, a ausência é informativa e
não aleatória.

Este critério é o que reprova o uso ingênuo dos sistemas de produção do SUS:
SIH e SIA registram apenas atendimento **faturado ao SUS**. Um estabelecimento
privado sem convênio existe no CNES e não existe no SIA. Um `NULL` ali não
significa "sem demanda", significa "não observável" — e a diferença está
correlacionada com `tp_gestao` e com natureza jurídica, ou seja, com exatamente
as variáveis que explicam capacidade de investir em equipamento.

Fontes que falham em C5 só entram se a ausência puder ser modelada
explicitamente, e se a análise for restrita ao subconjunto observável com o viés
declarado.

### C6 — Custo proporcional ao valor marginal

Volume, formato e esforço de parsing versus o que a fonte acrescenta. Os
microdados do DATASUS vêm em `.dbc` (DBF comprimido com um algoritmo
proprietário), que exige biblioteca específica. Para São Paulo, os arquivos
mensais de produção ambulatorial são da ordem de gigabytes por ano.

## 2. O que o CNES já oferece para junção geográfica

Medido na competência 202201, município de São Paulo, 26.790 estabelecimentos:

| Coluna | Preenchimento | Valores distintos | Serve como chave? |
|---|---|---|---|
| `co_cnes` | 100% | — | sim, chave canônica para SIH/SIA |
| `co_cep` | **100%** | 6.300 | sim, melhor chave territorial disponível |
| `nu_latitude` / `nu_longitude` | **57,3%** | — | parcialmente, ver abaixo |
| `co_regiao_saude` | **6,2%** | 50 | não, cobertura inviável |
| `co_distrito_administrativo` | fora de escopo | — | descrito no dicionário como "Módulo Assistencial", não é distrito da cidade |

### 2.1 As coordenadas têm teto estrutural de 57%

A cobertura cresce de 0,45% em 2017 para 57,5% em 2022 (D-15), mas a **união de
todos os snapshots dá 57,3%** — praticamente idêntica ao melhor snapshot
isolado. Quem não tem coordenada em 2022 também não tinha antes.

Isso corrige a expectativa de D-15: tratar a posição como invariante no tempo
resolve o problema de a janela de treino ficar sem nós, mas **não eleva o teto**.
Cerca de 43% dos estabelecimentos de São Paulo nunca serão nós da trilha
geográfica, e o viés dessa exclusão precisa ser reportado.

Além de esparsas, as coordenadas são **sujas**: 1,2% das que existem caem fora
de uma caixa generosa em torno do município de São Paulo, chegando a 197 km do
centro numa cidade de cerca de 35 km de largura.

### 2.2 CEP-5 é fallback, não substituto

`co_cep` tem cobertura perfeita, o que o torna tentador como definição de
vizinhança. Agrupando pelos cinco primeiros dígitos em São Paulo: 2.271 grupos,
mediana de 4 estabelecimentos, apenas 1,85% isolados. Estruturalmente ótimo.

Mas cobertura não é validade. Validando contra os 15.244 estabelecimentos que
têm coordenada limpa, o raio máximo ao centroide do grupo:

| Agrupamento | Mediana | p90 | Máximo |
|---|---|---|---|
| CEP-5 | 4,90 km | 14,78 km | 53,8 km |
| CEP-5 embaralhado (controle) | 8,70 km | 23,19 km | 57,6 km |

A razão das medianas é **0,56**: CEP-5 é informativo, mas só cerca de duas vezes
melhor que agrupar ao azar. Um raio mediano de 4,9 km não é "vizinhança" numa
cidade cujo raio inteiro é da ordem de 17 km. Um kNN sobre coordenadas reais
produz vizinhos a algumas centenas de metros — uma ordem de grandeza mais fino.

**Decisão:** a trilha geográfica é construída sobre coordenadas, restrita ao
subconjunto posicionável com o viés declarado. CEP-5 pode entrar como **tipo de
aresta distinto** para os 43% sem coordenada, nunca misturado com as arestas
métricas — se entrar, o modelo tem que poder distinguir as duas.

## 3. Avaliação das fontes candidatas

### 3.1 IBGE — população por área submunicipal · **adiada**

**O que acrescentaria.** O denominador. "Não tem tomógrafo" viraria "tem menos
tomógrafos por 100 mil habitantes que áreas comparáveis", que é a formulação
padrão em pesquisa de serviços de saúde e a que dá sentido de política pública ao
resultado.

**Onde falha.** C1 e C2.

- **C1.** A unidade do IBGE é territorial (município, setor censitário, área de
  ponderação); a nossa é o estabelecimento. Como a amostra é **um único
  município**, a população municipal é uma constante e tem variância zero dentro
  da amostra — inútil. Só serve desagregada, o que exige mapear estabelecimento
  para área submunicipal. Isso depende de CEP para setor censitário, mapeamento
  que o IBGE não publica diretamente; a via aberta é o CNEFE do Censo 2022, que
  traz endereços com setor.
- **C2.** Censo em 2010 e 2022. Estimativas anuais existem por município, não por
  setor. Interpolar setor entre dois censos ao longo de nove anos embute
  suavização.

**Condição para reabrir.** Duas coisas, nesta ordem: (1) medir a taxa de
pareamento CEP para setor censitário via CNEFE 2022 sobre os 6.300 CEPs de São
Paulo; (2) se a taxa passar de, digamos, 90%, entrar como **denominador** para
interpretação e como **atributo** de densidade, nunca como rótulo. A dependência
de um único censo (2022) para toda a série precisa ser declarada como limitação.

### 3.2 SIA/SUS — produção ambulatorial · **candidata mais forte, condicionada**

**O que acrescentaria.** O lado da demanda, com ligação direta a equipamento. A
produção ambulatorial contém procedimentos diagnósticos por imagem — tomografia,
ressonância, mamografia — que correspondem quase um-para-um aos tipos de
equipamento de `rlEstabEquipamento`. É a fonte que transformaria "escassez
inferida" em "escassez com demanda observada".

Passa C1 (chave `co_cnes`) e C2 (mensal, cobre a série inteira). A granularidade
mensal também endereçaria D-10 sem novo download de CNES.

**Onde falha.** C5 e C6.

- **C5.** Só atendimento faturado ao SUS. Estabelecimento privado sem convênio
  não aparece, e a ausência correlaciona com natureza jurídica — a mesma variável
  que explica capacidade de investimento. É confundimento, não ruído.
- **C6.** Formato `.dbc`, volume de gigabytes por ano para São Paulo, dependência
  nova (`pysus` ou equivalente) e trabalho de parsing e validação comparável ao
  do próprio ETL do CNES.

**Condição para entrar.** Como **atributo defasado** e apenas para o subconjunto
com produção observável, com três obrigações: um indicador explícito de
"observável no SIA" como feature, para que o modelo não confunda ausência com
zero; a comparação entre trilhas restrita ao mesmo subconjunto; e o defasamento
verificado por `verificar_features_sem_vazamento`.

Passo mínimo antes de qualquer integração: baixar **um** mês, medir a taxa de
pareamento `co_cnes` contra o CNES de São Paulo e a fração de estabelecimentos
observáveis. Um mês responde C1 e C5 a custo baixo.

### 3.3 SIH/SUS — internações hospitalares · **rejeitada nesta iteração**

Passa C1 e C2 pelos mesmos motivos do SIA, e falha em C5 do mesmo jeito. Mas
perde do SIA em relevância: internação é um desfecho a jusante do equipamento,
enquanto procedimento diagnóstico é o uso direto dele. Dado o custo de C6, não
faz sentido pagar por SIH antes de SIA.

### 3.4 IBGE — renda e vulnerabilidade por setor censitário · **rejeitada nesta iteração**

Valiosa e provavelmente a variável mais interessante em termos de política
pública: escassez concentrada em área pobre é a pergunta que importa. Mas herda
integralmente o problema de C1 e C2 do item 3.1, e acrescenta uma pergunta de
pesquisa própria — equidade na distribuição — que não é a deste trabalho.
Registrada como continuação natural.

### 3.5 CNES nacional em vez de um município · **alternativa mais barata que qualquer fonte externa**

Vale registrar porque é o contraponto honesto a todo o resto desta página. O
recorte de São Paulo é o que torna a população do IBGE inútil como atributo
(variância zero) e o que limita o número de nós.

Expandir para a Região Metropolitana, ou para o estado, custa apenas tempo de
ETL — o dado já está baixado, o filtro é um parâmetro — e **não introduz nenhuma
fonte de erro nova**. Ganha variância territorial, e com ela a possibilidade de
usar população municipal, que existe anualmente para todos os municípios e passa
C1 e C2 sem mediação geográfica nenhuma.

Ordenando por valor sobre risco, esta é a primeira coisa a fazer, antes de
qualquer integração externa.

## 4. Decisão

| Fonte | Papel | Status | Bloqueio |
|---|---|---|---|
| Expansão do recorte para RM ou estado | amostra | **recomendada primeiro** | nenhum, só tempo de ETL |
| IBGE população municipal | denominador, atributo | **liberada se o recorte expandir** | depende do item acima |
| IBGE população por setor censitário | denominador, atributo | adiada | medir pareamento CEP para setor via CNEFE 2022 |
| SIA/SUS produção ambulatorial | atributo defasado | condicionada | baixar um mês e medir C1 e C5 |
| SIH/SUS internações | — | rejeitada nesta iteração | perde do SIA em relevância pelo mesmo custo |
| IBGE renda por setor | — | rejeitada nesta iteração | outra pergunta de pesquisa |

Nenhuma fonte externa entra como rótulo. A tarefa permanece medida dentro do
CNES, e é isso que mantém as três trilhas comparáveis.

Registrado como decisão em [`03-decisoes.md`](03-decisoes.md), D-16.
