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

**Data:** 2026-07-25 · **Status:** pendente

O `notebook/00_analise_alvo.ipynb` precisa confirmar ou refutar D-01 medindo,
para cada tabela candidata, cobertura de nós, densidade de rótulo, volume de
eventos de aquisição e taxa de mudança entre snapshots. Candidatas:
`rlEstabEquipamento`, `rlEstabComplementar`, `rlEstabServClass`,
`rlEstabInstFisiAssist`.

Fecha também: reaplicação do filtro de D-06 sobre os nove snapshots, unicidade
das chaves naturais declaradas, e viabilidade da trilha geográfica.

**Alerta preliminar sobre a trilha geográfica.** Medido na camada primária de
201701: dos 19.607 estabelecimentos de São Paulo, **apenas 0,5% têm
`nu_latitude` preenchida**. Se a cobertura não melhorar substancialmente nos
snapshots recentes, a trilha 3 como especificada não é viável, e as opções são
três — restringir ao subconjunto posicionável declarando o viés de seleção,
geocodificar `co_cep` por fonte externa, ou trocar proximidade física por
proximidade administrativa via `co_regiao_saude`. A escolha depende da medição
completa e será registrada como decisão própria.

---

## D-10 — Densidade de snapshot é revisável pela evidência

**Data:** 2026-07-25 · **Status:** pendente

D-04 fixa nove snapshots anuais provisoriamente. Se o notebook 00 mostrar que a
taxa de mudança anual de `rlEstabEquipamento` é alta o bastante para que um ano
esconda ciclos relevantes, densificar para trimestral ou mensal numa janela
curta, ao custo de reexecutar o ETL.

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
