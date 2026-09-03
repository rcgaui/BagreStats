"""Testes da tela de lancar quinta: as validacoes que impedem lixo no banco."""
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_session
from app.main import app
from app.models import Cor, Jogador, Partida


@pytest.fixture
def cliente():
    """Sobe a aplicacao apontando para um banco de mentira, na memoria."""
    # StaticPool: banco em memoria cria um banco novo A CADA CONEXAO, e o
    # TestClient roda em outra thread. Sem isto, a aplicacao enxergaria um
    # banco vazio diferente do que o teste preparou.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Fabrica = sessionmaker(bind=engine, expire_on_commit=False)

    with Fabrica() as s:
        s.add_all([Cor(nome="PRETO", codigo="#000"), Cor(nome="BRANCO", codigo="#fff")])
        s.add_all([Jogador(apelido=n) for n in ["Ana", "Bruno", "Carla", "Davi"]])
        s.commit()

    def sessao_de_teste():
        with Fabrica() as s:
            yield s

    app.dependency_overrides[get_session] = sessao_de_teste
    yield TestClient(app, follow_redirects=False), Fabrica
    app.dependency_overrides.clear()


def _quinta(**mudancas):
    base = {
        "data": "2026-09-03",
        "cor_a": 1,
        "cor_b": 2,
        "vencedor": "A",
        "time_a": [1, 2],
        "time_b": [3, 4],
    }
    return {**base, **mudancas}


def test_salva_a_quinta_e_volta_para_a_classificacao(cliente):
    c, Fabrica = cliente
    r = c.post("/lancar", data=_quinta())
    assert r.status_code == 303 and r.headers["location"] == "/"
    with Fabrica() as s:
        partida = s.query(Partida).one()
        assert partida.data == date(2026, 9, 3)
        assert len(partida.participacoes) == 4
        assert not partida.empate


def test_empate_grava_vencedor_vazio(cliente):
    c, Fabrica = cliente
    c.post("/lancar", data=_quinta(vencedor="EMPATE"))
    with Fabrica() as s:
        assert s.query(Partida).one().empate


def test_recusa_jogador_escalado_nos_dois_times(cliente):
    c, Fabrica = cliente
    r = c.post("/lancar", data=_quinta(time_a=[1, 2], time_b=[2, 3]))
    assert "erro" in r.headers["location"]
    with Fabrica() as s:
        assert s.query(Partida).count() == 0


def test_recusa_times_com_a_mesma_cor(cliente):
    c, Fabrica = cliente
    r = c.post("/lancar", data=_quinta(cor_b=1))
    assert "mesma+cor" in r.headers["location"]


def test_recusa_time_vazio(cliente):
    c, Fabrica = cliente
    r = c.post("/lancar", data=_quinta(time_b=[]))
    assert "erro" in r.headers["location"]


def test_recusa_duas_partidas_na_mesma_data(cliente):
    c, Fabrica = cliente
    c.post("/lancar", data=_quinta())
    r = c.post("/lancar", data=_quinta(time_a=[3], time_b=[4]))
    assert "Ja+existe" in r.headers["location"]
    with Fabrica() as s:
        assert s.query(Partida).count() == 1
