"""Camada de regras: todas as contas do BagreStats moram aqui.

Nenhuma funcao daqui sabe o que e HTML ou navegador. Isso permite testar as
contas isoladamente, e e o que vai permitir servir um app de celular depois
sem reescrever nada.

ponytail: as funcoes carregam as participacoes todas para a memoria e contam
em Python, em vez de somar no banco com SQL. Com uma partida por semana isso
sao dezenas de linhas por ano e o ganho de legibilidade vale mais. Teto: se um
dia passar de ~50 mil participacoes, virar agregacao em SQL.
"""
from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Cor, Jogador, Participacao, Partida

VITORIA, EMPATE, DERROTA = "V", "E", "D"

PONTOS = {VITORIA: 3, EMPATE: 1, DERROTA: 0}


def _resultado(partida: Partida, cor_id: int) -> str:
    """O que aquela cor tirou naquela partida."""
    if partida.cor_vencedora_id is None:
        return EMPATE
    return VITORIA if partida.cor_vencedora_id == cor_id else DERROTA


def _participacoes(sessao: Session) -> list[Participacao]:
    return list(
        sessao.scalars(
            select(Participacao).options(
                joinedload(Participacao.partida),
                joinedload(Participacao.jogador),
                joinedload(Participacao.cor),
            )
        )
    )


@dataclass
class Linha:
    """Uma linha da classificacao."""

    jogador: Jogador
    vitorias: int = 0
    empates: int = 0
    derrotas: int = 0

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


def classificacao(sessao: Session) -> list[Linha]:
    linhas: dict[int, Linha] = {}
    for p in _participacoes(sessao):
        linha = linhas.setdefault(p.jogador_id, Linha(jogador=p.jogador))
        resultado = _resultado(p.partida, p.cor_id)
        if resultado == VITORIA:
            linha.vitorias += 1
        elif resultado == EMPATE:
            linha.empates += 1
        else:
            linha.derrotas += 1
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
    historico: list[tuple[Partida, Cor, str]] = field(default_factory=list)


def perfil(sessao: Session, jogador_id: int) -> Perfil | None:
    todas = _participacoes(sessao)
    minhas = [p for p in todas if p.jogador_id == jogador_id]
    if not minhas:
        jogador = sessao.get(Jogador, jogador_id)
        return Perfil(jogador=jogador, linha=Linha(jogador=jogador)) if jogador else None

    jogador = minhas[0].jogador
    por_partida = defaultdict(list)
    for p in todas:
        por_partida[p.partida_id].append(p)

    linha = Linha(jogador=jogador)
    duplas: dict[int, Parceria] = {}
    fregueses: dict[int, Parceria] = {}
    historico = []

    for minha in sorted(minhas, key=lambda p: p.partida.data):
        resultado = _resultado(minha.partida, minha.cor_id)
        if resultado == VITORIA:
            linha.vitorias += 1
        elif resultado == EMPATE:
            linha.empates += 1
        else:
            linha.derrotas += 1
        historico.append((minha.partida, minha.cor, resultado))

        for outra in por_partida[minha.partida_id]:
            if outra.jogador_id == jogador_id:
                continue
            # Mesmo time = dupla. Time diferente = adversario.
            alvo = duplas if outra.cor_id == minha.cor_id else fregueses
            par = alvo.setdefault(outra.jogador_id, Parceria(jogador=outra.jogador))
            par.jogos += 1
            if resultado == VITORIA:
                par.vitorias += 1

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
    partidas = sessao.scalars(
        select(Partida).options(joinedload(Partida.participacoes).joinedload(Participacao.cor))
    ).unique()

    resultado: dict[tuple[str, str], Confronto] = {}
    for partida in partidas:
        cores = {p.cor.nome for p in partida.participacoes}
        if len(cores) != 2:
            continue  # partida sem dois times nao entra no confronto
        # "preto x branco" e "branco x preto" sao o mesmo confronto: ordenamos
        # o par pelo nome para os dois cairem na mesma chave.
        a, b = sorted(cores)
        conf = resultado.setdefault((a, b), Confronto(cor_a=a, cor_b=b))
        if partida.cor_vencedora is None:
            conf.empates += 1
        elif partida.cor_vencedora.nome == a:
            conf.vitorias_a += 1
        else:
            conf.vitorias_b += 1
    return sorted(resultado.values(), key=lambda c: c.jogos, reverse=True)
