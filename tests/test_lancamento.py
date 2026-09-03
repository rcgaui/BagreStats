"""Testes da tela de lancar pelada: as validacoes que impedem lixo no banco."""
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


def _pelada(**mudancas):
    # posicoes_a/posicoes_b sao paralelas a time_a/time_b: posicoes_a[i] eh a
    # vaga de time_a[i]. A tela sempre manda os dois pares juntos.
    base = {
        "data": "2026-09-03",
        "cor_a": 1,
        "cor_b": 2,
        "vencedor": "A",
        "time_a": [1, 2],
        "posicoes_a": ["GOL", "ZAG"],
        "time_b": [3, 4],
        "posicoes_b": ["GOL", "RES"],
    }
    return {**base, **mudancas}


def test_salva_a_pelada_e_volta_para_a_classificacao(cliente):
    c, Fabrica = cliente
    r = c.post("/lancar", data=_pelada())
    assert r.status_code == 303 and r.headers["location"] == "/"
    with Fabrica() as s:
        partida = s.query(Partida).one()
        assert partida.data == date(2026, 9, 3)
        assert len(partida.participacoes) == 4
        assert not partida.empate


def test_grava_a_posicao_de_cada_jogador(cliente):
    c, Fabrica = cliente
    c.post("/lancar", data=_pelada())
    with Fabrica() as s:
        posicoes = {p.jogador_id: p.posicao for p in s.query(Partida).one().participacoes}
        assert posicoes == {1: "GOL", 2: "ZAG", 3: "GOL", 4: "RES"}


def test_jogador_sem_posicao_correspondente_fica_de_fora(cliente):
    # A tela sempre manda os dois pares do mesmo tamanho; se um dia nao mandar
    # (bug de JS), o jogador sem par so nao entra - nao quebra o lancamento
    # inteiro nem grava posicao inventada.
    c, Fabrica = cliente
    c.post("/lancar", data=_pelada(time_a=[1, 2], posicoes_a=["GOL"]))
    with Fabrica() as s:
        ids = {p.jogador_id for p in s.query(Partida).one().participacoes if p.cor_id == 1}
        assert ids == {1}


def test_empate_grava_vencedor_vazio(cliente):
    c, Fabrica = cliente
    c.post("/lancar", data=_pelada(vencedor="EMPATE"))
    with Fabrica() as s:
        assert s.query(Partida).one().empate


def test_recusa_jogador_escalado_nos_dois_times(cliente):
    c, Fabrica = cliente
    r = c.post("/lancar", data=_pelada(time_a=[1, 2], time_b=[2, 3]))
    assert "erro" in r.headers["location"]
    with Fabrica() as s:
        assert s.query(Partida).count() == 0


def test_recusa_times_com_a_mesma_cor(cliente):
    c, Fabrica = cliente
    r = c.post("/lancar", data=_pelada(cor_b=1))
    assert "mesma+cor" in r.headers["location"]


def test_recusa_time_vazio(cliente):
    c, Fabrica = cliente
    r = c.post("/lancar", data=_pelada(time_b=[]))
    assert "erro" in r.headers["location"]


def test_recusa_duas_partidas_na_mesma_data(cliente):
    c, Fabrica = cliente
    c.post("/lancar", data=_pelada())
    r = c.post("/lancar", data=_pelada(time_a=[3], time_b=[4]))
    assert "Ja+existe" in r.headers["location"]
    with Fabrica() as s:
        assert s.query(Partida).count() == 1
