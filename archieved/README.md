# Código arquivado

Scripts anteriores à refatoração, preservados como registro histórico.

**Não servem de referência de código.** Eles usam a API antiga do RelBench —
`relbench.data`, `relbench.data.task.NodeTask`, `relbench.model.encoder.RelBenchEncoder` —
que não existe na versão 2.1.1 instalada no ambiente. Não rodam, e copiar deles
reintroduz importações mortas.

O que ainda tem valor aqui é a **intenção**, não a implementação:

- `cnes_to_relbench_dataset.py` traz o mapeamento original de arquivo CSV para
  papel no grafo, com as referências ao dicionário de dados (`LFCES004`,
  `LFCES018`, …) anotadas linha por linha. Foi insumo da seleção de tabelas que
  hoje vive em [`docs/01-selecao-tabelas.md`](../docs/01-selecao-tabelas.md).
- `relbench_cnes.py` mostra a primeira tentativa de montar o grafo e a tarefa.
- `analise_cnes.ipynb` e `relbench_cnes.ipynb` são as explorações iniciais.

Ver [`docs/03-decisoes.md`](../docs/03-decisoes.md), D-12.
