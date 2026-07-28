# Resultados de execução

Um JSON por execução, gravado incrementalmente pelos dois orquestradores. É o registro
bruto; a leitura e as conclusões ficam em [`03-decisoes.md`](../03-decisoes.md).

| Origem | Nome do arquivo |
|---|---|
| `tools/roda_experimento.py` | `{data}-trilhas-{recorte}-{variante}-s{semente}.json` |
| `hpc/ml/experimento.py` | `{data}-hpc-{recorte}-{modo}-{variante}-s{semente}.json` |
| `hpc/roda_tudo.py` | `{data}-bateria.json`, o manifesto da bateria |

Todo eixo do experimento entra no nome. Sem isso duas execuções que diferem em recorte,
modo, variante de pandemia ou semente sobrescreveriam uma à outra em silêncio — já
aconteceu com a variante de pandemia, que só existia dentro do JSON.

`hpc/roda_tudo.py` usa esses nomes para saber o que já rodou, ignorando a data: a
bateria leva mais de um dia, e casar pela data faria toda célula concluída antes da
meia-noite rodar de novo.
