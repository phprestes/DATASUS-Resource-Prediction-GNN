# Registro de decisões

Uma entrada por decisão estrutural, com o contexto que a motivou, a
consequência prática e o que foi descartado. Serve para que uma escolha não seja
refeita por esquecimento, e para que seja possível reverter uma escolha sabendo
o que ela custava.

Decisões marcadas **pendente** aguardam evidência do
`notebook/00_analise_alvo.ipynb` e devem ser fechadas antes da modelagem.

**Sobre os caminhos de módulo citados abaixo.** As entradas anteriores a D-33 foram
escritas quando `src/` era plano, e os caminhos nelas foram atualizados para os
subpacotes atuais — `src/config/`, `src/etl/` e `src/ml/` — para que continuem
navegáveis. O raciocínio e a evidência de cada decisão estão como foram escritos. As
menções a `src/constant.py`, `src/model.py` e `src/check_changes.py` referem-se a
arquivos apagados e permanecem como registro histórico.

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
verdade. [`src/config/schema.py`](../src/config/schema.py) o lê em tempo de import e dele
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
materializada por [`src/etl/changes.py`](../src/etl/changes.py) como evento de mudança.

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
sai zerada. É o comportamento documentado em `src/etl/changes.py`, não um defeito
dos dados.

---

## D-11 — Resultado de GNN sem baseline ao lado é resultado inválido

**Data:** 2026-07-25 · **Status:** aceita

**Contexto.** `test()` em `src/model.py` usava `data[entity_table].train_mask`
como máscara de avaliação. O número reportado como desempenho de teste era
desempenho no conjunto de treino. A lógica de partição real existia apenas
inline no notebook de modelagem, nunca em `src/`.

**Decisão.** [`src/ml/splits.py`](../src/ml/splits.py) passa a ser o módulo único de
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

**Como não regride.** A validação de `src/config/schema.py` recusa qualquer
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
   `src/ml/graph.py`, que hoje usa a caixa do Brasil, precisa ser apertado para a
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
A classificação `alterada` de `src/etl/changes.py` é confiável para essas duas
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

- `src/ml/graph.py::_empilhar` já intersecta as colunas declaradas com as presentes
  em cada arquivo, e concatena com `promote_options="permissive"`. Estava correto
  por construção, não por sorte.
- Qualquer leitura direta de múltiplos Parquet via DuckDB precisa de
  `union_by_name=true`. Sem isso, falha em vez de degradar.

**Descartado.** Remover as colunas instáveis da seleção. Elas são válidas em oito
dos nove snapshots, e descartá-las por causa de uma competência anômala custaria
mais informação do que o problema que resolve.

**Revisão de 2026-07-26 — a extensão é maior, e o sentido do desvio muda.** A
medição acima partiu das colunas que o doc já declarava. Conferindo os *headers*
dos nove ZIPs contra o doc apareceram mais duas colunas instáveis, ambas em
`tbEstabelecimento` e ambas até então não declaradas (D-27/D-28 as admitem):

| Tabela | Coluna | Presente em |
|---|---|---|
| `tbEstabelecimento` | `co_tipo_abrangencia` | 201701, 201801, 202401, 202501 |
| `tbEstabelecimento` | `st_coworking` | 201701, 201801, 202501 |

E uma tabela inteira falta: `rlEquipeAldeia` não tem CSV em 201901.

Isso não desmente "201901 anômala", mas mostra que o desvio tem duas formas
diferentes. Uma coluna que existe em 2017–2018, desaparece por cinco ou seis
competências e volta em 2024–2025 não é ruído de uma competência: é campo
desativado e reativado no formulário do CNES. A conclusão operacional continua a
mesma — projetar o que existe, `union_by_name=true` sempre —, mas o número de
tabelas afetadas é **quatro**, não três, e a verificação que faltava (header do
CSV contra o doc) virou célula fixa do `notebook/00_analise_alvo.ipynb`.

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

---

## D-25 — O grafo estático precisa ser cortado antes de *todos* os rótulos

**Data:** 2026-07-25 · **Status:** aceita

**Contexto.** As features de estabelecimento são cortadas em
`ParticaoTemporal.fim_do_treino` (202201), o que está correto para features. Ao
montar o grafo relacional com o mesmo corte, apareceu um vazamento de outra
natureza.

**O vazamento.** O grafo é **estático**: uma única estrutura serve treino,
validação e teste. Os rótulos de treino, porém, vêm das transições que terminam
em 201801, 201901, 202001, 202101 e **202201**. Com o grafo cortado em 202201, a
aresta entre estabelecimento e tipo de equipamento naquele snapshot **é o rótulo**
da última transição de treino. O modelo não precisaria aprender nada: bastaria
consultar a própria aresta.

Vale notar que o vazamento não é do teste. O teste é a transição 2025, e o grafo
parava em 2022. O treino é que estava contaminado — o que produziria um modelo
que aprende a ler o grafo em vez de generalizar, e um desempenho de teste
provavelmente **pior**, não melhor. Vazamento no treino engana o processo de
ajuste, não a métrica final.

**Decisão.** `ParticaoTemporal.antes_de_todos_os_rotulos` devolve a origem da
primeira transição de treino — 201701 — e é o corte que o grafo estático usa.
`grafo_relacional_para_data` passa a **exigir** `ate_periodo` e a documentar que
`fim_do_treino` é a escolha errada ali.

**O custo, declarado.** A estrutura do grafo passa a ser a de 2017 para prever
aquisições de 2018 a 2025. É conservador, e desfavorece as trilhas 2 e 3 na
comparação. Continua sendo um teste justo do que o experimento quer medir: as
baselines da trilha 1 não recebem nenhuma informação estrutural, então mesmo um
grafo velho é mais do que elas têm.

Também vale para a trilha 3 pelo mesmo motivo, com um agravante: em 201701 só
1,1% dos estabelecimentos do estado tinham coordenada (D-22). Como D-15 trata a
posição como invariante no tempo e a toma da observação mais antiga disponível, a
trilha 3 não é afetada — a posição não é uma aresta datada.

**A solução correta, não implementada.** Um grafo **temporal**, com arestas
datadas e visibilidade por exemplo: cada par `(u, k)` da transição `t → t+1` veria
apenas arestas com data `≤ t`. É o que o RelBench faz com `time_col` e
amostragem temporal de vizinhança. Custa uma reamostragem do grafo por transição
e não cabia nesta iteração. Fica registrado como a extensão de maior valor para
as trilhas estruturais.

---

## D-26 — Resultado final: as três trilhas

**Data:** 2026-07-25 · **Status:** medido

Recorte estadual, transição de teste 2025. A tabela que vale é a **pareada**, sobre
os 117.146 estabelecimentos posicionáveis, porque só ela compara as três trilhas
no mesmo conjunto de nós (D-15). São 9.818.382 exemplos e 4.974 positivos.

| Modelo | AP | AUC-ROC | MAP@10 | Trilha |
|---|---|---|---|---|
| `gnn_relacional` | **0,00478** | **0,811** | 0,2133 | 2 |
| `gnn_geografica` | 0,00378 | 0,810 | 0,2077 | 3 |
| `gbdt_geral` | 0,00280 | 0,742 | 0,2520 | 1 |
| `popularidade_item` | 0,00215 | 0,729 | **0,2957** | 1 |
| `persistencia` | 0,00051 | 0,500 | 0,0354 | 1 |

### A régua continua funcionando

`persistencia` devolve AP exatamente igual à prevalência (0,000507) e AUC
exatamente 0,500, agora no subconjunto pareado. É a verificação de que o
arcabouço de avaliação não se quebrou ao mudar de recorte e de subconjunto.

### A estrutura acrescenta — em AP e AUC

As duas GNNs superam com folga as três baselines nas duas métricas globais. A
relacional dá **9,4 vezes a prevalência** em AP, contra 5,5 do gradient boosting
tabular; em AUC, 0,811 contra 0,742.

Isso responde afirmativamente à pergunta de pesquisa **nessa dimensão**: a
estrutura da rede carrega informação sobre onde recursos serão adquiridos, além
do que os atributos isolados do estabelecimento explicam.

### Mas as duas GNNs perdem em MAP@10

E perdem para o modelo mais simples de todos. `popularidade_item`, que só sabe
com que frequência cada tipo de equipamento é adquirido e ignora completamente o
estabelecimento, chega a 0,296 contra 0,213 da GNN relacional.

**A explicação mais provável, e é testável.** As duas métricas medem dimensões
diferentes do mesmo escore:

- **AP e AUC** são globais: ordenam todos os pares (estabelecimento, equipamento)
  juntos. Acertar *quais estabelecimentos* adquirem muito já melhora bastante
  essa ordenação, e é justamente o que o grafo informa bem.
- **MAP@10** fixa o estabelecimento e ordena os 99 equipamentos dentro dele. O
  componente "qual estabelecimento" some por construção, e sobra apenas "qual
  equipamento" — que é exatamente o que `popularidade_item` modela e a GNN
  aparentemente não aprendeu.

Ou seja: as GNNs aprenderam a dimensão **estabelecimento** e não a dimensão
**item**. O decoder concatena o embedding do nó com um embedding aprendido do
item e deveria capturar as duas, mas com 500 mil pares por época e parada em 47
épocas provavelmente não convergiu no componente de item.

**Consequência prática, não conclusão fechada.** O próximo experimento óbvio é um
modelo combinado — escore da GNN somado ao log-odds da popularidade do item — que
deve vencer nas duas métricas. Se vencer, confirma o diagnóstico; se não,
refuta-o. Antes disso, nada aqui autoriza dizer que a estrutura é inútil para
ranquear dentro do estabelecimento, apenas que **esta** GNN não a explorou.

### Relacional supera geográfica, mas por pouco

AP de 0,00478 contra 0,00378 favorece a trilha 2. Em AUC, porém, elas empatam
(0,811 contra 0,810). A estrutura relacional inteira — 25 tipos de nó e 48
relações — rende pouco acima do que a simples proximidade física já entrega, o
que é um resultado em si: a maior parte do sinal estrutural parece ser
capturável por vizinhança geográfica, que é muito mais barata de montar.

Custo, para dimensionar: 1.192 segundos de treino na relacional contra 156 na
geográfica.

### O subconjunto posicionável não é aleatório

A prevalência sobe de 0,0428% no conjunto completo para **0,0507%** no
subconjunto pareado — 18% maior. Estabelecimentos com coordenada registrada
adquirem mais equipamento que a média. É o viés de seleção que D-15 e D-17
mandavam reportar, agora quantificado, e é a razão de a comparação pareada ser
obrigatória: sem ela, a trilha 3 pareceria melhor do que é apenas por avaliar
numa população mais fácil.

### O que este resultado não diz

Não diz que o modelo identifica escassez. Diz que aquisição de equipamento é
parcialmente previsível a partir da estrutura da rede. A ponte entre as duas
coisas continua sendo a inferência declarada em D-02, e continua sendo hipótese.

## D-27 — Chave natural: de 2 para 42, tiradas do dicionário e verificadas

**Data:** 2026-07-26 · **Status:** aplicado

`docs/01-selecao-tabelas.md` declarava chave natural para duas tabelas —
`rlEstabEquipamento` e `rlEstabComplementar` (D-18, veredito 2 do notebook 00).
As outras 42 caíam no modo sem chave de `src/etl/changes.py`, em que cada modificação
conta como remoção mais inserção e a taxa de mudança sai inflada. O veredito 3
registrou isso como limitação; era limitação evitável.

**Agora são 42 das 44**, e nenhuma por dedução — cada tupla foi testada contra
todos os snapshots e tem zero duplicatas em todos. Três origens:

| Origem | Tabelas | Exemplo |
|---|---|---|
| PRIMARY KEY composta do dicionário | 25 | `rlEstabInstFisiAssist` = `co_unidade` + `co_instalacao` |
| Chave primária de uma coluna, quando é de fato única | 9 | `tbEstabelecimento` = `co_unidade` |
| Menor combinação única encontrada por busca | 8 | `rlEstabAvaliacao` = `co_unidade` + `co_avaliacao` + `to_chardt_avaliacaoddmmyyyy` |

A terceira origem cobre dois casos: coluna que no CSV tem outro nome que no
dicionário, e chave do dicionário que simplesmente **não** identifica a linha.
`rlMunUnidAcolhim` é do segundo tipo e mostra por que medir importa — o
dicionário dá `co_unidade` + `sq_acolhimento`, tupla que duplica em todos os nove
snapshots (43 linhas de 80 em 201701). Falta `co_municipio`: a tabela liga cada
município atendido a uma unidade de acolhimento, então o município é parte da
identidade. Para testar isso foi preciso primeiro reclassificar `sq_acolhimento`
de `descartada` para `util`, e regenerar a tabela na camada primária.

### As duas chaves antigas estavam infladas

`tp_sus` e `co_tipo_leito` são redundantes:

```
rlEstabEquipamento  (co_unidade, co_equipamento, co_tipo_equipamento)  única
rlEstabComplementar (co_unidade, co_leito)                             única
```

Ambos os subconjuntos coincidem com a PK do dicionário. Chave inflada não é
inofensiva: com `tp_sus` dentro dela, uma linha que apenas troca a
disponibilidade SUS de 1 para 2 conta como remoção mais inserção, que é o
comportamento que a chave natural existe para evitar. As duas foram encurtadas.

### As duas que ficaram de fora

- `rlEstabServClass` — a PK composta do dicionário **não** identifica a linha:
  561 duplicatas em 201701, 822 em 201801, 1.159 em 201901. Nenhuma combinação de
  até quatro colunas materializadas resolve. Importa porque ela é o alvo
  alternativo de primeira escolha (D-18): trocar de alvo exige antes resolver a
  identidade de linha dela.
- `rlEstabSipac` — mesma situação com seis colunas candidatas. É a tabela que o
  dicionário descreve em sete views diferentes.

### Consequências medidas

- **Taxa de mudança recalculada** (`detectar_mudancas(reprocess=True)`, 349 pares
  tabela-transição). O alvo passa a **0,110 · 0,091 · 0,097 · 0,097 · 0,092 ·
  0,083 · 0,079 · 0,087**, mediana 0,091 contra 0,094 de D-10. **A conclusão de
  D-10 não muda**: série plana entre 0,079 e 0,110, sem pico de pandemia,
  densidade anual adequada. A diferença é a esperada — 11 a 17 mil eventos por
  transição migraram de remoção-mais-inserção para `alterada`.
- **`tbEstabelecimento` deixa de ter taxa acima de 1,0.** Era o artefato que o
  veredito 3 mandava ler como "comportamento documentado, não defeito dos dados":
  sem chave, toda linha alterada contava duas vezes. Com `co_unidade` declarada, a
  taxa cai para 0,83 na primeira transição e 0,17–0,25 nas seguintes, e
  `alterada` passa a ser preenchida.
- **`src/ml/gnn.py::escolher_categoria`** preferia `natural[0]` como vocabulário de
  categorias do grafo. Com 41 chaves declaradas isso passaria a escolher
  `co_municipio` (um nó por município, ligando todos os estabelecimentos da
  cidade) ou sequenciais como `co_seq_central` e `sq_acolhimento` (um nó por
  linha, que é exatamente o que D-25 removeu). A função passa a exigir `dtype`
  `category` e a recusar colunas de município, com o município como último
  recurso para as quatro tabelas que não têm outra categoria. Efeito líquido
  sobre o grafo: as mesmas 36 tabelas, e **uma** muda de categoria em relação ao
  comportamento anterior — `rlEquipeNasfEsf`, de `co_municipio_esf` para
  `tp_equipe_esf`, que é melhora. D-26 continua comparável.

### Rejeitado

Declarar chave natural por dedução, sem medir. Foi como as duas primeiras
nasceram, e as duas estavam certas — mas `rlEstabServClass` mostra que a dedução
falha, e falha justamente na tabela em que se ia confiar nela.

## D-28 — Chave estrangeira só quando casa com a pkey do destino

**Data:** 2026-07-26 · **Status:** aplicado

O dicionário do CNES tem chaves estrangeiras **compostas**. O formato de
`01-selecao-tabelas.md` escreve uma coluna por linha, e o RelBench lê cada
`fkey_para` como join da coluna contra a *pkey do destino*. A transcrição
coluna-a-coluna perdeu a composição e produziu 33 declarações em que os valores
da coluna não são valores da pkey do destino.

Medido em 202501, o resultado é aresta vazia:

```
rlEstabEquipeProf.co_cbo  x tbCargaHorariaSus.co_unidade -> 0 de 312 valores casam
rlEstabEquipeProf.co_area x tbEquipe.co_municipio        -> 0 de 3.622 valores casam
```

Pior, `rlEstabEquipeProf.co_unidade` apontava para `tbCargaHorariaSus` e não para
a raiz: a tabela de profissionais das equipes, com 815 mil linhas, era a única
tabela de fato do escopo **sem aresta para `tbEstabelecimento`**. O destino
declarado também não serve como âncora — `tbCargaHorariaSus.co_unidade` tem 6,1
milhões de linhas para 448 mil unidades, ou seja não é chave. `tbProfResidencia`
tinha o mesmo problema, apontando para `tbResidenciaMed`.

**Regra adotada:** `fkey_para` só quando a coluna contém valores da chave
primária declarada do destino; `co_unidade` sempre aponta para
`tbEstabelecimento`, a única tabela cuja pkey é de fato única por snapshot
(560.166 linhas, 560.166 valores em 202501). Os 31 componentes restantes viraram
atributo, com a razão registrada na justificativa da coluna.

### O que continua torto

As ligações com a equipe sobraram pela componente de município
(`co_municipio -> tbEquipe`, `co_municipio -> tbArea`,
`co_municipio -> tbSegmento`): casam 100% dos valores, mas ligam a linha a
*todas* as equipes daquele município. Não é aresta falsa, é aresta grossa demais.
Resolver exige chave estrangeira composta, que nem este formato nem `schema.py`
expressam hoje. Fica registrado como limitação conhecida, não como corrigido.

Na prática ela hoje não chega ao grafo: `colunas_minimas_para_grafo` projeta cada
tabela filha em `co_unidade` mais a categoria (D-23), e `co_municipio` fica fora
da projeção. O `Database` no recorte da capital sai com 33 tabelas e 32
declarações de chave estrangeira, todas `co_unidade -> tbEstabelecimento` — uma
estrela. Se algum dia a projeção crescer, a limitação acima volta a valer.

### Rejeitado

Manter as declarações "porque o dicionário diz". O dicionário diz que as cinco
colunas *juntas* referenciam `TB_CARGA_HORARIA_SUS`; declarar cada uma sozinha
não é uma aproximação disso, é outra afirmação — e essa é falsa nos dados.

## D-29 — 202601 entra na série: dez snapshots, nove transições

**Data:** 2026-07-26 · **Status:** aplicado

A competência 01/2026 foi publicada e entrou. ZIP de 714 MB, 109 CSVs, as 44
tabelas do escopo convertidas. A série canônica passa de nove para **dez**
snapshots e de oito para **nove** transições.

### O que a série nova diz

| Medida | 9 snapshots | 10 snapshots |
|---|---|---|
| Aquisições de equipamento (SP) | 34.571 | **40.880** |
| Candidatos | 73,4 M | 86,7 M |
| Prevalência | 0,0465% | **0,0472%** |
| Estabelecimentos no recorte | 136.561 | 146.500 |
| Cobertura de coordenada | 85,67% | **87,27%** |

A transição nova rende 6.309 aquisições, em linha com as anteriores — sem salto.
A ordem entre alvos candidatos não muda: `rlEstabServClass` segue à frente em
volume (42.208) e `rlEstabEquipamento` segue sendo o alvo pelas razões de D-18,
nenhuma delas de volume. `rlEstabInstFisiAssist` passou de 51 para 56 itens; o
vocabulário de equipamentos continua com 99.

### A partição se move, e isso invalida comparação

`particionar` sempre toma a transição mais recente para teste. Com dez snapshots:

    treino      2018 2019 2020 2021 2022 2023
    validação   2024 2025
    teste       2026

Antes era treino até 2022, validação 2023–2024, teste 2025 — a divisão sob a qual
D-24 e D-26 foram medidas. **Aqueles números continuam válidos para aquela
divisão e não são comparáveis com um número novo.** Reexecutar
`tools/roda_experimento.py` é o que produz a tabela sob a série de dez.

### Três colunas novas no CSV de 202601

Apareceram na conferência de header contra o doc, não no dicionário — que é de
2025 e não as tem:

| Coluna | Classificação | Por quê |
|---|---|---|
| `rlEstabEquipamento.qt_sus` | `util` | Quantidade de equipamentos disponíveis ao SUS; desdobra o sinalizador `tp_sus` e é candidata à tarefa secundária de regressão (D-02) |
| `rlEstabEqpEmbarcacao.tp_veiculo` | `util` | `E`/`P`; a tabela de "embarcações de apoio" passou a comportar veículo terrestre |
| `rlEstabEqpEmbarcacao.no_registro_veiculo` | `descartada` | Identifica um veículo específico (placa, RNM, casco); 89,1% nula |

`qt_sus` existe em uma única competência, então não sustenta série — está
declarada para que a próxima competência a encontre já classificada, não para
entrar em feature agora.

### Onde "nove" estava cravado no código

- `src/etl/extract.py` — `ANO_INICIAL`/`ANO_FINAL`, e `PERIODOS_ANUAIS` derivado. É o
  único lugar onde se acrescenta um janeiro.
- `src/ml/graph.py::CNESDataset` — `val_timestamp` e `test_timestamp` eram literais
  `202301` e `202501`. Agora saem de `particionar(periodos_disponiveis())`. Um
  literal ali faria o RelBench avaliar num período que a partição chama de treino.
- `tests/test_splits.py` — a lista `ANUAIS` era reescrita no arquivo de teste;
  passa a vir de `PERIODOS_ANUAIS`, e há `tests/test_extract.py` guardando a forma
  da série.
- `notebook/00_analise_alvo.ipynb` — o aviso de série incompleta comparava com `9`.

### Verificações reexecutadas sobre os dez snapshots

- Triagem empírica de D-06: **zero rejeições**.
- As 42 chaves naturais de D-27: **zero duplicatas**, em todas as dez.
- Conferência header do CSV contra o doc: as três colunas acima, e nada mais.
- Taxa de mudança do alvo: 0,110 · 0,091 · 0,097 · 0,097 · 0,092 · 0,083 · 0,079 ·
  0,087 · **0,097**, mediana 0,092, amplitude 0,079–0,110. Série ainda plana,
  **D-10 segue fechada**.

Duas coisas quebraram no caminho, e as duas eram bugs que a série de nove
esconde: D-30 e D-31.

## D-30 — `CHAR` do Oracle chega com espaço, e o preenchimento muda

**Data:** 2026-07-26 · **Status:** aplicado

**Sintoma.** Com 202601 na série, a taxa de mudança de `rlEstabEquipamento` na
transição nova deu **1,94**: 1.323.329 inserções e 1.247.979 remoções, zero
alterações. Ou seja, a tabela inteira foi contada como substituída.

**Causa.** O CNES alargou `CO_TIPO_EQUIPAMENTO` de `CHAR(1)` para `CHAR(2)` em
202601 — há um tipo `10` novo — e os valores antigos passaram a vir preenchidos
com espaço:

```
202501: '1', '2', ... '9'
202601: '1 ', '2 ', ... '9 ', '10'
```

`'1' <> '1 '`, então nenhuma linha casou pela chave natural. Medido: o join entre
as duas competências pela chave dava **0** linhas.

**Extensão.** O preenchimento não é novo, é traço do CNES. Seis colunas já vinham
com espaço em **todas** as competências — `rlEstabComplementar.co_tipo_leito`,
`rlEstabProgFundo.tp_estadual_municipal`, `rlEstabServicoApoio.co_caracteristica`
e três de `tbMantenedora`. Por serem consistentes, nunca deram problema. O que
quebra é o preenchimento **mudar** no meio da série.

**Correção.** `to_parquet` passa a aplicar `NULLIF(TRIM(...), '')` nas colunas de
destino `string` e `category`. Espaço à direita não é valor, e string só de espaço
é ausência. As cinco tabelas afetadas foram regeradas nas dez competências.

**Verificado depois.** Zero valores com espaço sobrando; o join entre 202501 e
202601 pela chave natural volta a casar 1.226.691 linhas; as chaves naturais
continuam únicas; a taxa de mudança do alvo na transição nova cai de 1,94 para
0,097, dentro da faixa histórica.

**Descartado.** Normalizar só na comparação de `changes.py`. O Parquet
continuaria com `'1'` e `'1 '`, e o grafo veria duas categorias diferentes para o
mesmo tipo de equipamento — o erro sairia da taxa de mudança e entraria no modelo,
onde é mais difícil de ver.

## D-31 — O diff compara a interseção das colunas, não a lista de um lado

**Data:** 2026-07-26 · **Status:** aplicado

**Sintoma.** `detectar_mudancas` devolvia 393 pares tabela-transição onde deviam
ser 396, com dois erros no log:

```
[ERRO] tbEstabelecimento em 201801->201901: Binder Error:
       Referenced column "st_contrato_formalizado" not found in FROM clause!
```

**Causa.** `diff_tabela` montava a lista de colunas a partir de **um** dos lados
(o snapshot de origem, quando existe) e usava a mesma lista nos dois `SELECT`. Com
as colunas instáveis de D-20, o outro lado não tem a coluna e o SQL não liga.
A transição inteira sumia do resumo — e a falha era silenciosa no que importa:
a taxa de mudança daquela tabela ficava sem um ano, sem nada acusar.

**Correção.** A comparação usa as colunas presentes nos dois snapshots. Uma
coluna que não existe num dos lados não mudou nem deixou de mudar; afirmar
qualquer coisa sobre ela seria invenção.

**Consequência.** 396 de 396 pares, nenhuma tabela com menos de nove transições.
O efeito é maior do que parece: `tbEstabelecimento` e `tbCargaHorariaSus` são as
duas maiores tabelas do escopo, e cada uma tinha um ano faltando na série de taxa
de mudança que D-10 usa.

**Descartado.** Preencher a coluna ausente com `NULL` no lado que não a tem, para
manter a lista cheia. Isso faria toda linha aparecer como alterada na competência
em que a coluna volta, o que é ruído puro — a coluna não mudou, ela passou a
existir.

## D-32 — Resultado sob teste 2026: a GNN relacional passa a vencer as duas métricas

**Data:** 2026-07-26 · **Status:** medido

Reexecução das três trilhas sobre a série de dez snapshots (D-29), recorte
estadual, transição de teste 2026. Tabela pareada, sobre os 127.868
estabelecimentos posicionáveis: 11.411.933 exemplos e 6.309 positivos,
prevalência 0,0553%.

| Modelo | AP | AUC-ROC | MAP@10 | Trilha |
|---|---|---|---|---|
| `gnn_relacional` | **0,01061** | **0,849** | **0,3000** | 2 |
| `gnn_geografica` | 0,00490 | 0,816 | 0,2745 | 3 |
| `gbdt_geral` | 0,00355 | 0,766 | 0,2567 | 1 |
| `popularidade_item` | 0,00220 | 0,700 | 0,2714 | 1 |
| `persistencia` | 0,00055 | 0,500 | 0,0324 | 1 |

Treino: 1.668 s na trilha 2, melhor época 99, AP de validação 0,0097; 160 s na
trilha 3, melhor época 26. Grafo relacional com 25 tipos de nó e 48 relações;
geográfico com 127.868 nós e 1.913.816 arestas. Pico de memória 6,29 GB, dentro de
um cgroup de 7 GB — a primeira tentativa, com teto de 5,5 GB e swap proibido,
morreu na entrada do treino.

### A régua continua funcionando

`persistencia` devolve AP exatamente igual à prevalência e AUC exatamente 0,500,
agora sob outra partição, outra série e outro subconjunto. É a terceira execução
consecutiva em que isso se confirma (D-24, D-26).

### O que inverteu

D-26 registrava o resultado mais desconfortável do trabalho: as GNNs venciam em AP
e AUC e **perdiam** MAP@10 para `popularidade_item`, um modelo que ignora o
estabelecimento. Agora a relacional lidera as duas — 0,300 contra 0,271.

| Modelo | AP em D-26 | AP agora | MAP@10 em D-26 | MAP@10 agora |
|---|---|---|---|---|
| `gnn_relacional` | 0,00478 | 0,01061 | 0,2133 | 0,3000 |
| `gnn_geografica` | 0,00378 | 0,00490 | 0,2077 | 0,2745 |
| `gbdt_geral` | 0,00280 | 0,00355 | 0,2520 | 0,2567 |
| `popularidade_item` | 0,00215 | 0,00220 | 0,2957 | 0,2714 |
| `persistencia` | 0,00051 | 0,00055 | 0,0354 | 0,0324 |

### A atribuição não é limpa, e isso precisa ficar escrito

Três mudanças entraram ao mesmo tempo:

1. **A partição andou** — teste 2026 em vez de 2025, seis transições de treino em
   vez de cinco (D-29).
2. **O grafo relacional ficou correto** — D-28 removeu 33 chaves estrangeiras com
   zero valores casando e devolveu `rlEstabEquipeProf`, 815 mil linhas, para a
   raiz; era a única tabela de fato sem aresta para `tbEstabelecimento`.
3. **O treino foi mais longe** — melhor época 99 contra 47, com hiperparâmetros
   idênticos. A parada antecipada disparou depois porque a validação continuou
   melhorando.

As três baselines quase não se moveram (a maior variação é `gbdt_geral`, de
0,00280 para 0,00355) e as duas GNNs se moveram muito. Isso aponta para as
mudanças estruturais, não para a troca de ano — mas **não é ablation**. A
decomposição é barata e passa a ser o próximo passo: teste 2026 com as FKs antigas,
e teste 2025 com o grafo corrigido.

O item 3 enfraquece retroativamente o diagnóstico de D-26. Lá a hipótese era que o
decoder não convergia no componente de item, com 47 épocas e 500 mil pares por
época; o treino mais longo é consistente com essa hipótese e sugere que parte da
derrota em MAP@10 era falta de convergência, não limitação do desenho.

### Relacional supera geográfica com folga, revertendo outra leitura de D-26

AP 0,01061 contra 0,00490, AUC 0,849 contra 0,816. Em D-26 as duas empatavam em
AUC (0,811 contra 0,810), o que sustentava a leitura de que a proximidade física
capturava quase todo o sinal estrutural e que o schema inteiro rendia pouco a
mais. Com o grafo relacional corrigido, essa leitura cai. O custo de treino segue
desfavorável: dez vezes mais tempo.

### Todos os positivos estão nos posicionáveis

A prevalência sobe de 0,0478% no conjunto completo para 0,0553% no pareado, e o
motivo é mais forte que em D-26: os **6.309 positivos da transição de teste estão
todos** em estabelecimentos com coordenada plausível. Quem adquiriu equipamento
entre 2025 e 2026 está georreferenciado, sem exceção. A comparação não pareada
seria enganosa por construção.

### O que este resultado não diz

Não diz que o modelo identifica escassez — diz que aquisição de equipamento é
parcialmente previsível a partir da estrutura da rede, e a ponte entre as duas
coisas continua sendo a inferência declarada em D-02. Também não diz que a
estrutura relacional é superior por natureza: diz que, com as arestas certas, ela
supera a geográfica neste recorte e nesta transição.

### Limitações que a execução deixou medidas

- **45% dos nós entram sem feature.** As features de nó saem da última observação
  até o corte do grafo (201701, D-25), e o recorte tinha 80.073 estabelecimentos em
  2017 contra 146.679 na série.
- **298 das 368 colunas `util` das tabelas de fato ficam fora do grafo.** A
  projeção mínima de D-23 entrega duas colunas por tabela filha, então a aresta não
  tem peso nem atributo: a GNN sabe que a unidade tem um tipo de equipamento e não
  sabe quantos.

Nenhuma das duas é nova, mas nenhuma estava quantificada.

## D-33 — `src/` separado em três pacotes por responsabilidade

**Data:** 2026-07-26 · **Status:** aplicado

**Contexto.** `src/` tinha treze módulos num único nível, sem indicação de qual
pertencia a qual etapa. `paths.py` e `schema.py` (contrato), `extract.py`,
`to_sql.py`, `to_parquet.py`, `changes.py`, `pipeline.py` (produção de dado) e
`splits.py`, `tasks.py`, `baselines.py`, `graph.py`, `gnn.py`, `metrics.py`
(modelagem) apareciam lado a lado em ordem alfabética. Navegar exigia conhecer o
projeto de antemão, que é exatamente o que a estrutura deveria dispensar.

**Decisão.** Três pacotes, nomeados pela responsabilidade:

| Pacote | Módulos | Responsabilidade |
|---|---|---|
| `src/config/` | `paths.py`, `schema.py` | contrato e constantes: onde os dados moram, qual é o schema |
| `src/etl/` | `extract.py`, `to_sql.py`, `to_parquet.py`, `changes.py`, `pipeline.py` | os quatro estágios que produzem as camadas de dados |
| `src/ml/` | `splits.py`, `tasks.py`, `baselines.py`, `graph.py`, `gnn.py`, `metrics.py` | tarefa, partição, grafos, modelos e métricas |

**A regra que a separação codifica.** A dependência aponta sempre para o
contrato, nunca de volta: `src.config` não importa de `src.etl` nem de `src.ml`, e
`src.etl` não importa de `src.ml`. Cada `__init__.py` carrega o mapa dos próprios
módulos e a regra que obedece, de modo que a decisão de onde colocar um módulo
novo esteja escrita no lugar onde ela é tomada.

**Mudanças de invocação.** Os pontos de entrada por módulo mudaram de caminho:

```
python -m src.pipeline    ->  python -m src.etl.pipeline
python -m src.extract     ->  python -m src.etl.extract
python -m src.to_sql      ->  python -m src.etl.to_sql
python -m src.to_parquet  ->  python -m src.etl.to_parquet
python -m src.changes     ->  python -m src.etl.changes
```

O `Makefile` absorve essa mudança, e continua sendo a entrada recomendada — quem
usa `make` não percebe a reorganização.

**Um detalhe que quebraria em silêncio.** `paths.py` derivava a raiz do projeto
com `Path(__file__).resolve().parent.parent`. Descendo um nível, isso passaria a
apontar para `src/`, e todas as camadas de dados seriam procuradas em
`src/data/`. Corrigido para `parents[2]`, com o comentário explicando que o índice
acompanha a profundidade do arquivo.

**Verificado.** Os 67 testes passam; `src.config`, `src.etl` e `src.ml` importam
por completo; `python -m src.etl.pipeline --help` e `python -m src.etl.changes`
respondem; `make testes`, `make verificar` e `make resultados` funcionam. Os cinco
notebooks e os dois scripts de `tools/` foram atualizados.

**Descartado.** Manter atalhos de compatibilidade em `src/__init__.py`
reexportando os nomes antigos. Dois caminhos válidos para o mesmo módulo é o tipo
de ambiguidade que a reorganização existe para eliminar, e um repositório de
pesquisa com um único consumidor não tem por que carregar essa dívida.
