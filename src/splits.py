"""
Partição temporal, módulo único consumido pelas três trilhas de modelagem.

Existe por causa de um erro concreto: a função de teste em `src/model.py` usava
`data[entity_table].train_mask` como máscara de avaliação, então o número
reportado como desempenho de teste era desempenho no conjunto de treino. A
lógica de partição real vivia apenas inline no notebook de modelagem, o que
tornava impossível garantir que baselines e GNNs vissem a mesma divisão — e
comparar as duas coisas é o objetivo do trabalho.

A partição é feita por **transição**, nunca por linha. Ver
docs/02-metodologia.md, seção 6.1, e docs/03-decisoes.md, D-08 e D-11.

Com os nove snapshots anuais de 01/2017 a 01/2025:

    treino      2018 2019 2020 2021 2022
    validação   2023 2024
    teste       2025

Cada rótulo é o período de destino da transição.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.changes import Transicao, transicoes

# Snapshots tirados sob a pandemia de covid-19. A aquisição de equipamentos
# nesse período não é amostra do mesmo processo que a dos demais: respiradores e
# leitos de UTI foram adquiridos em regime de exceção.
# Ver docs/02-metodologia.md, seção 4.1.
SNAPSHOTS_PANDEMIA = ("202001", "202101")


class ErroParticao(ValueError):
    """Partição temporal impossível ou com vazamento."""


@dataclass(frozen=True)
class ParticaoTemporal:
    """
    Uma divisão treino / validação / teste sobre transições entre snapshots.

    Imutável de propósito: a partição é fixada uma vez e as trilhas a recebem
    pronta, para que nenhuma delas possa redividir por conta própria.
    """

    treino: tuple[Transicao, ...]
    validacao: tuple[Transicao, ...]
    teste: tuple[Transicao, ...]

    @property
    def conjuntos(self) -> dict[str, tuple[Transicao, ...]]:
        return {"treino": self.treino, "validacao": self.validacao, "teste": self.teste}

    @property
    def fim_do_treino(self) -> str:
        """
        Último snapshot que o treino pode enxergar.

        Qualquer feature agregada tem que ser calculada até aqui. Ler adiante
        deste ponto é vazamento, mesmo quando o rótulo vem do conjunto certo.
        """
        return self.treino[-1].destino

    def conjunto_de(self, transicao: Transicao) -> str | None:
        for nome, grupo in self.conjuntos.items():
            if transicao in grupo:
                return nome
        return None

    def resumo(self) -> str:
        linhas = [f"{'conjunto':10} {'n':>3}  transições (por período de destino)"]
        for nome, grupo in self.conjuntos.items():
            destinos = " ".join(t.destino for t in grupo)
            linhas.append(f"{nome:10} {len(grupo):>3}  {destinos}")
        return "\n".join(linhas)


def particionar(
    periodos: list[str],
    n_validacao: int = 2,
    n_teste: int = 1,
    excluir_pandemia: bool = False,
) -> ParticaoTemporal:
    """
    Divide as transições cronologicamente: o passado treina, o futuro testa.

    As `n_teste` transições mais recentes vão para teste, as `n_validacao`
    anteriores para validação, e o restante para treino. Nunca há sorteio: a
    tarefa é prever o período seguinte, então qualquer divisão aleatória
    permitiria treinar no futuro e avaliar no passado.

    Com `excluir_pandemia=True`, descarta-se toda transição que **toque** um
    snapshot de pandemia, em qualquer das duas pontas. Excluir apenas pelo
    destino deixaria passar 202101 -> 202201, que mede a variação a partir de uma
    base já distorcida pelo choque — o que anularia o propósito da variante.
    É o experimento de controle que a metodologia exige para verificar se a
    conclusão sobrevive à covid-19.
    """
    todas = transicoes(periodos)
    if excluir_pandemia:
        todas = [
            t
            for t in todas
            if t.origem not in SNAPSHOTS_PANDEMIA and t.destino not in SNAPSHOTS_PANDEMIA
        ]

    minimo = n_validacao + n_teste + 1
    if len(todas) < minimo:
        raise ErroParticao(
            f"partição pede ao menos {minimo} transições "
            f"({n_teste} de teste, {n_validacao} de validação e 1 de treino), "
            f"mas {len(periodos)} snapshots produzem {len(todas)}"
            + (" após excluir as transições de pandemia" if excluir_pandemia else "")
            + f". Snapshots: {periodos}"
        )
    if n_teste < 1 or n_validacao < 1:
        raise ErroParticao(
            f"validação e teste precisam de ao menos uma transição cada; "
            f"recebido n_validacao={n_validacao}, n_teste={n_teste}"
        )

    corte_teste = len(todas) - n_teste
    corte_validacao = corte_teste - n_validacao

    particao = ParticaoTemporal(
        treino=tuple(todas[:corte_validacao]),
        validacao=tuple(todas[corte_validacao:corte_teste]),
        teste=tuple(todas[corte_teste:]),
    )
    verificar_sem_vazamento(particao)
    return particao


def verificar_sem_vazamento(particao: ParticaoTemporal) -> None:
    """
    Recusa qualquer partição que permita treinar no que será avaliado.

    Três coisas são checadas, e todas as três já falharam em alguma versão do
    projeto: sobreposição entre conjuntos, conjunto vazio, e ordem cronológica
    invertida entre treino, validação e teste.
    """
    for nome, grupo in particao.conjuntos.items():
        if not grupo:
            raise ErroParticao(f"conjunto {nome!r} está vazio")
        if len(set(grupo)) != len(grupo):
            raise ErroParticao(f"conjunto {nome!r} repete transições")

    nomes = list(particao.conjuntos)
    for i, a in enumerate(nomes):
        for b in nomes[i + 1 :]:
            comum = set(particao.conjuntos[a]) & set(particao.conjuntos[b])
            if comum:
                raise ErroParticao(
                    f"transições em {a!r} e {b!r} ao mesmo tempo: "
                    f"{sorted(str(t) for t in comum)}"
                )

    ordem = [
        (nome, max(t.destino for t in grupo), min(t.destino for t in grupo))
        for nome, grupo in particao.conjuntos.items()
    ]
    for (nome_a, ultimo_a, _), (nome_b, _, primeiro_b) in zip(ordem, ordem[1:]):
        if ultimo_a >= primeiro_b:
            raise ErroParticao(
                f"{nome_a!r} termina em {ultimo_a} e {nome_b!r} começa em "
                f"{primeiro_b}: o passado precisa vir estritamente antes do futuro"
            )


def verificar_features_sem_vazamento(
    particao: ParticaoTemporal, periodos_usados: "list[str] | set[str]"
) -> None:
    """
    Confere que nenhuma feature de treino leu além do fim da janela de treino.

    A partição por transição não basta: um agregado calculado sobre todos os
    snapshots contamina o treino com informação do futuro mesmo que os rótulos
    estejam corretamente divididos. Este é o vazamento mais fácil de cometer
    sem perceber, e o mais difícil de detectar olhando a métrica.
    """
    limite = particao.fim_do_treino
    adiante = sorted(p for p in periodos_usados if p > limite)
    if adiante:
        raise ErroParticao(
            f"features de treino usaram os snapshots {adiante}, posteriores ao "
            f"fim da janela de treino ({limite}). Recalcule usando apenas "
            f"snapshots até {limite}."
        )
