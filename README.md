# 🏥 Escassez de Recursos em Redes de Saúde: a Estrutura Importa? (Iniciação Científica)

![Python](https://img.shields.io/badge/Python%203.12-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)
![PyG](https://img.shields.io/badge/PyTorch%20Geometric-3C2179?style=for-the-badge&logo=pytorch&logoColor=white)
![RelBench](https://img.shields.io/badge/RelBench-1B3A57?style=for-the-badge&logo=databricks&logoColor=white)
![DuckDB](https://img.shields.io/badge/DuckDB-FFF000?style=for-the-badge&logo=duckdb&logoColor=black)
![Pandas](https://img.shields.io/badge/Pandas-150458?style=for-the-badge&logo=pandas&logoColor=white)
![Arrow](https://img.shields.io/badge/Apache%20Arrow-1A1A1A?style=for-the-badge&logo=apachearrow&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn-%23F7931E.svg?style=for-the-badge&logo=scikit-learn&logoColor=white)
![Jupyter](https://img.shields.io/badge/Jupyter-F37626?style=for-the-badge&logo=jupyter&logoColor=white)
![uv](https://img.shields.io/badge/uv-DE5C2E?style=for-the-badge&logo=uv&logoColor=white)
![pytest](https://img.shields.io/badge/pytest-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white)

Bem-vindo ao repositório da Iniciação Científica sobre os microdados do **CNES**
(Cadastro Nacional de Estabelecimentos de Saúde, DATASUS). O projeto combina
**Engenharia de Dados** (ETL em quatro camadas sobre dez anos de cadastro) com
**Aprendizado Profundo Relacional e Geográfico** (RelBench e PyTorch Geometric) para
medir uma coisa só: se a **estrutura** de uma rede de saúde carrega informação sobre
onde recursos serão adquiridos.

**Pedro H. S. Prestes** · orientação: Alexandre C. B. Delbem e Eric K. Tokuda

---

## 📖 A Grande Ideia: um hospital sem tomógrafo é sempre o mesmo hospital?

> Dado o estado observável da rede de saúde, é possível identificar onde faltam
> recursos assistenciais — e antecipar onde essa falta será suprida no período
> seguinte?

Um hospital sem tomógrafo cercado de hospitais **com** tomógrafo é um caso
qualitativamente diferente de um hospital sem tomógrafo isolado a 40 km do próximo
serviço. Nenhum modelo que trate estabelecimentos como linhas independentes de uma
tabela distingue os dois — e verificar se essa distinção tem efeito mensurável é o
objeto do trabalho.

Cinco notebooks sequenciais conduzem a investigação:

1. **[00_analise_alvo.ipynb](notebook/00_analise_alvo.ipynb)** — o **gate empírico**.
   Ponto de decisão bloqueante: qual tabela é o melhor alvo, se as chaves de linha são
   únicas, se a densidade anual basta, se a trilha geográfica é viável e quais colunas
   o filtro empírico rejeita. Cinco vereditos escritos, todos fechados.
2. **[01_perfil_dados.ipynb](notebook/01_perfil_dados.ipynb)** — perfil da camada
   primária: nulos, cardinalidade e distribuição das 393 colunas aprovadas.
3. **[02_relacoes.ipynb](notebook/02_relacoes.ipynb)** — o grafo do schema CNES,
   derivado do parser e não de uma lista escrita à mão.
4. **[03_modelagem.ipynb](notebook/03_modelagem.ipynb)** — as três trilhas sobre a
   mesma tabela de rótulos e a mesma partição temporal.
5. **[04_recorte_e_dados_externos.ipynb](notebook/04_recorte_e_dados_externos.ipynb)**
   — efeito do recorte espacial e pré-requisitos para admitir fonte externa.

---

## 🔬 Metodologia de Ciência de Dados

**A tarefa.** Classificação binária de **aquisição** sobre o grafo bipartido
estabelecimento × tipo de equipamento: dado que a unidade `u` não tem equipamento do
tipo `k` em `t`, ela passa a ter em `t+1`? É predição de aresta futura — o regime em
que uma GNN tem vantagem estrutural sobre um modelo tabular, o que faz a comparação
medir algo. Regime de desbalanceamento extremo: **86,7 milhões de pares candidatos
para 40.880 eventos**, prevalência de 0,047%.

**As três trilhas.** Mesmo rótulo, mesma partição, mesmo subconjunto de nós na
avaliação. Só a informação estrutural muda:

| Trilha | Entrada | O que isola |
| :--- | :--- | :--- |
| **1 — Baselines tabulares** | atributos achatados por estabelecimento, sem relações | quanto do fenômeno se explica sem estrutura nenhuma |
| **2 — GNN relacional** | grafo do schema CNES: 25 tipos de nó, 48 relações | ganho da estrutura relacional |
| **3 — GNN geográfica** | estabelecimentos e proximidade física (kNN, k=10) | ganho da vizinhança física, sem o schema |

O **decoder é idêntico** nas trilhas 2 e 3 — ambas produzem um embedding por
estabelecimento e o combinam com um embedding aprendido do tipo de equipamento. Só o
encoder difere, senão a diferença de resultado poderia vir do decoder. E a trilha 1
fica deliberadamente livre de agregado de vizinhança: incluí-lo a transformaria numa
versão pobre da trilha 2.

**A partição é temporal, por transição, e nunca sorteada.** A transição mais recente
testa, as duas anteriores validam, o resto treina — derivado da série, não configurado:

| Conjunto | Transições |
| :--- | :--- |
| Treino | 2018, 2019, 2020, 2021, 2022, 2023 |
| Validação | 2024, 2025 |
| Teste | 2026 |

**As métricas, e o piso que as valida.** MAP@10 por estabelecimento é a métrica de
destaque, porque responde à pergunta que o trabalho faz — quais equipamentos esta
unidade provavelmente deveria ter. AP é a métrica global, interpretável contra a
prevalência. E a baseline de **persistência devolve AP exatamente igual à prevalência
e AUC exatamente 0,500**: qualquer desvio denuncia erro no arcabouço de avaliação, e
não no modelo.

### 📚 Fontes e documentação de referência

| Fonte | Relação com o projeto | Acesso |
| :--- | :--- | :--- |
| **Microdados do CNES** — ZIPs de competência do banco de produção federal | Fonte única do estudo. TABNET e API ElasticCNES foram descartados: entregam dado agregado, e a integridade relacional necessária ao grafo só existe no bruto | [cnes.datasus.gov.br](https://cnes.datasus.gov.br/) |
| **Dicionário de Dados do CNES (2025)** | Descreve o banco **Oracle**, não o CSV distribuído; onde os dois discordam, vale o CSV | [`docs/DICIONARIO_DE_DADOS.pdf`](docs/DICIONARIO_DE_DADOS.pdf) |
| **RelBench / PyTorch Geometric** | Base da trilha 2: tarefa preditiva formulada direto sobre o schema relacional, sem achatar as 44 tabelas numa matriz | [relbench.stanford.edu](https://relbench.stanford.edu/) |
| **Esboço do artigo** | Onde o argumento científico e a bibliografia estão sendo montados; a seção de trabalhos relacionados é a lacuna declarada | [`docs/05-esboco-artigo.md`](docs/05-esboco-artigo.md) |

---

## ⚙️ Engenharia de Dados (Pipeline ETL)

O ETL opera em **quatro camadas**, uma competência por vez, descartando o
intermediário ao fim de cada uma — o pico de disco fica em uma competência em vez da
série inteira, e a execução é retomável.

1. **Bruta (`01_raw`)** — `BASE_DE_DADOS_CNES_{YYYYMM}.ZIP`, dez competências, ~3,6 GB.
2. **Intermediária (`02_intermediate`)** — um DuckDB por competência, tudo `VARCHAR`.
   Descartável por construção.
3. **Primária (`03_primary`)** — `{YYYYMM}/{tabela}.parquet`, tipado e comprimido,
   ~2,7 GB. É a camada que se guarda.
4. **Derivada (`04_feature`)** — eventos de mudança entre snapshots consecutivos, que
   são a origem dos rótulos.

**O ponto de projeto que organiza o resto.** O arquivo
[`docs/01-selecao-tabelas.md`](docs/01-selecao-tabelas.md) é a **fonte da verdade do
schema**: [`src/config/schema.py`](src/config/schema.py) o lê em tempo de import e dele derivam as
tabelas ingeridas, as colunas materializadas, os tipos de destino e as chaves.
**Editar aquele Markdown muda o pipeline** — não existe segunda lista em código para
manter em sincronia, e a divergência entre duas listas paralelas foi exatamente o bug
que a refatoração eliminou.

**O tempo é a parte sutil.** Um ZIP de competência é fotografia do estado atual, não
log de eventos, e guarda apenas a última data de atualização de cada linha. Logo: a
coluna de atualização é **censurada à direita**, alteração entre dois snapshots é
**irrecuperável**, e a resolução temporal real do estudo é o **espaçamento entre
snapshots**. Daí a unidade de análise ser a **transição** `t → t+1`, e o eixo temporal
do grafo ser a data do snapshot, que é exata e uniforme.

### Diagramas do pipeline e do schema

As figuras do artigo — arquitetura do pipeline, as três trilhas diante do mesmo
rótulo, recorte do grafo relacional e as visualizações de dado — moram em
[`docs/figuras/`](docs/figuras/), com convenção de nome, formato e procedência
documentada em [`docs/figuras/README.md`](docs/figuras/README.md). O grafo do schema é
gerado por [`notebook/02_relacoes.ipynb`](notebook/02_relacoes.ipynb) a partir do
parser, e não de uma lista mantida à mão.

---

## 📊 Resultados

Recorte estadual (São Paulo), transição de teste 2026, comparação **pareada** sobre os
127.868 estabelecimentos posicionáveis — 11.411.933 exemplos, 6.309 positivos,
prevalência 0,0553%:

| Modelo | Trilha | AP | AUC-ROC | MAP@10 |
| :--- | :---: | ---: | ---: | ---: |
| **`gnn_relacional`** | 2 | **0,01061** | **0,849** | **0,3000** |
| `gnn_geografica` | 3 | 0,00490 | 0,816 | 0,2745 |
| `gbdt_geral` | 1 | 0,00355 | 0,766 | 0,2567 |
| `popularidade_item` | 1 | 0,00220 | 0,700 | 0,2714 |
| `persistencia` | 1 | 0,00055 | 0,500 | 0,0324 |

- **A estrutura acrescenta.** A GNN relacional dá **19,2 vezes a prevalência** em AP,
  contra 6,4 do gradient boosting tabular.
- **E acrescenta na métrica de destaque.** MAP@10 de 0,300 contra 0,271 do modelo que
  só conhece a popularidade de cada tipo de equipamento e ignora o estabelecimento. Na
  execução anterior essa comparação era o contrário.
- **Relacional supera geográfica.** 0,0106 contra 0,0049 em AP, a um custo de treino
  dez vezes maior — 1.668 s contra 160 s.

Resultados brutos em [`docs/resultados/`](docs/resultados/); `make resultados` imprime
a tabela do mais recente, e `make modelos` lista os pacotes de modelo com escore por
exemplo.

**O que vem a seguir.** As limitações de memória que moldaram estes números — recorte
estadual, grafo estático, projeção mínima, negativos subamostrados — foram levantadas no
pipeline do servidor. A comparação passa a ser uma matriz de quatro células, técnica ×
escopo, descrita em [`docs/06-pipeline-hpc.md`](docs/06-pipeline-hpc.md) e ainda sem
execução (D-36).

---

## 🛠️ Como Executar (O Makefile)

Qualquer passo do projeto é abstraído pelo `Makefile` na raiz. Digite `make` (ou
`make help`) para a lista autodocumentada:

```bash
# Ambiente
make setup                                   # .venv, pacote editável e extensões do PyG

# Pipeline de dados
make etl                                     # ETL completo da série canônica
make etl-periodo PERIODOS=202601             # só uma competência
make mudancas                                # recalcula os eventos de mudança
make reprocessar-tabelas TABELAS=tbEstabelecimento PERIODO=202601

# Experimento
make experimento                             # as três trilhas (~55 min, teto de memória)
make experimento-baselines                   # só a trilha 1 (~15 min)
make experimento-capital                     # recorte da capital, barato para depuração
make resultados                              # tabela pareada do resultado mais recente

# Qualidade e limpeza
make testes                                  # 67 testes
make verificar                               # testes + resumo do schema derivado do doc
make limpar-intermediario                    # apaga a camada 02, que é descartável
```

---

## 🛡️ Boas Práticas e Qualidade de Código

- **Documento como fonte da verdade.** O schema mora em Markdown versionado e é lido
  no import; o parser é estrito e **quebra o import** em vez de carregar um schema
  silenciosamente incompleto.
- **Testes deliberadamente negativos.** Os 67 testes existem para que a partição
  temporal, o schema e o diff entre snapshots **falhem** em vez de produzir um número
  bonito e errado. Cada modo de falha coberto já ocorreu neste projeto ao menos uma vez.
- **Decisões auditáveis.** 36 entradas numeradas em
  [`docs/03-decisoes.md`](docs/03-decisoes.md), cada uma com a evidência que a motivou
  e o que foi rejeitado. Quando o código parecer surpreendente, a razão está num `D-nn`.
- **Gerenciamento moderno de pacotes.** Ecossistema `uv` com `pyproject.toml`, e lock
  completo em `requirements.txt`.
- **Reprodutibilidade defensiva.** Todos os estágios do ETL usam `reprocess=False` por
  padrão: a série tem vários gigabytes e rebaixar por acidente é caro.
- **Pendência declarada.** Não há CI configurado neste repositório — `make verificar` é
  hoje o portão manual equivalente.

---

## 📁 Estrutura do Projeto

```text
📦 IC
├── 📂 docs/                      # O contrato do projeto — o código é downstream daqui
│   ├── 01-selecao-tabelas.md     # FONTE DA VERDADE do schema; lida por schema.py
│   ├── 02-metodologia.md         # desenho experimental detalhado
│   ├── 03-decisoes.md            # 36 decisões numeradas, com evidência e o rejeitado
│   ├── 04-dados-externos.md      # teste de admissão para fontes do SUS e do IBGE
│   ├── 05-esboco-artigo.md       # estrutura do artigo, figuras e pendências
│   ├── 06-pipeline-hpc.md        # pipeline do servidor e a matriz técnica × escopo
│   ├── 📂 figuras/               # figuras do artigo, com convenção documentada
│   ├── 📂 resultados/            # JSON de cada execução das trilhas
│   └── DICIONARIO_DE_DADOS.pdf   # dicionário do DATASUS (descreve o Oracle)
├── 📂 src/                       # Três pacotes, separados por responsabilidade
│   ├── 📂 config/                # Contrato: onde os dados moram e qual é o schema
│   │   ├── paths.py              # localização das camadas e dos documentos
│   │   └── schema.py             # parser estrito do doc de seleção
│   ├── 📂 etl/                   # Os quatro estágios que produzem as camadas
│   │   ├── extract.py            # 01_raw — download dos ZIPs
│   │   ├── to_sql.py             # 02_intermediate — CSV para DuckDB
│   │   ├── to_parquet.py         # 03_primary — DuckDB para Parquet tipado
│   │   ├── changes.py            # 04_feature — diff entre snapshots
│   │   └── pipeline.py           # orquestra, uma competência por vez
│   └── 📂 ml/                    # Tarefa, grafos, modelos e avaliação
│       ├── splits.py             # a partição temporal única
│       ├── tasks.py              # tabelas de rótulo: aquisição e quantidade
│       ├── baselines.py          # trilha 1
│       ├── graph.py              # trilhas 2 e 3 — Database e grafo geográfico
│       ├── gnn.py                # encoders, decoder compartilhado, treino
│       └── metrics.py            # AP, AUC, MAP@k, RMSE/MAE
├── 📂 notebook/                  # Investigação e visualização
│   ├── 00_analise_alvo.ipynb     # gate empírico bloqueante
│   └── ...                       # perfil, relações, modelagem, recorte
├── 📂 hpc/                       # Pipeline do servidor: nacional, CUDA, isolado
│   ├── config/                   # raiz de dados própria, detecção de GPU, guardas
│   ├── etl/                      # ETL paralelo e a camada 05 de grafos
│   ├── ml/                       # tarefa nacional, grafo temporal, treino CUDA
│   ├── Makefile                  # alvos do servidor
│   └── README.md                 # como rodar no brucutuvii, do zero
├── 📂 models/                    # Pacotes de modelo dos dois pipelines
├── 📂 tests/                     # 101 testes, todos negativos por desenho
├── 📂 tools/                     # roda_experimento.py e o migrador de procedência
├── 📂 data/                      # (criado dinamicamente) nada versionado
│   ├── 01_raw/                   # ZIPs de competência
│   ├── 02_intermediate/          # DuckDB descartável
│   ├── 03_primary/               # Parquet tipado
│   └── 04_feature/               # eventos de mudança
├── Makefile                      # Automação de tarefas (CLI autodocumentada)
├── pyproject.toml                # Definições do projeto e dependências (uv)
└── README.md                     # Você está aqui!
```

---

## 📄 Licença e dados

Os dados do CNES são públicos, publicados pelo DATASUS. Nada sob `data/` é versionado:
tudo é reprodutível a partir do estágio 1 do ETL.
