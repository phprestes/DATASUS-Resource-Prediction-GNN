# Modelos treinados

Um diretório por execução, escrito por [`src/ml/artefatos.py`](../src/ml/artefatos.py)
e lido pelo mesmo módulo. Os **dois** pipelines gravam aqui, no mesmo formato: o desta
máquina ([`tools/roda_experimento.py`](../tools/roda_experimento.py)) e o do servidor
([`hpc/`](../hpc/)). É deliberado — as células da matriz técnica × escopo (D-34) só são
comparáveis se o artefato for lido pelo mesmo código.

## Nome do diretório

```
<AAAA-MM-DD>-<trilha>-<escopo>-<modo>
```

`escopo` é o prefixo IBGE (`35`, `355030`) ou `pais`. `modo` é `compativel` ou
`completo`: duas células da matriz diferem **apenas** nele, e sem isso a segunda
sobrescreveria a primeira.

## Conteúdo

| Arquivo | O que é |
|---|---|
| `manifesto.json` | hiperparâmetros, escopo, modo, partição, corte do grafo, métricas, commit do git, versões de biblioteca e perfil da máquina. **Versionado no git** |
| `modelo.pt` | `state_dict` com tensores em CPU; ausente nas baselines, que não têm pesos |
| `indice.parquet` | ordem de `unidades` e `itens`, como o treino a viu |
| `historico.parquet` | curva de treino por época, quando houve treino |
| `previsoes/teste.parquet` | escore por exemplo: `entidade`, `item`, `y`, `escore` |
| `previsoes/teste-compacto.parquet` | top-50 por estabelecimento mais amostra de resto, com a coluna `origem` |

Só o `manifesto.json` entra no git. Pesos e previsões ficam de fora pelo
[`.gitignore`](.gitignore) local: a previsão do recorte nacional passa de meio
gigabyte, e nada aqui é fonte da verdade — tudo é reproduzível a partir do commit
registrado no manifesto.

## Por que o índice não é opcional

O embedding de item é indexado por **posição**. Um `state_dict` sem a ordem de
`unidades` e `itens` carrega sem erro nenhum e pontua lixo — é a mesma classe de erro
que `IndicePares` existe para evitar, agora atravessando máquinas. `salvar_execucao`
recusa gravar pesos sem índice.

## Usar um pacote

```bash
make validar                      # confere o pacote mais recente
make validar RUN=models/2026-07-26-gnn_relacional-35-compativel
```

```python
from src.ml.artefatos import carregar_execucao, conferir, recomputar_metricas

pacote = carregar_execucao("models/2026-07-26-gnn_relacional-35-compativel")
pacote.manifesto["metricas"]["teste_pareado"]["map@10"]
pacote.previsoes()                # escore por exemplo, para a curva PR
pacote.indice()["itens"]          # ordem dos 99 tipos de equipamento
pacote.pesos()                    # state_dict em CPU

recomputar_metricas(pacote)       # recalcula AP, AUC e MAP@10 do zero
conferir(pacote)                  # [] se o manifesto bate com as previsões
```

`recomputar_metricas` e `conferir` funcionam **sem GPU e sem `data/`**: é o que
significa validar em qualquer dispositivo. Quem recebe o pacote verifica o número em
vez de aceitá-lo por confiança.

## Reconstruir o modelo a partir dos pesos

O `state_dict` não guarda a arquitetura. Para reinstanciar, use o
`manifesto.json`: `trilha` diz se o encoder é relacional (`DynamicHeteroGNN`) ou
geográfico (`GNNGeografica`), e `hiperparametros` traz as dimensões. Reinferir exige o
grafo, e portanto a camada primária — o caminho barato para inspeção é
`previsoes/teste.parquet`, que já traz o escore de cada par.
