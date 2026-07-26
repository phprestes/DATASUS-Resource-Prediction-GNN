"""
Contrato do projeto: onde os dados moram e qual é o schema.

    paths.py    localização das camadas de dados e dos documentos canônicos
    schema.py   parser estrito de docs/01-selecao-tabelas.md, que deriva as
                tabelas ingeridas, as colunas materializadas, os tipos de
                destino e as chaves

Este pacote é a base da pilha e **não importa** de `src.etl` nem de `src.ml`.
Editar o Markdown de seleção muda o que `schema.py` expõe, e com isso o
pipeline inteiro — não existe segunda lista em código (D-05).
"""
