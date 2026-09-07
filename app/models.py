"""As tabelas do BagreStats.

    jogador       quem joga (id fixo, apelido editavel)
    cor           as cores dos coletes (preto, branco, ...)
    pelada        uma noite. Uma por data.
    participacao  quem jogou de qual cor NAQUELA NOITE
    partida       um jogo dentro da noite: cor A x cor B, e quem venceu

A separacao entre pelada e partida existe porque uma noite pode ter tres times
e varios jogos. Assim a escalacao e registrada uma vez por noite e cada jogo
custa so escolher as duas cores e o vencedor - se fosse por jogo, seria
preciso reescalar todo mundo a cada partida, que e o atrito que mata o habito
de registrar. Noite com dois times e apenas uma pelada com um jogo dentro: nao
existe caso especial.
"""
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

VITORIA, EMPATE, DERROTA = "V", "E", "D"

# Formacao fixa. Ordem = ordem de preenchimento automatico ao escalar.
POSICOES = [
    ("GOL", "Goleiro"),
    ("ZAG", "Zagueiro"),
    ("LAT_E", "Lateral esquerdo"),
    ("LAT_D", "Lateral direito"),
    ("MEI_E", "Meio-campo esquerdo"),
    ("MEI_D", "Meio-campo direito"),
    ("ATA", "Atacante"),
]


class Jogador(Base):
    __tablename__ = "jogador"

    id: Mapped[int] = mapped_column(primary_key=True)
    # O apelido pode ser editado a vontade: o historico se liga pelo id,
    # nunca pelo texto. Renomear "Digo" para "Rodrigo" nao perde nada.
    apelido: Mapped[str] = mapped_column(String(50), unique=True)

    participacoes: Mapped[list["Participacao"]] = relationship(back_populates="jogador")

    def __repr__(self) -> str:
        return f"<Jogador {self.apelido}>"


class Cor(Base):
    __tablename__ = "cor"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(30), unique=True)
    # Codigo hexadecimal, para a tela pintar a bolinha de verdade.
    codigo: Mapped[str] = mapped_column(String(7), default="#888888")

    def __repr__(self) -> str:
        return f"<Cor {self.nome}>"


class Pelada(Base):
    """Uma noite de pelada."""

    __tablename__ = "pelada"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Uma pelada por dia. O banco recusa duas na mesma data.
    data: Mapped[date] = mapped_column(Date, unique=True)

    participacoes: Mapped[list["Participacao"]] = relationship(
        back_populates="pelada", cascade="all, delete-orphan"
    )
    partidas: Mapped[list["Partida"]] = relationship(
        back_populates="pelada", cascade="all, delete-orphan",
        order_by="Partida.ordem",
    )

    def __repr__(self) -> str:
        return f"<Pelada {self.data}>"


class Participacao(Base):
    """Quem jogou de qual cor naquela noite. Os times sao fixos a noite toda."""

    __tablename__ = "participacao"

    id: Mapped[int] = mapped_column(primary_key=True)
    pelada_id: Mapped[int] = mapped_column(ForeignKey("pelada.id", ondelete="CASCADE"))
    jogador_id: Mapped[int] = mapped_column(ForeignKey("jogador.id"))
    cor_id: Mapped[int] = mapped_column(ForeignKey("cor.id"))
    # Vaga ocupada (GOL, ZAG, ... ou RES). Nula nas peladas antigas.
    posicao: Mapped[str | None] = mapped_column(String(10))

    pelada: Mapped["Pelada"] = relationship(back_populates="participacoes")
    jogador: Mapped["Jogador"] = relationship(back_populates="participacoes")
    cor: Mapped["Cor"] = relationship()

    __table_args__ = (
        # Um jogador so pode estar num time por noite. Regra DO BANCO: nao
        # depende de ninguem lembrar de conferir.
        UniqueConstraint("pelada_id", "jogador_id", name="uq_um_time_por_jogador"),
    )


class Partida(Base):
    """Um jogo dentro da noite."""

    __tablename__ = "partida"

    id: Mapped[int] = mapped_column(primary_key=True)
    pelada_id: Mapped[int] = mapped_column(ForeignKey("pelada.id", ondelete="CASCADE"))
    # Ordem em que os jogos aconteceram na noite.
    ordem: Mapped[int] = mapped_column(Integer, default=1)
    cor_a_id: Mapped[int] = mapped_column(ForeignKey("cor.id"))
    cor_b_id: Mapped[int] = mapped_column(ForeignKey("cor.id"))
    # Vazio (None) significa EMPATE. E por isso que nao existe coluna de empate.
    cor_vencedora_id: Mapped[int | None] = mapped_column(ForeignKey("cor.id"))

    pelada: Mapped["Pelada"] = relationship(back_populates="partidas")
    cor_a: Mapped["Cor"] = relationship(foreign_keys=[cor_a_id])
    cor_b: Mapped["Cor"] = relationship(foreign_keys=[cor_b_id])
    cor_vencedora: Mapped["Cor | None"] = relationship(foreign_keys=[cor_vencedora_id])

    @property
    def empate(self) -> bool:
        return self.cor_vencedora_id is None

    def cores(self) -> tuple[int, int]:
        return (self.cor_a_id, self.cor_b_id)

    def resultado_de(self, cor_id: int) -> str | None:
        """O que aquela cor tirou neste jogo. None se ela nao jogou."""
        if cor_id not in self.cores():
            return None
        if self.cor_vencedora_id is None:
            return EMPATE
        return VITORIA if self.cor_vencedora_id == cor_id else DERROTA

    __table_args__ = (
        UniqueConstraint("pelada_id", "ordem", name="uq_ordem_do_jogo"),
    )

    def __repr__(self) -> str:
        return f"<Partida {self.pelada_id}#{self.ordem}>"

