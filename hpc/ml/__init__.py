"""
Modelagem do servidor: o mesmo alvo, sem os atalhos de memória.

    tarefa.py           tabela de tarefa na raiz do servidor, negativos completos
    grafo_temporal.py   um grafo por transição, com atributo e peso de aresta
    treino.py           laço CUDA: N passos por época, AMP, checkpoint
    experimento.py      orquestrador, com --modo e --recorte

### Os dois modos, e por que existem

`--modo compativel` replica **de propósito** as limitações da máquina de 9 GB:
grafo único cortado antes de todos os rótulos, projeção de duas colunas por tabela
filha, negativos de treino a 200:1 e um passo de gradiente por época.
`--modo completo` levanta as quatro.

Sem o modo compatível, a diferença entre o resultado do notebook e o do servidor
misturaria efeito de técnica com efeito de escopo, e nenhum dos dois seria
atribuível. Com ele, a matriz de D-34 fecha:

                     escopo 35        escopo nacional
    compativel       célula A         célula B
    completo         célula C         célula D
"""
