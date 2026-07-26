# Figuras do artigo

Destino das figuras referenciadas por
[`../05-esboco-artigo.md`](../05-esboco-artigo.md). O esboço já contém a legenda e a
linha de inclusão de cada figura, comentada até que o arquivo exista; ao gerar a
figura, basta remover o comentário.

## Convenção de nome

```
fig-NN-descricao-curta.png
```

`NN` é o número da figura no artigo, com dois dígitos, e a descrição usa apenas
minúsculas e hífens. O número precisa coincidir com o do sumário de figuras do
esboço: é por ele que legenda e arquivo se encontram.

## Formato

| Item | Diretriz |
|---|---|
| Formato | PNG para o repositório; PDF ou SVG adicional quando o veículo exigir vetor |
| Resolução | 300 dpi, ou largura mínima de 1600 px |
| Largura útil | pensar em coluna simples (~9 cm) — texto legível quando reduzido |
| Fonte | tamanho tal que o menor rótulo permaneça legível a 50% da escala |
| Cor | paleta segura para daltonismo; nunca usar cor como único codificador |
| Fundo | branco, sem transparência, sem moldura |

## Procedência

Toda figura derivada de dado precisa ser reproduzível. Registre no bloco de código
que a gera, dentro do notebook correspondente, a competência ou o arquivo de
resultado usado. As figuras 3, 4, 5, 6 e 8 saem de dado; as figuras 1, 2 e 7 são
diagramas.

| Figura | Origem |
|---|---|
| `fig-01-arquitetura-pipeline` | diagrama; ferramenta a definir |
| `fig-02-tres-trilhas` | diagrama; ferramenta a definir |
| `fig-03-eventos-por-transicao` | `notebook/00_analise_alvo.ipynb` |
| `fig-04-cobertura-coordenada` | `notebook/00_analise_alvo.ipynb` |
| `fig-05-precisao-revocacao` | `docs/resultados/*.json` |
| `fig-06-map10-por-modelo` | `docs/resultados/*.json` |
| `fig-07-recorte-grafo-relacional` | `notebook/02_relacoes.ipynb` |
| `fig-08-distribuicao-espacial` | `notebook/04_recorte_e_dados_externos.ipynb` |

As figuras 5 e 6 dependem de dado que hoje não é persistido: os arquivos de
`docs/resultados/` guardam as métricas agregadas, e não os escores por exemplo. Gerar
a curva de precisão–revocação exige salvar os escores do conjunto de teste, ou
recalculá-los em execução dedicada.
