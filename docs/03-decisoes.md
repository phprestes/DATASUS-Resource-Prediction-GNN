# Registro de decisões

Uma entrada por decisão estrutural, com o contexto que a motivou, a
consequência prática e o que foi descartado. Serve para que uma escolha não seja
refeita por esquecimento, e para que seja possível reverter uma escolha sabendo
o que ela custava.

Decisões marcadas **pendente** aguardam evidência do
`notebook/00_analise_alvo.ipynb` e devem ser fechadas antes da modelagem.

---

## D-01 — Alvo migra de leitos para equipamentos

**Data:** 2026-07-25 · **Status:** aceita, sujeita a confirmação em D-09

**Contexto.** O código previa leitos (`rlEstabComplementar.qt_exist`), enquanto
o projeto escrito tinha como título a identificação de escassez de
equipamentos. As duas coisas divergiram sem registro. O notebook de modelagem
não conseguia superar a baseline de persistência ingênua, e a conclusão
implícita era de que a GNN havia falhado.

**Evidência.** Medida em `docs/relatorio_analise_dados.md`:

| Tabela | 201701 | 202501 | Crescimento | Estabelecimentos cobertos |
|---|---|---|---|---|
| `rlEstabEquipamento` | 747.500 | 1.247.979 | +67% | ~280 mil |
| `rlEstabComplementar` | 53.489 | 59.848 | +12% | ~11 mil |

**Decisão.** Equipamentos passa a ser o alvo. Leitos é rebaixado a alvo de
controle opcional.

**Consequência.** O diagnóstico do resultado anterior muda: a GNN não perdia da
persistência por deficiência de modelo, mas porque o rótulo era esparso — leitos
existem em cerca de 11 mil de 560 mil estabelecimentos — e quase estático, com
12% de variação em oito anos. Sob esse rótulo, persistir é quase ótimo por
construção, e o experimento não conseguia informar nada sobre o modelo.

**Descartado.** Manter leitos como alvo principal. Também descartado abstrair
uma tarefa genérica parametrizável sobre `(tabela, coluna)` antes de haver duas
tarefas de fato em uso.

---

## D-02 — Formulação primária é evento de aquisição, não regressão de quantidade

**Data:** 2026-07-25 · **Status:** aceita

**Contexto.** Com equipamentos definido como alvo, restava escolher a
formulação: prever quanto existe, ou prever o que muda.

**Decisão.** Tarefa primária é classificação binária de **aquisição**: dado que
o estabelecimento `u` não tem equipamento do tipo `k` em `t`, ele passa a ter em
`t+1`? Regressão em `qt_existente` fica como tarefa secundária.

**Justificativa.** Predição de aresta futura em grafo bipartido é onde uma GNN
tem vantagem estrutural sobre um modelo tabular, o que faz a comparação entre
trilhas medir algo. Além disso, a formulação consome diretamente os eventos de
mudança, que é o sinal que o dado realmente carrega.

**Ressalva registrada.** Aquisição não é escassez. A ponte entre as duas — um
par com alta probabilidade predita que não se concretiza é candidato a
necessidade latente — é uma inferência sobre a regularidade da rede, não uma
medição de necessidade clínica. O CNES não tem coluna de demanda. Detalhado na
seção 2.1 de [`02-metodologia.md`](02-metodologia.md).

---

## D-03 — Taxa de utilização descartada por degeneração

**Data:** 2026-07-25 · **Status:** aceita

**Contexto.** `qt_uso / qt_existente` é a definição de escassez mais imediata a
partir das colunas disponíveis.

**Evidência.** Em 202501, `qt_existente` e `qt_uso` têm ambas moda 1, em 69,6% e
69,0% das linhas. A razão é 1,0 na grande maioria dos casos.

**Decisão.** Descartada. A variável não tem variância suficiente para ser alvo.

---

## D-04 — Densidade de snapshots dobra: nove anuais em vez de cinco bienais

**Data:** 2026-07-25 · **Status:** aceita, revisável em D-10

**Contexto.** O projeto original definia cinco snapshots bienais, de 01/2017 a
01/2025. Cinco pontos com dois anos de intervalo produzem quatro transições, o
que não sustenta afirmação sobre dinâmica temporal, e força uma janela de
predição de 730 dias — como estava codificado em `timedelta`.

**Decisão.** Nove snapshots anuais de janeiro, 01/2017 a 01/2025, gerando oito
transições.

**Consequência.** Custo de ETL cerca de duas vezes maior; a partição temporal
passa a ter cinco transições de treino, duas de validação e uma de teste.

**Descartado.** Densidade mensal, que daria resolução muito maior ao custo de
dezenas de gigabytes de dado bruto e exigiria execução em cluster, como o
cronograma original já antecipava. Fica como extensão caso D-10 mostre que anual
é grosseiro demais.

---

## D-05 — A seleção de tabelas passa a morar em Markdown, no repositório

**Data:** 2026-07-25 · **Status:** aceita

**Contexto.** A seleção existia em dois lugares mantidos à mão em paralelo:
`docs/SelecaoTabelas_v2.pdf`, fora do alcance de qualquer verificação, e
`src/constant.py`, com 1298 linhas. As duas fontes já haviam divergido, e nada
detectava a divergência.

**Decisão.** [`01-selecao-tabelas.md`](01-selecao-tabelas.md) é a fonte única da
verdade. [`src/schema.py`](../src/schema.py) o lê em tempo de import e dele
deriva `FACT_TABLES`, `CNES_USEFUL_COLUMNS`, `CNES_DTYPES`, `CNES_PKEY` e
`CNES_FKEY`. `src/constant.py` é removido.

**Consequência.** A divergência entre a lista de tabelas ingeridas e a lista de
tabelas com colunas declaradas fica estruturalmente impossível, porque as duas
passam a ser projeções da mesma tabela Markdown. Em troca, um erro de formatação
no Markdown quebra o import — daí o parser ser estrito e nomear arquivo, seção e
linha no erro, e daí haver teste de parse.

**Procedência.** A primeira versão do doc foi gerada por
[`tools/build_selecao_inicial.py`](../tools/build_selecao_inicial.py), que fez o
join das três fontes anteriores. O script fica no repositório como registro de
origem e não é parte do pipeline. Verificado: a seleção gerada reproduz
exatamente as 44 tabelas e 390 colunas em uso, menos a única coluna rejeitada
pelo novo filtro empírico (ver D-06).

**Descartado.** Manter a verdade em YAML e renderizar o Markdown a partir dele.
Mais robusto a erro de parse, mas transformaria o doc num artefato de build em
vez de um arquivo que se lê e se edita.

---

## D-06 — Seleção de colunas passa a exigir filtro empírico além do semântico

**Data:** 2026-07-25 · **Status:** aceita

**Contexto.** A seleção anterior classificava colunas como Útil ou Não Útil
lendo o dicionário de dados. Critério puramente semântico e a priori: o
dicionário descreve o que a coluna significa, não o que ela contém.

**Decisão.** Uma coluna só é `util` se passar em dois filtros independentes: o
semântico, herdado, e o empírico — não estar 100% nula e não ser constante em
todos os snapshots medidos.

**Evidência que motivou.** `DT_ATUALIZACAO_ORIGEM` é descrita como "data da
primeira entrada no banco de produção federal", semanticamente significativa,
e chega 100% nula em `rlEstabEquipamento` nas duas competências medidas,
enquanto vem preenchida em `rlEstabComplementar`. A diferença é invisível para
quem lê apenas o dicionário.

**Consequência.** Uma coluna em uso foi rejeitada:
`rlEstabRegimeRes.dt_desativacao`, 100% nula em ambos os snapshots medidos. O
efeito é pequeno agora porque só duas competências foram perfiladas; o notebook
00 reaplica o filtro sobre os nove snapshots.

---

## D-07 — Treze tabelas saem do escopo com motivo escrito

**Data:** 2026-07-25 · **Status:** aceita

**Contexto.** `FACT_TABLES` tinha 57 tabelas e `CNES_USEFUL_COLUMNS` tinha 44.
As 13 restantes eram baixadas, extraídas do ZIP, gravadas no DuckDB e então
descartadas em silêncio na conversão para Parquet, por não terem entrada no
dicionário de colunas. O descarte era um efeito colateral de omissão, não uma
decisão.

**Decisão.** As 13 recebem `escopo: fora` declarado em
[`01-selecao-tabelas.md`](01-selecao-tabelas.md), com motivo. Em todas as 13 o
motivo é o mesmo e é verificável: **todas** as colunas da tabela estão
classificadas como Não Útil no dicionário. São `rlEstabEndCompl`,
`rlEstabEquipeMun`, `rlEstabOrgParc`, `rlEstabRepresentante`, `rlEstabTeleCnes`,
`rlJustifPtProf`, `rlJustifPtProfLog`, `rlNasfEsf`, `tbEquipeAtendCompl`,
`tbEquipeChDifer`, `tbEstabBanco`, `tbJustificaDesligaPrf` e
`tbLocalGerenteAdministrador`.

**Consequência.** Deixam de ser ingeridas, o que encurta o ETL. Reincluir
qualquer uma delas é editar uma linha do doc.

---

## D-08 — A unidade de análise é a transição, não a linha

**Data:** 2026-07-25 · **Status:** aceita

**Contexto.** O código usava `to_chardt_atualizacaoddmmyyyy` como `time_col` do
grafo temporal. Cada ZIP de competência é uma fotografia do estado atual do
banco de produção e guarda apenas a **última** `dt_atualizacao` de cada linha,
o que torna essa coluna um valor censurado à direita, dependente de quando o
snapshot foi tirado — e não uma história.

**Decisão.** A unidade de análise passa a ser a transição `t → t+1`,
materializada por [`src/changes.py`](../src/changes.py) como evento de mudança.

O eixo temporal do grafo é a **data do snapshot** (1º de janeiro da
competência), não a coluna de atualização e não a data do evento. Os eventos de
mudança fornecem os rótulos e o filtro opcional de linhas alteradas.

**Por que separar as duas coisas.** A primeira redação desta decisão dizia que o
`time_col` do grafo viria dos eventos, o que estava errado: um grafo montado só
com eventos carrega as mudanças e perde o estado da rede, e sem estado não há
vizinhança para a GNN observar. O grafo precisa responder "como era a rede em
01/2021", e a resposta é o snapshot inteiro daquela data. A data do snapshot
também é preferível por ser conhecida exatamente e uniforme para todas as
linhas do arquivo, ao contrário da coluna de atualização, que é censurada.

**Consequência.** Fica explícito que mudanças intermediárias entre snapshots são
irrecuperáveis, e que a resolução temporal do estudo é o espaçamento entre
snapshots, não a granularidade diária da coluna. Implementa também o filtro
"somente linhas que sofreram alteração" do projeto original, agora como variante
declarada de ablação, e não como efeito colateral.

**Nota histórica.** Existiu um `src/check_changes.py` no projeto, hoje apagado —
o rastro sobrevivia em `meu_projeto_ic.egg-info/SOURCES.txt`. `changes.py`
retoma essa intenção.

---

## D-09 — Alvo e parâmetros só se fecham após o gate empírico

**Data:** 2026-07-25 · **Status:** FECHADA. Ver o resultado em D-18

O `notebook/00_analise_alvo.ipynb` precisa confirmar ou refutar D-01 medindo,
para cada tabela candidata, cobertura de nós, densidade de rótulo, volume de
eventos de aquisição e taxa de mudança entre snapshots. Candidatas:
`rlEstabEquipamento`, `rlEstabComplementar`, `rlEstabServClass`,
`rlEstabInstFisiAssist`.

Fecha também: reaplicação do filtro de D-06 sobre os nove snapshots, unicidade
das chaves naturais declaradas, e viabilidade da trilha geográfica.

O item da trilha geográfica já foi medido e fechado em D-15.

---

## D-10 — Densidade de snapshot é revisável pela evidência

**Data:** 2026-07-25 · **Status:** FECHADA, densidade anual mantida

D-04 fixou nove snapshots anuais provisoriamente, sob a condição de densificar
caso a taxa de mudança mostrasse que um ano esconde ciclos.

**Medido.** Taxa de mudança anual de `rlEstabEquipamento`, sobre as oito
transições, com chave natural declarada e portanto sem a inflação que afeta as
tabelas sem chave:

| Transição | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|---|---|
| Taxa | 0,112 | 0,094 | 0,101 | 0,100 | 0,095 | 0,085 | 0,082 | 0,089 |

Mediana de **0,094**, e a série é notavelmente plana: a amplitude inteira cabe
entre 0,082 e 0,112, sem pico nas transições de pandemia. A mudança é dominada
por inserção — de 63 mil a 89 mil por transição, contra cerca de 10 mil
remoções — coerente com o crescimento de 67% que motivou D-01.

**Decisão.** Densidade anual mantida. Uma taxa estável e moderada é justamente o
que indica que o intervalo não está agregando eventos que se queira separar; não
há evidência de ciclo escondido que justifique o custo de densificar.

**Nota de leitura.** `tbEstabelecimento` aparece com taxa acima de 1,0 em 2018 e
2020. Isso não é mudança real: a tabela não tem chave natural declarada, então
cada modificação conta como uma remoção mais uma inserção, e a coluna `alterada`
sai zerada. É o comportamento documentado em `src/changes.py`, não um defeito
dos dados.

---

## D-11 — Resultado de GNN sem baseline ao lado é resultado inválido

**Data:** 2026-07-25 · **Status:** aceita

**Contexto.** `test()` em `src/model.py` usava `data[entity_table].train_mask`
como máscara de avaliação. O número reportado como desempenho de teste era
desempenho no conjunto de treino. A lógica de partição real existia apenas
inline no notebook de modelagem, nunca em `src/`.

**Decisão.** [`src/splits.py`](../src/splits.py) passa a ser o módulo único de
partição, consumido pelas três trilhas de modelagem, com teste automatizado de
vazamento. Nenhuma métrica de GNN é reportada sem persistência ingênua e modelo
tabular na mesma tabela, sobre a mesma partição.

**Consequência.** Resultados anteriores do projeto não são comparáveis aos novos
e não devem ser citados.

---

## D-12 — `archieved/` é preservado e marcado como API morta

**Data:** 2026-07-25 · **Status:** aceita

Os scripts em `archieved/` usam a API antiga do RelBench — `relbench.data`,
`NodeTask`, `RelBenchEncoder` — inexistente na versão 2.1.1 do ambiente. Ficam
no repositório como registro da intenção original de mapeamento CSV para
tabelas, com um README declarando que não servem de referência de código.

---

## D-13 — Reprodutibilidade: git, dependências pinadas, testes

**Data:** 2026-07-25 · **Status:** aceita

**Contexto.** O projeto não era um repositório git, apesar de ter `.gitignore`.
Não havia declaração de dependências nem testes, e `data/` estava vazia —
portanto nada no repositório era reproduzível.

**Decisão.** Repositório git inicializado com um commit registrando o estado
anterior. `setup.py` promovido a `pyproject.toml` com dependências diretas
declaradas, e `requirements.txt` com o lock completo do ambiente. Suíte de
testes em `tests/`.

**Nota.** As três extensões compiladas do PyG — `pyg-lib`, `torch-scatter`,
`torch-sparse` — não existem no PyPI e exigem o índice de wheels casado com a
versão do torch. A instrução está no cabeçalho de `requirements.txt`.

---

## D-14 — Duas chaves estrangeiras quebradas, encontradas pela validação

**Data:** 2026-07-25 · **Status:** aceita

**Contexto.** A validação estrita introduzida por D-05 recusou o import na
primeira execução, apontando chaves estrangeiras sem destino válido. As duas
estavam em `rlEstabEqpUnidApoio` e existiam desde antes da refatoração.

**O que estava errado.**

| Coluna | Antes | Depois | Natureza |
|---|---|---|---|
| `co_unidade` | `rlEstabEndCompl` | `tbEstabelecimento` | erro de copy-paste: a coluna é descrita no dicionário como "Código do Estabelecimento de Saúde", e nas outras 35 tabelas em que aparece como chave estrangeira aponta para `tbEstabelecimento` |
| `co_endereco_complementar` | `rlEstabEndCompl` | sem chave estrangeira | destino legítimo, mas `rlEstabEndCompl` está fora de escopo por D-07; a coluna fica como atributo simples |

**Consequência.** Sob o código anterior, `dataset.py` montava
`fkey_col_to_pkey_table` apontando para uma tabela que nunca era materializada,
porque `rlEstabEndCompl` não tinha entrada em `CNES_USEFUL_COLUMNS`. O grafo
entregue ao RelBench continha uma referência pendurada. O erro era invisível
justamente porque as duas listas eram mantidas separadamente — o mesmo modo de
falha que D-05 elimina.

**Como não regride.** A validação de `src/schema.py` recusa qualquer
`fkey_para` que não nomeie uma tabela com escopo `incluida`, e falha no import
em vez de seguir com o grafo incompleto.

---

## D-15 — Coordenada é tratada como invariante no tempo, com o custo declarado

**Data:** 2026-07-25 · **Status:** aceita

**Contexto.** A trilha geográfica depende inteiramente de `nu_latitude` e
`nu_longitude`, cujo preenchimento nunca havia sido verificado.

**Medição.** Estabelecimentos de São Paulo (`co_municipio_gestor = 355030`) com
coordenada plausível, por snapshot:

| Snapshot | Estabelecimentos | Com coordenada | Cobertura |
|---|---|---|---|
| 201701 | 19.607 | 89 | **0,45%** |
| 201801 | 20.885 | 218 | 1,04% |
| 201901 | 22.289 | 850 | 3,81% |
| 202001 | 23.771 | 8.032 | **33,79%** |
| 202101 | 25.096 | 12.814 | 51,06% |
| 202201 | 26.790 | 15.412 | **57,53%** |

Há um degrau claro em 2020 — coerente com o CNES ter passado a exigir
geolocalização no cadastro. "Plausível" exclui coordenada zerada e coordenada
fora da caixa que contém o Brasil.

**O problema.** A partição de treino cobre as transições 2018 a 2022 (D-04, seção
6.1 da metodologia). Nas duas primeiras, a cobertura é de 1% e 4%: praticamente
não há nó posicionável, então a trilha geográfica não teria grafo para treinar
justamente na maior parte da janela de treino.

**Decisão.** A posição geográfica é tratada como **atributo invariante no
tempo**: um estabelecimento é posicionado pela coordenada do snapshot mais
antigo em que ela existe, e essa posição vale para todos os períodos.

**O custo, declarado.** Isso é uma forma limitada de olhar adiante: posicionar
em 2018 um estabelecimento cuja coordenada só apareceu em 2021 usa informação
que não estava disponível em 2018. Duas razões para aceitar, e uma para
mitigar:

1. O que se usa é a *localização física*, que muda muito pouco — o registro
   apareceu depois, mas o prédio já estava lá. Não é informação sobre o
   desfecho.
2. A alternativa é restringir a série a 2020 em diante, o que deixa três
   transições e inviabiliza a partição.
3. **Mitigação:** toma-se a observação mais **antiga** disponível, não a mais
   recente, o que minimiza a distância entre o dado usado e o período modelado.

**Alternativas descartadas.** Geocodificar `co_cep` por fonte externa
acrescentaria dependência de dado de terceiro e um erro de posição não medido.
Substituir proximidade física por `co_regiao_saude` mudaria a hipótese da trilha
de vizinhança física para vizinhança administrativa, o que é outra pesquisa.

**Obrigação de reporte.** Toda métrica da trilha geográfica traz o número de
estabelecimentos posicionáveis ao lado, e a comparação com as trilhas 1 e 2
precisa ser feita **sobre o mesmo subconjunto de nós** — comparar uma GNN
geográfica restrita aos posicionáveis com um baseline rodado em todos os
estabelecimentos não mede estrutura, mede diferença de amostra.

---

## D-16 — Dado externo entra como atributo ou denominador, nunca como rótulo

**Data:** 2026-07-25 · **Status:** aceita

**Contexto.** O CNES não tem coluna de demanda, então a definição operacional de
escassez é inferida da regularidade da rede. Fontes do SUS e do IBGE poderiam
fechar essa lacuna, e a pergunta é sob que condições.

**Decisão.** Vale um critério de admissão de seis itens, escrito em
[`04-dados-externos.md`](04-dados-externos.md): chave determinística,
alinhamento temporal, papel declarado, ausência de vazamento, viés de cobertura
mensurável, e custo proporcional ao valor.

O item decisivo é o terceiro. **Nenhuma fonte externa entra como rótulo.** A
tarefa de aquisição é medida inteiramente dentro do CNES, e é isso que torna as
trilhas 1, 2 e 3 comparáveis entre si. Trocar o rótulo por um derivado de dado
externo refaz a comparação inteira, ou seja, é outro trabalho — não uma melhoria
deste.

**Ordem de prioridade, por valor sobre risco.**

1. **Expandir o recorte de São Paulo para a Região Metropolitana ou o estado.**
   É mais barato que qualquer fonte externa — o dado já está baixado e o filtro é
   um parâmetro — e não introduz fonte de erro nova. Ganha variância territorial,
   e com ela habilita a população municipal do IBGE, que existe anualmente para
   todos os municípios e não precisa de mediação geográfica.
2. **População municipal do IBGE**, como denominador e atributo, condicionada ao
   item 1. Com um único município a população é constante e tem variância zero
   dentro da amostra — inútil por construção.
3. **Produção ambulatorial do SIA/SUS**, como atributo defasado. É a candidata
   de maior valor: procedimentos diagnósticos por imagem correspondem quase
   um-para-um aos tipos de equipamento. Condicionada a um teste barato — baixar
   um mês e medir a taxa de pareamento por `co_cnes` e a fração de
   estabelecimentos observáveis.

**Rejeitadas nesta iteração.** SIH/SUS, porque internação é desfecho a jusante do
equipamento enquanto procedimento diagnóstico é o uso direto dele, ao mesmo custo
de parsing. População e renda por setor censitário, porque dependem de um
mapeamento CEP para setor que o IBGE não publica e de um único censo (2022) para
cobrir nove anos.

**O risco que o critério existe para barrar.** SIH e SIA registram apenas
atendimento faturado ao SUS. Estabelecimento privado sem convênio existe no CNES
e não existe nesses sistemas, então ausência ali não é "sem demanda", é "não
observável" — e a diferença correlaciona com natureza jurídica, exatamente a
variável que explica capacidade de investir em equipamento. É confundimento, não
ruído, e integrar sem tratá-lo pioraria o trabalho em vez de deixá-lo neutro.

---

## D-17 — O teto de cobertura das coordenadas é estrutural, não temporal

**Data:** 2026-07-25 · **Status:** SUPERADA POR D-22 — os números abaixo
foram medidos sobre seis das nove competências e subestimam a cobertura.
A conclusão qualitativa (a união acrescenta pouco sobre o melhor snapshot)
permanece; o nível não. · **Corrige uma expectativa de D-15**

**Contexto.** D-15 decidiu tratar a coordenada como invariante no tempo,
posicionando cada estabelecimento pela observação mais antiga disponível. A
premissa implícita era que unir os snapshots elevaria a cobertura.

**Medição.** A união de todos os snapshots disponíveis dá **57,3%** dos 26.790
estabelecimentos de São Paulo posicionáveis — contra 57,5% no melhor snapshot
isolado, 202201. A união não acrescenta praticamente nada: quem não tem
coordenada em 2022 também não tinha nos anos anteriores.

**Consequência.** A decisão de D-15 continua correta pelo motivo certo — ela
permite que a janela de treino de 2018 e 2019 tenha nós, o que sem ela não
aconteceria — mas **não eleva o teto**. Cerca de 43% dos estabelecimentos nunca
serão nós da trilha geográfica, e essa exclusão não é aleatória.

Duas obrigações decorrem, além das já registradas em D-15:

1. Caracterizar quem fica de fora. Se os 43% não posicionáveis diferirem
   sistematicamente em `tp_unidade`, `tp_gestao` ou porte, a trilha geográfica
   não fala sobre a rede — fala sobre um recorte enviesado dela.
2. As coordenadas também são **sujas**: 1,2% das existentes caem fora de uma
   caixa generosa em torno do município, chegando a 197 km do centro numa cidade
   de cerca de 35 km de largura. O filtro de plausibilidade de
   `src/graph.py`, que hoje usa a caixa do Brasil, precisa ser apertado para a
   caixa da amostra.

**Alternativa avaliada e rebaixada a fallback.** `co_cep` tem 100% de
preenchimento e agrupá-lo pelos cinco primeiros dígitos produz 2.271 grupos com
mediana de 4 estabelecimentos — estruturalmente ótimo. Mas validado contra as
coordenadas limpas, o raio mediano ao centroide do grupo é 4,90 km, contra 8,70
km de um controle com os CEPs embaralhados. A razão de 0,56 mostra que CEP-5 é
informativo, porém apenas cerca de duas vezes melhor que agrupar ao azar, numa
cidade cujo raio inteiro é da ordem de 17 km. Não é vizinhança. Detalhado na
seção 2.2 de [`04-dados-externos.md`](04-dados-externos.md).

---

## D-18 — Resultado do gate empírico

**Data:** 2026-07-25 · **Status:** aceita · **Fecha D-09**

Executado sobre as nove competências, camada primária, recorte de São Paulo.

### 1. Alvo: `rlEstabEquipamento` confirmado, com folga

Eventos de aquisição somados nas oito transições, dentro de São Paulo:

| Tabela candidata | Tipos de item | Candidatos | Aquisições | Prevalência mediana |
|---|---|---|---|---|
| `rlEstabEquipamento` | 99 | 18.473.151 | **12.081** | 0,065% |
| `rlEstabServClass` | 72 | 13.919.717 | 8.992 | 0,062% |
| `rlEstabInstFisiAssist` | 51 | 9.350.614 | 7.185 | 0,087% |
| `rlEstabComplementar` (leitos) | 69 | 13.536.992 | **688** | 0,005% |

D-01 se confirma, e por margem maior do que a evidência nacional sugeria. Leitos
produzem 688 aquisições em oito transições — cerca de 86 por transição — o que
não sustenta treino nem avaliação. Equipamentos produzem 17 vezes mais.

`rlEstabInstFisiAssist` tem a maior prevalência e fica registrada como alvo
alternativo caso a modelagem de equipamentos se mostre inviável.

### 2. Chaves naturais: as duas hipóteses estavam certas

Zero duplicatas em 201701 e 202501:

- `rlEstabEquipamento` por (`co_unidade`, `co_equipamento`, `co_tipo_equipamento`, `tp_sus`)
- `rlEstabComplementar` por (`co_unidade`, `co_leito`, `co_tipo_leito`)

Deixam de ser hipóteses derivadas do dicionário e passam a ser fato verificado.
A classificação `alterada` de `src/changes.py` é confiável para essas duas
tabelas, e só para elas.

### 3. Densidade anual: mantida

Ver D-10, fechada com a série de taxas medida.

### 4. Trilha geográfica: teto de 57%

Ver D-15 e D-17, já fechadas antes deste gate.

### 5. Filtro empírico sobre nove snapshots: uma rejeição

`rlEstabUnidAcolhim.tp_sus_nao_sus`, constante em toda a série, reclassificada
para `descartada`. O total de colunas `util` cai de 389 para 388.

O resultado importa mais pelo que **não** mudou: ampliar de duas para nove
competências acrescentou uma única rejeição. A triagem original era representativa,
e o filtro de D-06 é estável — não é um crivo que aperta indefinidamente conforme
se olha mais dado.

---

## D-19 — O desbalanceamento é intrínseco; MAP@k passa a ser a métrica de destaque

**Data:** 2026-07-25 · **Status:** aceita

**Contexto.** A tarefa de aquisição tem prevalência de 0,065%: um positivo a cada
1.530 candidatos. São 18,5 milhões de exemplos para 12 mil eventos. Isso é severo
mesmo para os padrões de predição de aresta.

**Duas restrições do espaço de candidatos foram testadas e ambas rejeitadas.**

1. *Restringir a pares (tipo de unidade, tipo de equipamento) já observados em
   algum lugar do Brasil.* Dos 3.861 pares possíveis, 1.297 nunca ocorrem —
   parecia promissor. Mas corta apenas **1,5%** dos candidatos e nenhum positivo:
   os pares impossíveis combinam tipos raros com equipamentos raros, e quase não
   aparecem em São Paulo. Ganho de prevalência de 1,02x. Não compensa a
   complexidade.
2. *Restringir a estabelecimentos que já têm ao menos um equipamento em `t`.*
   Corta 49,6% dos candidatos, mas leva junto **32,7% dos positivos**, para um
   ganho de prevalência de apenas 1,3x. Além de ser uma troca ruim, excluiria
   justamente a **primeira aquisição** de um estabelecimento — provavelmente o
   evento mais relevante do ponto de vista de política pública.

**Decisão.** Nenhuma restrição. O espaço de candidatos permanece completo, e o
desbalanceamento é tratado como característica do problema, não como defeito a
corrigir por amostragem.

**Consequência para o reporte.** O average precision continua sendo a métrica
principal para comparar modelos entre si, mas o seu **valor absoluto deixa de ser
interpretável** para um leitor: com prevalência de 0,00065, um AP de 0,02 é trinta
vezes a linha de base e ainda assim parece próximo de zero.

**MAP@k por estabelecimento passa a ser a métrica de destaque.** Ela responde à
pergunta que o trabalho de fato faz — "quais equipamentos este estabelecimento
provavelmente deveria ter?" — ranqueando 99 tipos dentro de cada estabelecimento,
onde o desbalanceamento global não distorce a escala. Toda tabela de resultados
traz as duas, com a prevalência ao lado, como já exige D-11.

---

## D-20 — O schema do CNES varia entre competências

**Data:** 2026-07-25 · **Status:** aceita

**Contexto.** A leitura conjunta dos nove snapshots falhou com erro de schema:
`rlEstabPoloAldeia.co_dsei` existe em 201701 e não em 201901.

**Extensão, medida.** Três das 44 tabelas têm colunas instáveis:

| Tabela | Coluna | Ausente em |
|---|---|---|
| `tbEstabelecimento` | `st_contrato_formalizado` | 201901 |
| `rlEstabPoloAldeia` | `co_dsei` | 201901 |
| `tbCargaHorariaSus` | `qt_carga_hor_hosp_sus`, `qt_carga_horaria_outros` | 201901, 202001, 202101 |

O padrão aponta para **201901 como competência anômala**, e não para uma evolução
progressiva do schema: duas das três tabelas perdem a coluna só naquele ano e a
recuperam depois.

**Consequência.** A lista de colunas de
[`01-selecao-tabelas.md`](01-selecao-tabelas.md) descreve o schema *modal*, não um
schema que valha uniformemente na série. Código que lê vários snapshots precisa
ser tolerante a isso:

- `src/graph.py::_empilhar` já intersecta as colunas declaradas com as presentes
  em cada arquivo, e concatena com `promote_options="permissive"`. Estava correto
  por construção, não por sorte.
- Qualquer leitura direta de múltiplos Parquet via DuckDB precisa de
  `union_by_name=true`. Sem isso, falha em vez de degradar.

**Descartado.** Remover as colunas instáveis da seleção. Elas são válidas em oito
dos nove snapshots, e descartá-las por causa de uma competência anômala custaria
mais informação do que o problema que resolve.

---

## D-21 — Recorte passa do município de São Paulo para o estado

**Data:** 2026-07-25 · **Status:** aceita · **Executa a prioridade 1 de D-16**

**Contexto.** D-16 colocou a expansão do recorte como a primeira coisa a fazer,
antes de qualquer fonte externa: é mais barata, o dado já está baixado e não
introduz erro novo.

**Medido**, comparando o município com o estado sobre as nove competências:

| | Município | Estado | Ganho |
|---|---|---|---|
| Estabelecimentos (202501) | 38.688 | 136.561 | 3,5x |
| Municípios distintos | 1 | **645** | habilita o IBGE |
| Aquisições nas 8 transições | 12.081 | **34.571** | 2,9x |
| Candidatos | 18,5 M | 73,4 M | 4,0x |
| Prevalência | 0,065% | 0,047% | pior |
| Cobertura de coordenada | 75,0% | **85,7%** | melhor |

**Decisão.** `RECORTE_PADRAO` passa a ser `'35'`. O recorte deixa de ser um
código de município e vira um **prefixo de código IBGE**, que é hierárquico:
`'35'` é o estado, `'355030'` a capital, `None` o país. Não há caso especial —
município é apenas o prefixo completo.

**O que se ganha.** Quase três vezes mais eventos, que era o principal risco
técnico do projeto (D-19). E 645 municípios em vez de um: a população municipal
do IBGE deixa de ser uma constante de variância zero e passa a ser um atributo
utilizável, o que desbloqueia o item 2 de D-16 sem nenhuma mediação geográfica.

**O que se perde.** A prevalência piora de 0,065% para 0,047%, porque o estado
tem proporcionalmente mais estabelecimentos pequenos, que raramente adquirem
equipamento. O ganho absoluto em positivos compensa com folga.

---

## D-22 — Correção de D-17: o teto das coordenadas é 85,7%, não 57%

**Data:** 2026-07-25 · **Status:** aceita · **Corrige D-17**

D-17 afirmou que a cobertura de coordenada tinha teto estrutural de 57,3% e que
43% dos estabelecimentos jamais seriam nós da trilha geográfica. **O número
estava errado.** A medição rodou quando só seis das nove competências tinham
sido convertidas, e as três que faltavam são justamente as de melhor cobertura.

Cobertura de coordenada plausível, série completa:

| Snapshot | Município | Estado |
|---|---|---|
| 201701 | 0,5% | 1,1% |
| 201901 | 3,8% | 26,4% |
| 202001 | 33,8% | 71,7% |
| 202201 | 57,6% | 79,9% |
| 202501 | **74,7%** | **85,7%** |

União das nove competências: **75,0%** no município e **85,7%** no estado.

**O que muda.** A trilha geográfica é bem mais viável do que D-17 concluiu — no
recorte estadual ela cobre 6 de cada 7 estabelecimentos, não 4 de cada 7. A
obrigação de comparação pareada continua valendo, mas o subconjunto excluído é
menor e a perda de poder estatístico é bem menor.

**O que continua valendo de D-17.** A união acrescenta pouco sobre o melhor
snapshot isolado (85,7% contra 85,7% no estado), então a política de D-15 de
tratar a posição como invariante segue justificada pelo motivo certo: ela dá nós
à janela de treino de 2018 e 2019, onde a cobertura própria é de 1% a 26%.
Continuam valendo também a rejeição do CEP-5 como substituto e o aperto do filtro
de plausibilidade.

**Lição de método, registrada de propósito.** A medição foi feita sobre dados
parciais sem que a parcialidade fosse checada, e virou uma decisão. O
`notebook/00_analise_alvo.ipynb` afirma o número de snapshots disponíveis logo na
primeira célula justamente para que isso não se repita.

---

## D-23 — Otimização de memória: a máquina tem 9 GB, não infinitos

**Data:** 2026-07-25 · **Status:** aceita

**Contexto.** Montar a tarefa no recorte estadual derrubou a IDE do
pesquisador por consumo de RAM. A máquina tem 9 GB no total, com cerca de 3 GB
livres em uso normal.

**Onde a memória ia, e o que foi feito.**

| Causa | Antes | Depois |
|---|---|---|
| Tabela de tarefa com colunas `object` | 3,22 GB | **0,317 GB** |
| Pico ao montar a tabela | 4,87 GB | **3,37 GB** |
| `_codificar` fazia `.astype(str)` do frame inteiro | cópia integral em strings | códigos categóricos em `float32` |
| `Previsao.entidades` guardava strings | ~1 GB no teste do estado | `int32` mais índice |
| `map_at_k` montava DataFrame de 4 colunas e ordenava | >1 GB de pico | `np.lexsort` sobre códigos |
| `por_entidade` varria o vetor inteiro por entidade | O(136k × 37M) | índice invertido em uma passada |

As mudanças estruturais:

1. **Categórico compartilhado, definido antes do laço.** Sem um índice comum, o
   `concat` cairia de volta para `object` e o pico seria o da tabela inteira em
   strings.
2. **Arrow com dicionário em vez de `.df()`.** `fetch_arrow_table` mais `cast`
   para `dictionary(int32, string)` produz `category` sem nunca materializar o
   vetor de objetos Python.
3. **`timestamp` deixa de ser coluna** e vira propriedade derivada de
   `periodo_destino`. Oito bytes por linha para guardar o que já estava
   determinado.
4. **Teto explícito de memória no DuckDB.** Sem ele, o DuckDB dimensiona o buffer
   pela RAM total e disputa memória com o pandas no mesmo processo; com teto, ele
   derrama para disco, que é lento mas termina.

**Efeito colateral bem-vindo.** A montagem também ficou quase duas vezes mais
rápida — 66s para 35s. Menos alocação é menos trabalho.

**Consequência de projeto.** A restrição de memória passa a ser parte do
contrato: código novo que toque a tabela de tarefa não pode materializar
`co_unidade` como string, nem copiar o frame inteiro. `TabelaTarefa.codigos()` e
`Previsao.mascara_de_entidades()` existem para tornar o caminho certo o mais
curto.

---

## D-24 — Primeiro resultado: as baselines no recorte estadual

**Data:** 2026-07-25 · **Status:** medido

Trilha 1 completa, conjunto de teste (transição 2025), 11.671.480 exemplos,
4.994 positivos, prevalência 0,0428%.

| Modelo | AP | AUC-ROC | MAP@10 |
|---|---|---|---|
| `gbdt_geral` | **0,00248** | **0,741** | 0,253 |
| `gbdt_ultimo_snapshot` | 0,00228 | 0,721 | 0,230 |
| `popularidade_item` | 0,00181 | 0,730 | **0,296** |
| `persistencia` | 0,000428 | 0,500 | 0,028 |

### A régua funciona

`persistencia` devolve AP exatamente igual à prevalência (0,000428) e AUC
exatamente 0,500. Não é coincidência, é o que a construção exige, e serve de
verificação de que o arcabouço de avaliação está correto. Se algum dia esse
número divergir da prevalência, há erro no código, não no modelo.

### As duas métricas discordam, e isso é informação

`gbdt_geral` vence em AP e AUC; `popularidade_item` vence em MAP@10 por margem
larga (0,296 contra 0,253). Um modelo pode ordenar melhor **globalmente** e pior
**dentro de cada estabelecimento**.

Isso valida D-19 na prática, e não mais por argumento: a métrica de destaque
tinha de ser o MAP@k, porque o uso pretendido é ranquear equipamentos dentro de
um estabelecimento, não comparar pares de estabelecimentos diferentes entre si.
Um relatório que trouxesse apenas AP concluiria que o GBDT é o melhor modelo da
trilha 1, o que é falso para o uso que se pretende dar a ele.

### A série histórica acrescenta, e agora está medido

`gbdt_geral` supera `gbdt_ultimo_snapshot` nas três métricas. Responde
empiricamente a pergunta que o cronograma original fazia e que nunca havia sido
respondida: treinar sobre a série inteira é melhor que treinar apenas sobre a
transição mais recente. A diferença é modesta mas consistente em AP, AUC e MAP.

### A barra para as GNNs

Qualquer trilha estrutural precisa superar **MAP@10 = 0,296**, que é o que um
modelo obtém sabendo apenas quais tipos de equipamento são comumente adquiridos —
sem olhar para o estabelecimento, para a rede ou para a geografia. Essa é a barra
concreta, e ela não é trivial.

Se as GNNs não a superarem, a conclusão honesta é que a estrutura do CNES não
acrescenta poder preditivo para esta tarefa. É um resultado negativo publicável,
e o desenho experimental foi montado para que ele possa ser afirmado com
segurança em vez de confundido com falha de implementação.

### Nota sobre `por_entidade`

A quinta baseline não entrou nesta execução. Com 136 mil estabelecimentos e um
mínimo de 30 exemplos de treino por entidade, poucos qualificam, e o custo de
ajustar milhares de modelos separados não se justificava antes de haver as GNNs
para comparar. Fica para a execução completa da trilha 1.
