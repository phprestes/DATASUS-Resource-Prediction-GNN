"""
Modelagem: da tabela de rótulos às métricas, nas três trilhas.

    splits.py      a partição temporal única, consumida por todas as trilhas
    tasks.py       tabelas de rótulo: aquisição (primária) e quantidade
    baselines.py   trilha 1 — cinco previsões sem informação estrutural
    graph.py       trilhas 2 e 3 — Database do RelBench e grafo geográfico
    gnn.py         encoders, decoder compartilhado e laço de treino
    metrics.py     AP, AUC, MAP@k, RMSE/MAE e a tabela de resultados

O que mantém as trilhas comparáveis vive aqui: todas consomem a mesma
`TabelaTarefa` e a mesma `ParticaoTemporal`, e todas devolvem `Previsao`, de
modo que `metrics.tabela_de_resultados` recebe tudo junto (D-11).
"""
