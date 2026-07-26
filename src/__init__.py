"""
Pipeline e modelagem do projeto, separados por responsabilidade.

    src.config   contrato e constantes — onde os dados moram, o schema derivado
                 de docs/01-selecao-tabelas.md
    src.etl      os quatro estágios que produzem as camadas de dados
    src.ml       tarefa, partição, grafos, modelos e métricas

A separação é por responsabilidade e não por conveniência: `src.config` não
importa nada de `src.etl` ou de `src.ml`, e `src.etl` não importa de `src.ml`.
A dependência aponta sempre para o contrato, nunca de volta. Ver D-33.
"""
