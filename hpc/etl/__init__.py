"""
ETL do servidor: as mesmas camadas, produzidas em paralelo e em disco rápido.

    pipeline.py      baixa, ingere e converte, várias competências ao mesmo tempo
    grafo_store.py   materializa os tensores de grafo por transição (camada 05)

**O conteúdo não muda em relação ao ETL do notebook, e isso é proposital.** Os
arquivos de competência do CNES já são nacionais: o recorte espacial só age na
montagem do grafo e da tarefa. Se as duas camadas primárias divergissem, a matriz
de D-34 estaria comparando dado e não técnica — então os estágios reutilizam as
funções de `src.etl`, e o que muda aqui é como elas são chamadas:

- **em paralelo**, uma competência por processo, contra 16 a 40 núcleos;
- **em SSD**, com o intermediário sob `/var/fasttmp`;
- **retomável**, porque sem escalonador o processo pode ser morto em 168 h.
"""
