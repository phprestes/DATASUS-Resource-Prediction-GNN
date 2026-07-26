"""
Configuração do pipeline do servidor: raiz de dados, hardware e guardas.

    paths.py      camadas de dados sob uma raiz própria, fora do repositório
    ambiente.py   detecção de GPU, RAM e VRAM; guardas de execução; procedência

O schema **não** é redefinido aqui: `src.config.schema` continua sendo a única
leitura de `docs/01-selecao-tabelas.md`. Ver a regra de dependência em
`hpc/__init__.py`.

Sem reexportação de propósito: `python -m hpc.config.ambiente` precisa importar o
módulo como `__main__`, e um `from hpc.config import ambiente` aqui faria o
interpretador avisar que o módulo já estava carregado.
"""
