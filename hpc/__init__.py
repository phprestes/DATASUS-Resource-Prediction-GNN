"""
Pipeline do servidor: o mesmo problema sem as limitações da máquina de 9 GB.

Existe como pacote separado de `src/` porque as duas coisas rodam em lugares
diferentes e não devem interferir: `src/` é o que roda no notebook do
pesquisador, `hpc/` é o que roda no cluster do IME. Ver D-34.

    hpc.config   raiz de dados própria, detecção de hardware e guardas
    hpc.etl      ETL nacional, paralelo por competência, intermediário em SSD
    hpc.ml       tarefa nacional, grafo temporal, treino em CUDA

### O que este pacote levanta

Cada item corresponde a uma troca de informação por viabilidade feita sob 9 GB:

| Limitação | Decisão | O que o servidor faz |
|---|---|---|
| Recorte no estado de São Paulo | D-21 | recorte nacional, 602 mil estabelecimentos |
| Grafo estático cortado em 201701, 45% dos nós sem feature | D-25 | um grafo por transição, cortado na origem |
| Projeção mínima: 298 de 368 colunas fora do grafo | D-23 | projeção completa, com atributo e peso na aresta |
| Negativos 200:1, validação amostrada, um passo por época | D-23 | negativos completos, validação completa, N passos |

### A regra de dependência

`hpc` importa de `src` **apenas o que precisa ser idêntico** para a comparação
entre os dois pipelines valer:

    src.config.schema    docs/01-selecao-tabelas.md é a fonte única da verdade;
                         duplicar o parser recriaria o bug que D-05 eliminou
    src.ml.metrics       AP, AUC e MAP@k têm de ser a mesma implementação
    src.ml.splits        mesma regra de partição temporal
    src.ml.artefatos     mesmo formato de modelo salvo (D-35)
    src.ml.baselines     a trilha 1 não tem gargalo de GPU

Nada mais. Montagem de grafo, tabela de tarefa e laço de treino são próprios, e
**nenhum módulo de `src` importa de `hpc`** — o pipeline do notebook não pode
quebrar por causa de mudança feita para o servidor.
"""
