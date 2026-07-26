# Esboço do artigo

Estrutura do texto a ser submetido, com o conteúdo que já está medido e marcação
explícita do que falta escrever. É o documento de redação: o README descreve o
repositório, este descreve o argumento.

Os outros quatro documentos de `docs/` são as fontes: metodologia detalhada em
[`02-metodologia.md`](02-metodologia.md), o racional de cada escolha nas 32
entradas de [`03-decisoes.md`](03-decisoes.md), o schema em
[`01-selecao-tabelas.md`](01-selecao-tabelas.md) e o critério para fonte externa
em [`04-dados-externos.md`](04-dados-externos.md).

**Estado da redação:** seções 1, 3, 4, 5 e 7 têm conteúdo medido e podem ser
escritas agora. A seção 2 (trabalhos relacionados) é a lacuna real. A 6 depende
do ablation pendente.

---

## Título provisório

**Escassez de recursos em redes de saúde: a estrutura da rede acrescenta poder
preditivo?**

Alternativa mais direta ao resultado: *Estrutura relacional supera proximidade
geográfica na predição de aquisição de equipamento médico no CNES*.

**Autores.** Pedro H. S. Prestes; orientação de Alexandre C. B. Delbem e
Eric K. Tokuda.

## Resumo (rascunho)

O Cadastro Nacional de Estabelecimentos de Saúde registra o que cada
estabelecimento *tem*, nunca o que precisaria ter. Este trabalho pergunta se a
**estrutura** da rede — quem está perto de quem, quem compartilha o quê — carrega
informação sobre onde recursos serão adquiridos, além do que os atributos isolados
de cada estabelecimento explicam. A tarefa operacional é predizer aquisição de
equipamento médico entre dois snapshots anuais, sobre dez competências do CNES
(01/2017 a 01/2026) no estado de São Paulo: 146.679 estabelecimentos, 99 tipos de
equipamento, 40.880 eventos de aquisição em nove transições, prevalência de
0,047%. Três trilhas veem o mesmo rótulo com informação estrutural diferente —
nenhuma, relacional e geográfica — sob a mesma partição temporal e o mesmo
subconjunto de nós. A GNN relacional atinge AP de 0,0106 e MAP@10 de 0,300,
contra 0,0036 e 0,257 do gradient boosting sem estrutura, e supera também a GNN
puramente geográfica (0,0049 e 0,274). A contribuição metodológica é o desenho que
torna essa comparação interpretável: piso verificável, viés de seleção
quantificado e corte temporal que impede o rótulo de aparecer no grafo.

**Palavras-chave:** CNES; redes de saúde; aprendizado profundo relacional; redes
neurais de grafos; predição de aquisição.

---

## 1. Introdução

### 1.1 A pergunta

> Dado o estado observável da rede de saúde, é possível identificar onde faltam
> recursos assistenciais — e antecipar onde essa falta será suprida no período
> seguinte?

A hipótese é que a resposta depende da **estrutura da rede**, e não apenas dos
atributos isolados de cada estabelecimento. Um hospital sem tomógrafo cercado de
hospitais com tomógrafo é um caso qualitativamente diferente de um hospital sem
tomógrafo isolado a 40 km do próximo. Nenhum modelo que trate estabelecimentos
como linhas independentes de uma tabela distingue os dois.

Testar se essa distinção importa é o objeto do trabalho.

### 1.2 O que o trabalho é, e o que não é

A contribuição **não** é uma rede neural de grafos. É a **diferença medida entre
três abordagens** que veem o mesmo rótulo com informação estrutural diferente:
nenhuma, relacional, geográfica. A GNN é instrumento de medição.

Isso orienta todo o desenho: **resultado negativo é publicável**. Se as GNNs
empatassem com o modelo tabular, a conclusão honesta seria que a estrutura do CNES
não acrescenta poder preditivo para esta tarefa — e o experimento foi montado para
que essa afirmação pudesse ser feita com segurança, em vez de confundida com falha
de implementação.

### 1.3 A limitação central, declarada de saída

**Escassez não é observável no CNES.** O registro diz o que *existe*; não diz o
que era *necessário*. Não há coluna de demanda, fila ou população atendida.

A definição operacional adotada — predizer aquisição de equipamento — é inferência
sobre a regularidade da rede, não medição de necessidade clínica. Um par
(estabelecimento, equipamento) previsto com alta probabilidade e que não se
concretiza é *candidato* a necessidade latente: hipótese a discutir, nunca
resultado a reportar como fato. Registrado em D-02.

### 1.4 Contribuições

1. Um desenho experimental que isola o efeito da informação estrutural sobre uma
   tarefa de predição em rede de saúde, com piso verificável e viés quantificado.
2. A medição, sobre dez anos de CNES no estado de São Paulo, de que a estrutura
   relacional supera tanto o modelo tabular quanto a vizinhança geográfica.
3. Um conjunto de armadilhas documentadas com o efeito de cada uma sobre o número
   reportado — a seção 4.5 e as 32 entradas de `03-decisoes.md`.

---

## 2. Trabalhos relacionados

**Lacuna principal do texto.** Nada aqui está escrito ainda. O que precisa entrar,
com a razão de cada bloco:

- **Aprendizado profundo relacional.** RelBench e a formulação de tarefas
  preditivas direto sobre schema relacional; é a base da trilha 2 e o que
  justifica não achatar as 44 tabelas em uma matriz.
- **GNN em dados de saúde.** Predição sobre redes hospitalares, referência e
  fluxo de pacientes. Situar o que é novo aqui: o grafo é de *recurso instalado*,
  não de paciente ou de coautoria clínica.
- **Predição de demanda e alocação no SUS.** Trabalhos com SIA/SIH e com o próprio
  CNES; mostrar que a literatura brasileira trata sobretudo produção e
  faturamento, e raramente a estrutura da rede como objeto.
- **Aprendizado em grafos geográficos.** kNN espacial e vizinhança física como
  indutor de suavidade; é a trilha 3 e o controle mais informativo do desenho.
- **Métricas em regime de desbalanceamento extremo.** AP e MAP@k contra AUC quando
  a prevalência é da ordem de 10⁻⁴; sustenta a escolha de métrica de destaque da
  seção 4.4.

---

## 3. Dados

### 3.1 Fonte e recorte

Microdados do CNES, ZIPs de competência do banco de produção federal. Não se usa
TABNET nem a API ElasticCNES: entregam dado agregado ou recortado, e a integridade
relacional necessária para montar o grafo só existe no bruto.

| | |
|---|---|
| Recorte espacial | Estado de São Paulo — prefixo IBGE `35`, 645 municípios, 146.679 estabelecimentos |
| Recorte temporal | Dez snapshots anuais de janeiro, 01/2017 a 01/2026 |
| Escopo do schema | 44 tabelas, 393 colunas aprovadas em dois filtros |

O recorte espacial é um prefixo hierárquico: `355030` recupera a capital, `None` o
país. Começou como capital apenas e foi ampliado para o estado porque isso quase
triplica os eventos de aquisição e dá variância a atributos municipais (D-21).

### 3.2 A semântica temporal, que é a parte sutil

Um ZIP de competência é **fotografia do estado atual**, não log de eventos, e
guarda apenas a **última** data de atualização de cada linha. Três consequências:

- A coluna de atualização é **censurada à direita**: usá-la como eixo temporal
  atribui a cada linha um instante que depende de quando o snapshot foi tirado.
- Alteração entre dois snapshots é **irrecuperável**.
- A resolução temporal real do estudo é o **espaçamento entre snapshots**, não a
  granularidade diária da coluna de data.

Daí a unidade de análise ser a **transição** `t → t+1`, e o eixo temporal do grafo
ser a **data do snapshot**, que é exata e uniforme (D-08).

### 3.3 Seleção de tabelas e colunas

A seleção mora em Markdown versionado e é lida em tempo de import pelo código, de
modo que não existe segunda lista para manter em sincronia (D-05). Uma coluna só
entra se passar em dois filtros independentes: **semântico**, significar algo para
a pergunta, e **empírico**, não ser degenerada nos dados reais (D-06).

Duas propriedades do dado que só apareceram com medição e que valem menção no
artigo por serem generalizáveis a qualquer trabalho sobre CNES:

- **O schema oscila.** Quatro tabelas têm colunas que desaparecem e voltam entre
  competências, com 201901 anômala (D-20).
- **Colunas `CHAR(n)` chegam preenchidas com espaço, e o preenchimento muda.** Em
  202601 o CNES alargou o código de tipo de equipamento e `'1'` virou `'1 '`, o
  que fez toda a tabela do alvo ser contada como substituída antes da correção
  (D-30).

---

## 4. Metodologia

Detalhamento em [`02-metodologia.md`](02-metodologia.md); aqui fica o que o artigo
precisa afirmar.

### 4.1 A tarefa

Classificação binária de **aquisição** sobre o grafo bipartido estabelecimento ×
tipo de equipamento: dado que a unidade `u` não tem equipamento do tipo `k` em `t`,
ela passa a ter em `t+1`?

Predição de aresta futura é onde uma GNN tem vantagem estrutural sobre um modelo
tabular, o que faz a comparação entre trilhas medir algo. Regressão da quantidade
existente fica como tarefa secundária.

O regime é de desbalanceamento extremo: 86,7 milhões de pares candidatos para
40.880 eventos, prevalência de 0,047%. Duas restrições do espaço de candidatos
foram testadas e rejeitadas por descartarem positivos ou quase nada (D-19).

### 4.2 As três trilhas

| Trilha | Entrada | O que isola |
|---|---|---|
| 1 — baselines tabulares | features achatadas por estabelecimento, sem relação | quanto do fenômeno se explica sem estrutura nenhuma |
| 2 — relacional | grafo do schema CNES, 25 tipos de nó e 48 relações | ganho da estrutura relacional |
| 3 — geográfica | somente estabelecimentos e proximidade física (kNN, k=10) | ganho da vizinhança física, sem o schema |

O **decoder é o mesmo** nas trilhas 2 e 3: as duas produzem um embedding por
estabelecimento e o combinam com um embedding aprendido do tipo de equipamento. Só
o encoder difere, senão uma diferença de resultado poderia vir do decoder.

A trilha 1 é mantida deliberadamente sem agregado de vizinhança: incluí-lo a
transformaria numa versão pobre da trilha 2 e apagaria a diferença que o
experimento existe para medir.

### 4.3 Partição temporal

Por **transição**, nunca por linha, e nunca sorteada:

| Conjunto | Transições |
|---|---|
| Treino | 2018, 2019, 2020, 2021, 2022, 2023 |
| Validação | 2024, 2025 |
| Teste | 2026 |

A divisão é derivada da série, não configurada: a transição mais recente testa, as
duas anteriores validam, o resto treina. Cada competência nova move a janela um ano
adiante, o que significa que resultado de execuções diferentes só é comparável se a
série for a mesma (D-29).

### 4.4 Métricas

- **MAP@10 por estabelecimento** é a métrica de destaque: responde à pergunta que o
  trabalho faz — quais equipamentos esta unidade provavelmente deveria ter —
  ranqueando os 99 tipos dentro de cada uma.
- **Average precision** é a métrica global, interpretável contra a prevalência: com
  linha de base em 0,00055, um AP de 0,0106 é dezenove vezes o azar.
- **AUC-ROC** entra por comparabilidade com a literatura, com a ressalva de que é
  otimista sob desbalanceamento extremo.
- **Piso verificável.** A baseline de persistência devolve AP exatamente igual à
  prevalência e AUC exatamente 0,500. Qualquer desvio denuncia erro no arcabouço,
  não no modelo — e isso já se confirmou em três execuções (D-24, D-26, D-32).

### 4.5 Armadilhas que custaram correção

Cada uma produziria um resultado plausível e errado. É material de artigo, não
apenas de repositório:

| Armadilha | Efeito se não corrigida |
|---|---|
| Avaliar sobre a máscara de treino | desempenho de treino reportado como de teste (D-11) |
| Grafo estático cortado no fim do treino | o rótulo aparece dentro do grafo na última transição de treino (D-25) |
| Um nó por linha de tabela de fato | 76 milhões de nós, e nenhum vizinho compartilhado entre unidades com o mesmo equipamento (D-25) |
| Chave estrangeira composta transcrita coluna a coluna | 33 declarações com zero valores casando (D-28) |
| Comparar `CHAR(n)` sem normalizar o preenchimento | tabela do alvo inteira contada como substituída (D-30) |
| Empates de MAP@k desfeitos pela ordem das linhas | escore constante parecendo ranqueador competente |

---

## 5. Resultados

Recorte estadual, transição de teste 2026. Tabela **pareada** sobre os 127.868
estabelecimentos posicionáveis — 11.411.933 exemplos, 6.309 positivos, prevalência
0,0553%. Só a comparação pareada é legítima: a trilha 3 alcança apenas quem tem
coordenada, e medir populações diferentes mediria diferença de amostra.

| Modelo | Trilha | AP | AUC-ROC | MAP@10 |
|---|---|---|---|---|
| `gnn_relacional` | 2 | **0,01061** | **0,849** | **0,3000** |
| `gnn_geografica` | 3 | 0,00490 | 0,816 | 0,2745 |
| `gbdt_geral` | 1 | 0,00355 | 0,766 | 0,2567 |
| `popularidade_item` | 1 | 0,00220 | 0,700 | 0,2714 |
| `persistencia` | 1 | 0,00055 | 0,500 | 0,0324 |

Três leituras:

1. **A estrutura acrescenta.** A GNN relacional dá 19,2 vezes a prevalência em AP,
   contra 6,4 do gradient boosting tabular.
2. **E acrescenta também na métrica de destaque.** MAP@10 de 0,300 contra 0,271 do
   modelo que só conhece a popularidade de cada tipo de equipamento. Na execução
   anterior (D-26, teste 2025) essa comparação era o contrário.
3. **Relacional supera geográfica.** 0,0106 contra 0,0049 em AP; em D-26 as duas
   praticamente empatavam em AUC, o que sustentava a leitura de que a proximidade
   física capturava quase todo o sinal estrutural. Com o grafo relacional
   corrigido, essa leitura cai.

O viés de seleção do subconjunto está quantificado: prevalência 0,0478% no conjunto
completo contra 0,0553% no pareado, e os **6.309 positivos da transição de teste
estão todos** em estabelecimentos com coordenada plausível.

Custo: 1.668 s de treino na trilha 2 (melhor época 99), 160 s na trilha 3 (melhor
época 26), pico de 6,3 GB de RAM.

---

## 6. Discussão

**Depende do ablation pendente.** Três coisas mudaram entre a execução de D-26 e a
de D-32: a partição andou um ano, o grafo relacional foi corrigido (D-28) e o
treino foi até a época 99 em vez de parar na 47. As baselines quase não se moveram
e as duas GNNs se moveram muito, o que aponta para a mudança estrutural — mas
afirmar isso exige decompor. O experimento é barato: teste 2026 com as chaves
antigas, e teste 2025 com o grafo corrigido.

Pontos a desenvolver depois disso:

- **Por que AP e MAP@10 discordaram antes e concordam agora.** As duas medem
  dimensões diferentes do mesmo escore — ordenação global contra ordenação dentro
  do estabelecimento — e a convergência tardia do componente de item é a
  explicação candidata.
- **Por que o schema rende mais que a geografia.** Candidata: o vizinho
  compartilhado de categoria conecta unidades distantes que se parecem, o que a
  proximidade física por construção não faz.
- **O que a predição não realizada significa.** É onde a ponte com escassez
  latente teria de ser argumentada, com a cautela de D-02.

---

## 7. Limitações

- **Escassez continua inferida.** O resultado é sobre aquisição, não sobre
  necessidade. Só dado de demanda — a produção ambulatorial do SIA/SUS é a fonte
  candidata — fecharia a ponte.
- **O grafo é estático, e as features também.** Cortado em 2017 para não vazar
  rótulo, descreve uma rede nove anos mais velha que o teste. Pior: as features de
  nó saem do mesmo corte, e o recorte tinha 80.073 estabelecimentos em 2017 contra
  146.679 na série — **45% dos nós entram com vetor vazio**.
- **O grafo relacional é topologia pura.** A projeção que faz a montagem caber em
  9 GB entrega duas colunas por tabela filha, então 298 das 368 colunas `util` das
  tabelas de fato ficam fora: a aresta não tem peso nem atributo.
- **Um estado, uma transição de teste.** Generalização para outros estados não foi
  testada, e o resultado repousa sobre uma única transição de avaliação.
- **A virada de MAP@10 não está decomposta.** Ver seção 6.

---

## 8. Conclusão e trabalhos futuros

A estrutura da rede carrega informação sobre onde recursos serão adquiridos, e a
estrutura relacional carrega mais que a proximidade física. O que o trabalho
estabelece com mais segurança, porém, é o **desenho**: comparação pareada de
verdade, piso verificável, viés quantificado e decisões auditáveis.

Próximos passos, em ordem de valor sobre custo:

1. **Ablation da virada** — separa efeito de partição de efeito de estrutura.
2. **Peso na aresta e feature no fim do treino** — devolvem informação que a
   projeção mínima e o corte de vazamento hoje descartam, sem arquitetura nova.
3. **Escore combinado GNN + popularidade do item** — se superar 0,300 em MAP@10, o
   componente de item continua subaproveitado.
4. **Grafo temporal com visibilidade por exemplo** — remove o handicap de nove anos
   imposto às trilhas estruturais.
5. **População municipal do IBGE** — desbloqueada pela expansão para o estado.
6. **Produção ambulatorial do SIA/SUS** — a única fonte que transformaria escassez
   inferida em escassez com demanda observada, e a mais cara.

---

## Referências

A escrever, junto com a seção 2. Blocos previstos: RelBench e aprendizado
relacional; GNN em saúde; predição de demanda no SUS; grafos geográficos; métricas
sob desbalanceamento extremo.

## Checklist de redação

- [ ] Seção 2 inteira, com as referências.
- [ ] Ablation rodado, e a seção 6 reescrita com o resultado dele.
- [ ] Figura 1: as três trilhas vendo o mesmo rótulo (diagrama).
- [ ] Figura 2: curva de precisão-revocação das cinco previsões.
- [ ] Figura 3: cobertura de coordenada por competência, que motiva a comparação
      pareada.
- [ ] Tabela de hiperparâmetros e semente, para reprodutibilidade.
- [ ] Revisar se o resumo bate com os números finais depois do ablation.
