"""Camada de regras: todas as contas do BagreStats moram aqui.

Nenhuma funcao daqui sabe o que e HTML ou navegador. Isso permite testar as
contas isoladamente, e e o que vai permitir servir um app de celular depois
sem reescrever nada.

A unidade da estatistica e o JOGO, nao a noite: numa noite de tres times cada
um joga um numero diferente de partidas, e contar por noite jogaria fora
justamente essa diferenca. Quem sentou nao pontua no jogo que nao disputou.

ponytail: as contas percorrem tudo em memoria em vez de agregar em SQL. Sao
algumas dezenas de jogos por ano e a legibilidade vale mais. Teto: se passar
de ~50 mil participacoes, virar agregacao no banco.
"""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import (DERROTA, EMPATE, VITORIA, Cor, Jogador, Participacao,
                        Partida, Pelada)

PONTOS = {VITORIA: 3, EMPATE: 1, DERROTA: 0}


def _peladas(sessao: Session) -> list[Pelada]:
    """As noites com escalacao e jogos ja carregados."""
    return list(
        sessao.scalars(
            select(Pelada)
            .options(
                joinedload(Pelada.participacoes).joinedload(Participacao.jogador),
                joinedload(Pelada.participacoes).joinedload(Participacao.cor),
                joinedload(Pelada.partidas),
            )
            .order_by(Pelada.data)
        ).unique()
    )


def _por_cor(pelada: Pelada) -> dict[int, list[Participacao]]:
    """Quem estava em cada cor naquela noite."""
    times: dict[int, list[Participacao]] = defaultdict(list)
    for p in pelada.participacoes:
        times[p.cor_id].append(p)
    return times


@dataclass
class Linha:
    """Uma linha da classificacao."""

    jogador: Jogador
    vitorias: int = 0
    empates: int = 0
    derrotas: int = 0
    peladas: int = 0

    @property
    def jogos(self) -> int:
        return self.vitorias + self.empates + self.derrotas

    @property
    def pontos(self) -> int:
        return self.vitorias * 3 + self.empates

    @property
    def aproveitamento(self) -> float:
        """Percentual dos pontos possiveis, igual a tabela do Brasileirao."""
        if not self.jogos:
            return 0.0
        return 100 * self.pontos / (3 * self.jogos)

    def marcar(self, resultado: str) -> None:
        if resultado == VITORIA:
            self.vitorias += 1
        elif resultado == EMPATE:
            self.empates += 1
        else:
            self.derrotas += 1


def classificacao(sessao: Session) -> list[Linha]:
    linhas: dict[int, Linha] = {}
    for pelada in _peladas(sessao):
        times = _por_cor(pelada)
        for p in pelada.participacoes:
            linhas.setdefault(p.jogador_id, Linha(jogador=p.jogador)).peladas += 1
        for jogo in pelada.partidas:
            for cor_id in jogo.cores():
                resultado = jogo.resultado_de(cor_id)
                for p in times.get(cor_id, []):
                    linhas[p.jogador_id].marcar(resultado)
    return sorted(
        linhas.values(),
        key=lambda l: (l.pontos, l.aproveitamento, l.vitorias),
        reverse=True,
    )


@dataclass
class Parceria:
    """Estatistica de dupla (mesmo time) ou de confronto (times opostos)."""

    jogador: Jogador
    jogos: int = 0
    vitorias: int = 0

    @property
    def aproveitamento(self) -> float:
        return 100 * self.vitorias / self.jogos if self.jogos else 0.0


@dataclass
class Perfil:
    jogador: Jogador
    linha: Linha
    duplas: list[Parceria] = field(default_factory=list)
    fregueses: list[Parceria] = field(default_factory=list)
    sem_perder: int = 0
    # Um item por JOGO disputado: a noite, a cor vestida e o resultado.
    historico: list[tuple[Pelada, Cor, str]] = field(default_factory=list)
    # Aproveitamento acumulado apos cada jogo, na ordem em que aconteceram.
    evolucao: list[tuple[date, float]] = field(default_factory=list)


def perfil(sessao: Session, jogador_id: int) -> Perfil | None:
    jogador = sessao.get(Jogador, jogador_id)
    if jogador is None:
        return None

    linha = Linha(jogador=jogador)
    duplas: dict[int, Parceria] = {}
    fregueses: dict[int, Parceria] = {}
    historico: list[tuple[Pelada, Cor, str]] = []

    for pelada in _peladas(sessao):
        minha = next(
            (p for p in pelada.participacoes if p.jogador_id == jogador_id), None
        )
        if minha is None:
            continue
        linha.peladas += 1
        times = _por_cor(pelada)

        for jogo in pelada.partidas:
            resultado = jogo.resultado_de(minha.cor_id)
            if resultado is None:
                continue  # o time dele sentou neste jogo
            linha.marcar(resultado)
            historico.append((pelada, minha.cor, resultado))

            cor_adversaria = next(c for c in jogo.cores() if c != minha.cor_id)
            for alvo, participantes in (
                (duplas, times.get(minha.cor_id, [])),
                (fregueses, times.get(cor_adversaria, [])),
            ):
                for outro in participantes:
                    if outro.jogador_id == jogador_id:
                        continue
                    par = alvo.setdefault(
                        outro.jogador_id, Parceria(jogador=outro.jogador)
                    )
                    par.jogos += 1
                    if resultado == VITORIA:
                        par.vitorias += 1

    # Evolucao: refaz a conta jogo a jogo, guardando o acumulado de cada ponto
    # no tempo. O historico ja esta em ordem cronologica aqui.
    evolucao, corrida = [], Linha(jogador=jogador)
    for pelada, _, resultado in historico:
        corrida.marcar(resultado)
        evolucao.append((pelada.data, corrida.aproveitamento))

    # Sequencia sem perder: conta de tras para frente ate a primeira derrota.
    sem_perder = 0
    for _, _, resultado in reversed(historico):
        if resultado == DERROTA:
            break
        sem_perder += 1

    ordenar = lambda d: sorted(  # noqa: E731
        d.values(), key=lambda x: (x.aproveitamento, x.jogos), reverse=True
    )
    return Perfil(
        jogador=jogador,
        linha=linha,
        duplas=ordenar(duplas),
        fregueses=ordenar(fregueses),
        sem_perder=sem_perder,
        historico=list(reversed(historico)),
        evolucao=evolucao,
    )


@dataclass
class Confronto:
    """Historico entre duas cores. Sem nenhum sentido esportivo, e a graca e essa."""

    cor_a: str
    cor_b: str
    vitorias_a: int = 0
    vitorias_b: int = 0
    empates: int = 0

    @property
    def jogos(self) -> int:
        return self.vitorias_a + self.vitorias_b + self.empates


def confrontos(sessao: Session) -> list[Confronto]:
    jogos = sessao.scalars(
        select(Partida).options(
            joinedload(Partida.cor_a),
            joinedload(Partida.cor_b),
            joinedload(Partida.cor_vencedora),
        )
    ).unique()

    resultado: dict[tuple[str, str], Confronto] = {}
    for jogo in jogos:
        # "preto x branco" e "branco x preto" sao o mesmo confronto: ordenamos
        # o par pelo nome para os dois cairem na mesma chave.
        a, b = sorted([jogo.cor_a.nome, jogo.cor_b.nome])
        conf = resultado.setdefault((a, b), Confronto(cor_a=a, cor_b=b))
        if jogo.cor_vencedora is None:
            conf.empates += 1
        elif jogo.cor_vencedora.nome == a:
            conf.vitorias_a += 1
        else:
            conf.vitorias_b += 1
    return sorted(resultado.values(), key=lambda c: c.jogos, reverse=True)
