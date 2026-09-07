"""Editar uma pelada ja registrada: trocar jogadores, resultado ou data."""
import json
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_session
from app.main import app
from app.models import Cor, Jogador, Partida, Pelada
from tests.test_lancamento import _noite, _time


@pytest.fixture
def cliente():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Fabrica = sessionmaker(bind=engine, expire_on_commit=False)
    with Fabrica() as s:
        s.add_all([Cor(nome=n, codigo="#000") for n in ("PRETO", "BRANCO", "VERMELHO")])
        s.add_all([Jogador(apelido=f"J{i:02d}") for i in range(1, 22)])
        s.commit()

    def sessao_de_teste():
        with Fabrica() as s:
            yield s

    app.dependency_overrides[get_session] = sessao_de_teste
    yield TestClient(app, follow_redirects=False), Fabrica
    app.dependency_overrides.clear()


@pytest.fixture
def pelada_salva(cliente):
    c, Fabrica = cliente
    c.post("/lancar", data=_noite())
    with Fabrica() as s:
        return c, Fabrica, s.query(Pelada).one().id


def test_a_tela_de_edicao_abre_com_a_pelada(pelada_salva):
    c, _, pid = pelada_salva
    r = c.get(f"/pelada/{pid}/editar")
    assert r.status_code == 200
    # O estado inicial da tela vem da pelada, nao de um formulario em branco.
    assert '"cor_id": 1' in r.text and f'action="/pelada/{pid}"' in r.text


def test_troca_um_jogador_do_elenco(pelada_salva):
    c, Fabrica, pid = pelada_salva
    time_a = _time(1, 1)
    time_a["jogadores"][0] = {"id": 15, "posicao": "GOL"}  # J15 no lugar de J01
    r = c.post(f"/pelada/{pid}", data=_noite(times=[time_a, _time(2, 8)]))
    assert r.headers["location"] == f"/pelada/{pid}"
    with Fabrica() as s:
        pelada = s.query(Pelada).one()
        ids = {p.jogador_id for p in pelada.participacoes}
        assert 15 in ids and 1 not in ids
        assert len(pelada.participacoes) == 14  # nao duplicou


def test_troca_o_resultado_de_um_jogo(pelada_salva):
    c, Fabrica, pid = pelada_salva
    c.post(f"/pelada/{pid}",
           data=_noite(jogos=[{"cor_a": 1, "cor_b": 2, "vencedor": 2}]))
    with Fabrica() as s:
        assert s.query(Partida).one().cor_vencedora_id == 2


def test_acrescenta_jogos_a_uma_noite_ja_registrada(pelada_salva):
    c, Fabrica, pid = pelada_salva
    c.post(f"/pelada/{pid}", data=_noite(jogos=[
        {"cor_a": 1, "cor_b": 2, "vencedor": 1},
        {"cor_a": 1, "cor_b": 2, "vencedor": None},
        {"cor_a": 1, "cor_b": 2, "vencedor": 2},
    ]))
    with Fabrica() as s:
        jogos = s.query(Pelada).one().partidas
        assert [j.ordem for j in jogos] == [1, 2, 3]
        assert [j.cor_vencedora_id for j in jogos] == [1, None, 2]


def test_acrescenta_um_time_a_noite(pelada_salva):
    c, Fabrica, pid = pelada_salva
    c.post(f"/pelada/{pid}", data=_noite(
        times=[_time(1, 1), _time(2, 8), _time(3, 15)],
        jogos=[{"cor_a": 1, "cor_b": 3, "vencedor": 3}],
    ))
    with Fabrica() as s:
        assert len(s.query(Pelada).one().participacoes) == 21


def test_corrige_a_data_da_pelada(pelada_salva):
    c, Fabrica, pid = pelada_salva
    ontem = (date.today() - timedelta(days=1)).isoformat()
    c.post(f"/pelada/{pid}", data=_noite(data=ontem))
    with Fabrica() as s:
        assert s.query(Pelada).one().data.isoformat() == ontem


def test_manter_a_mesma_data_nao_e_conflito(pelada_salva):
    """A pelada nao pode colidir consigo mesma na checagem de data repetida."""
    c, _, pid = pelada_salva
    r = c.post(f"/pelada/{pid}", data=_noite())
    assert r.headers["location"] == f"/pelada/{pid}"


def test_recusa_data_ja_usada_por_outra_pelada(pelada_salva):
    c, Fabrica, pid = pelada_salva
    ontem = (date.today() - timedelta(days=1)).isoformat()
    c.post("/lancar", data=_noite(data=ontem, times=[_time(1, 1), _time(2, 8)]))
    r = c.post(f"/pelada/{pid}", data=_noite(data=ontem))
    assert "Ja+existe+pelada" in r.headers["location"]
    with Fabrica() as s:
        assert s.query(Pelada).filter_by(id=pid).one().data == date.today()


def test_as_regras_de_lancamento_valem_na_edicao(pelada_salva):
    c, Fabrica, pid = pelada_salva
    r = c.post(f"/pelada/{pid}",
               data=_noite(times=[_time(1, 1), _time(2, 8, titulares=5)]))
    assert "titulares" in r.headers["location"]
    with Fabrica() as s:  # a pelada original fica intacta
        assert len(s.query(Pelada).one().participacoes) == 14


def test_pelada_inexistente_volta_para_a_lista(cliente):
    c, _ = cliente
    assert c.get("/pelada/999/editar").headers["location"] == "/peladas"
    assert c.post("/pelada/999", data=_noite()).headers["location"] == "/peladas"
