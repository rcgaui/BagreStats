"""As quatro tabelas do BagreStats.

    jogador       quem joga (id fixo, apelido editavel)
    cor           as cores dos times (preto, branco, ...)
    partida       uma pelada (a data e livre, nao so quinta)
    participacao  liga jogador + partida + cor ("fulano jogou de preto no dia 27")
"""
from datetime import date

from sqlalchemy import Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


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


class Partida(Base):
    __tablename__ = "partida"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Uma pelada por dia. O banco recusa duas partidas na mesma data.
    data: Mapped[date] = mapped_column(Date, unique=True)
    # Vazio (None) significa EMPATE. E por isso que nao existe coluna de empate.
    cor_vencedora_id: Mapped[int | None] = mapped_column(ForeignKey("cor.id"))

    cor_vencedora: Mapped["Cor | None"] = relationship()
    participacoes: Mapped[list["Participacao"]] = relationship(
        back_populates="partida", cascade="all, delete-orphan"
    )

    @property
    def empate(self) -> bool:
        return self.cor_vencedora_id is None

    def __repr__(self) -> str:
        return f"<Partida {self.data}>"


class Participacao(Base):
    __tablename__ = "participacao"

    id: Mapped[int] = mapped_column(primary_key=True)
    partida_id: Mapped[int] = mapped_column(ForeignKey("partida.id", ondelete="CASCADE"))
    jogador_id: Mapped[int] = mapped_column(ForeignKey("jogador.id"))
    cor_id: Mapped[int] = mapped_column(ForeignKey("cor.id"))

    partida: Mapped["Partida"] = relationship(back_populates="participacoes")
    jogador: Mapped["Jogador"] = relationship(back_populates="participacoes")
    cor: Mapped["Cor"] = relationship()

    __table_args__ = (
        # A regra prometida: o mesmo jogador nao pode aparecer duas vezes na
        # mesma partida, entao nao tem como escala-lo nos dois times.
        # Isto e uma regra DO BANCO: nao depende de ninguem lembrar de conferir.
        UniqueConstraint("partida_id", "jogador_id", name="uq_um_time_por_jogador"),
    )
