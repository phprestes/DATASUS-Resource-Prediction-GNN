# Pipeline do servidor e a matriz técnica × escopo

Este documento descreve o segundo pipeline do projeto — o que roda no cluster do IME —
e a comparação que a existência dele torna possível. O passo a passo operacional está
em [`../hpc/README.md`](../hpc/README.md); aqui ficam a motivação, o desenho e o que
cada metade da comparação sustenta.

Numa máquina nova do cluster, do zero ao resultado:

```bash
screen -S ic && make -f hpc/Makefile tudo-do-zero
```

Confere o ambiente, roda o ETL nacional e a bateria completa, nessa ordem, parando no
primeiro estágio que falhar. Os três são retomáveis, então relançar o mesmo comando
depois de uma queda — ou do corte de 168 h do cluster — continua de onde parou.

## 1. Por que dois pipelines

Todo o projeto foi construído sob uma máquina de 9 GB de RAM, e várias decisões
trocaram informação por viabilidade. Quatro estão medidas:

| Limitação | Decisão | Custo medido |
|---|---|---|
| Recorte no estado de São Paulo | D-21 | o país tem 602.160 estabelecimentos contra 146.679 |
| Grafo estático cortado em 201701 | D-25 | rede nove anos mais velha que o teste; **45% dos nós sem feature** |
| Projeção mínima de duas colunas por tabela filha | D-23 | **273 das 343 colunas `util`** fora do grafo; aresta sem peso |
| Negativos 200:1, validação amostrada, um passo por época | D-23 | gradiente de um único minilote por época |

Nenhuma delas é escolha metodológica: são consequências de hardware, e cada uma
descarta informação que o trabalho gostaria de ter usado. Com acesso a um servidor de
440 GB e duas RTX A6000, elas deixam de ser necessárias — mas o pipeline que roda no
notebook **continua tendo de funcionar**, porque é onde a análise exploratória
acontece.

Daí dois pipelines isolados, e não um com bifurcações: uma mudança feita para o
servidor não pode quebrar a execução local.

## 2. O que é compartilhado, e por quê

`hpc/` importa de `src/` **apenas o que precisa ser idêntico** para a comparação valer:

| Compartilhado | Por que não pode divergir |
|---|---|
| `src.config.schema` | `01-selecao-tabelas.md` é a fonte única da verdade do schema; duplicar o parser recriaria o bug que D-05 eliminou |
| `src.ml.metrics` | AP, AUC e MAP@k precisam ser a mesma implementação, senão as células da matriz não se comparam |
| `src.ml.splits` | mesma regra de partição temporal |
| `src.ml.artefatos` | mesmo formato de modelo salvo (D-35) |
| `src.ml.baselines` | a trilha 1 não tem gargalo de GPU, e reimplementá-la criaria uma segunda verdade sobre o piso |

Montagem de grafo, tabela de tarefa e laço de treino são próprios. E **nenhum módulo
de `src` importa de `hpc`**.

O ETL do servidor também reutiliza os estágios locais, o que aqui é requisito e não
economia: os arquivos do CNES já são nacionais — o recorte só age na modelagem —, e se
as duas camadas primárias divergissem a matriz estaria comparando dado em vez de
técnica. `python -m hpc.etl.pipeline --conferir-contra <camada>` compara contagem de
linhas tabela por tabela, e é a verificação que fecha esse risco.

## 3. Isolamento operacional

Três guardas, cada uma vinda de um problema concreto:

- **Raiz de dados própria.** `IC_HPC_DATA`, com default `/var/fasttmp/$USER/ic`, e
  recusa explícita a qualquer caminho dentro do repositório: apontar para `data/`
  sobrescreveria a camada primária do notebook.
- **Recusa de CPU.** Sem escalonador para rejeitar um job mal dimensionado, a recusa
  mora no programa. Cair em CPU em silêncio daria uma execução de dias e um número que
  pareceria comparável ao do servidor.
- **Recusa de máquina pequena.** Abaixo de 64 GB de RAM o pipeline não roda. A guarda
  foi acrescentada depois de uma tentativa de exercitar o caminho completo na estação
  de trabalho esgotar a memória do sistema **e do editor**. A validação da lógica fora
  do servidor é feita com dado sintético (`tests/test_hpc_*.py`).

## 4. A matriz técnica × escopo

Com `--modo compativel | completo` e `--recorte`, técnica e escopo deixam de estar
amarrados:

| | Escopo São Paulo | Escopo nacional |
|---|---|---|
| **Técnica limitada** | célula A — reproduz o resultado do notebook (D-44) | célula B |
| **Técnica completa** | célula C | célula D |

- **A** é o controle: rodada no servidor, deve reproduzir D-44 dentro do ruído de
  semente. Se não reproduzir, a diferença está no código novo — e não no hardware nem
  no escopo. É a única checagem que separa as três coisas. O alvo é D-44 e não D-32:
  D-43 mostrou que todo número de GNN anterior a ele saiu de ordem arbitrária de
  linhas, D-32 incluído, e a inversão que D-32 registrou não se reproduz.
- **B** isola o efeito do **escopo**, com a técnica constante.
- **C** isola o efeito da **técnica**, com o escopo constante. É a extensão do grafo
  temporal medida em São Paulo, comparável diretamente a D-44.
- **D** é o resultado de referência do trabalho.

O alvo de A é medido por `tools/roda_experimento.py`, e ele tem de coincidir com
`notebook/03_modelagem.ipynb` nos três eixos que D-44 fixou: as cinco baselines, 200
épocas e paciência 20.

O modo compatível replica de propósito as quatro limitações. Não é modo de
compatibilidade de código: é **condição experimental**.

## 5. O que o modo completo faz de diferente

### 5.1 Um grafo por transição

Cada transição `t → t+1` recebe um grafo montado com dado **até `t`**. A garantia de
D-25 — nenhuma aresta contemporânea do rótulo — se mantém por construção, e
`verificar_sem_vazamento()` recusa qualquer grafo cujo corte alcance o destino da
transição que ele serve.

Isso remove duas coisas de uma vez: a defasagem de nove anos, e o vetor de features
vazio em 45% dos nós, já que as features saem do mesmo instante do grafo.

**Não é tempo contínuo.** É um grafo por passo, que é a aproximação de 80/20; a
visibilidade por exemplo dentro da transição continua registrada como extensão.

### 5.2 Aresta com peso, e mais de um vocabulário por tabela

A projeção completa entrega 343 colunas das tabelas filhas contra 70 da mínima. Cada
coluna `category` vira um vocabulário próprio — `rlEstabServClass` passa a contribuir
serviço **e** classificação —, as colunas `Int64` viram peso de aresta agregado por par
com soma e `log1p`, e `min_arestas` cai a zero.

O peso é escalar por decisão consciente: `SAGEConv` não aceita atributo de aresta e
`GraphConv` aceita peso. Reduzir o vetor de quantidades a um escalar perde a distinção
entre existente e em uso, mas mantém a intensidade — que a projeção mínima descartava
por completo. O restante do conteúdo entra como vocabulário, não como atributo.

### 5.3 Treino sem atalho

| | notebook | servidor |
|---|---|---|
| Passos de gradiente por época | 1 | `passos × transições` (120 no default) |
| Negativos de treino | 200 por positivo | todos |
| Validação | amostra fixa de 2 M | completa, ou a cada `k` épocas |
| Precisão | fp32 | bf16 com AMP, quando a GPU suporta |
| Retomada | nenhuma | checkpoint por época |

Os grafos ficam em CPU e só o da transição em curso vai para a GPU, o que mantém o
pico de VRAM no tamanho de um grafo em vez da soma — e é o que permite não depender da
VRAM, que a wiki do IME não documenta. Quando a estimativa autoriza, todos são
cacheados.

**A paciência conta validações, não épocas.** Com `--validar-cada k`, apenas uma época
em cada `k` produz medição, e só ela pode avançar a contagem. A versão anterior somava
em toda época: `--validar-cada 5 --paciencia 15` parava depois de três medições em vez
de quinze, e o histórico recebia o melhor AP repetido nas épocas mudas — uma curva
falsa dentro do artefato, sendo que a curva é resultado reportável (metodologia,
seção 6.3). Hoje a época muda grava AP nulo.

**A retomada é de verdade.** O checkpoint carrega pesos correntes, melhores pesos,
estado do Adam, estado dos geradores e o histórico, e uma execução relançada continua
da época seguinte. Antes ele só era escrito, nunca lido: relançar depois do corte de
168 h recomeçava do zero. A semente entra no nome do arquivo, senão a execução da
semente 43 retomaria a da 42. `--sem-retomar` força o recomeço.

## 6. Custo estimado, e o que ainda não foi medido

Do dimensionamento feito sobre a camada primária: 375 milhões de pares candidatos no
recorte nacional, tabela de tarefa em torno de 3,2 GB com a codificação compacta de
D-23, e nove grafos nacionais de uma a duas dezenas de milhões de arestas cada.
Validação completa custa cerca de 83 milhões de pares por época.

**Nenhuma das quatro células foi executada ainda.** O que está verificado é o caminho:
ETL de uma competência no servidor reproduzindo a camada do notebook linha por linha, e
a lógica de grafo, treino e artefato coberta por teste sintético. Os números entram em
D-36 quando as execuções acontecerem.

## 7. Artefatos, e por que eles saem do servidor

Toda execução escreve um pacote em `models/` no mesmo formato dos dois pipelines:
`state_dict` em CPU, manifesto com procedência e perfil da máquina, índice de nós e
itens, histórico de treino e **escore por exemplo**. Ver
[`../models/README.md`](../models/README.md) e D-35.

Duas consequências práticas. Primeira: `make validar RUN=<pacote>` recomputa AP, AUC e
MAP@10 a partir do escore salvo, sem GPU e sem camada de dados — quem recebe o pacote
verifica o número em vez de aceitá-lo. Segunda: as figuras 5 e 6 do
[esboço do artigo](05-esboco-artigo.md), que dependiam de escore por exemplo e estavam
bloqueadas, passam a ser geráveis.
