"""Conexao com o banco. Camada de dados: ninguem mais no projeto abre conexao."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL)


# O SQLite vem de fabrica IGNORANDO chaves estrangeiras. Sem esta linha ele
# aceitaria uma participacao apontando para um jogador que nao existe.
@event.listens_for(engine, "connect")
def _ativa_chaves_estrangeiras(conexao, _):
    if DATABASE_URL.startswith("sqlite"):
        cursor = conexao.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


Session = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """Classe mae de todas as tabelas."""


def get_session():
    """Abre uma sessao por requisicao e fecha no fim, sempre."""
    with Session() as sessao:
        yield sessao
