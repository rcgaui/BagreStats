"""Testes da tela de lancar pelada: as validacoes que impedem lixo no banco."""
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

CORES = ["PRETO", "BRANCO", "VERMELHO"]


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
        s.add_all([Cor(nome=n, codigo="#000") for n in CORES])
        # 21 jogadores: o suficiente para tres times de sete.
        s.add_all([Jogador(apelido=f"J{i:02d}") for i in range(1, 22)])
        s.commit()

    def sessao_de_teste():
        with Fabrica() as s:
            yield s

    app.dependency_overrides[get_session] = sessao_de_teste
    yield TestClient(app, follow_redirects=False), Fabrica
    app.dependency_overrides.clear()


POSICOES = ["GOL", "ZAG", "LAT_E", "LAT_D", "MEI_E", "MEI_D", "ATA"]


def _time(cor_id, primeiro_jogador, titulares=7, reservas=0):
    jogadores = [
        {"id": primeiro_jogador + i, "posicao": POSICOES[i]} for i in range(titulares)
    ]
    jogadores += [
        {"id": primeiro_jogador + titulares + i, "posicao": "RES"}
        for i in range(reservas)
    ]
    return {"cor_id": cor_id, "jogadores": jogadores}


def _noite(**mudancas):
    base = {
        "data": date.today().isoformat(),
        "times": [_time(1, 1), _time(2, 8)],
        "jogos": [{"cor_a": 1, "cor_b": 2, "vencedor": 1}],
    }
    return {"dados": json.dumps({**base, **mudancas})}


# ------------------------------------------------------------- caminho feliz

def test_salva_a_pelada_e_volta_para_a_classificacao(cliente):
    c, Fabrica = cliente
    r = c.post("/lancar", data=_noite())
    assert r.status_code == 303 and r.headers["location"] == "/"
    with Fabrica() as s:
        pelada = s.query(Pelada).one()
        assert pelada.data == date.today()
        assert len(pelada.participacoes) == 14
        assert len(pelada.partidas) == 1


def test_grava_a_posicao_de_cada_jogador(cliente):
    c, Fabrica = cliente
    c.post("/lancar", data=_noite())
    with Fabrica() as s:
        pos = {p.jogador_id: p.posicao for p in s.query(Pelada).one().participacoes}
        assert pos[1] == "GOL" and pos[7] == "ATA"
        assert pos[8] == "GOL" and pos[14] == "ATA"


def test_reserva_entra_com_posicao_res(cliente):
    c, Fabrica = cliente
    c.post("/lancar", data=_noite(times=[_time(1, 1, reservas=2), _time(2, 11)]))
    with Fabrica() as s:
        reservas = [p for p in s.query(Pelada).one().participacoes if p.posicao == "RES"]
        assert len(reservas) == 2


def test_empate_grava_vencedor_vazio(cliente):
    c, Fabrica = cliente
    c.post("/lancar", data=_noite(jogos=[{"cor_a": 1, "cor_b": 2, "vencedor": None}]))
    with Fabrica() as s:
        assert s.query(Partida).one().empate


# ----------------------------------------------------------------- tres times

def test_salva_noite_de_tres_times_com_varios_jogos(cliente):
    c, Fabrica = cliente
    r = c.post("/lancar", data=_noite(
        times=[_time(1, 1), _time(2, 8), _time(3, 15)],
        jogos=[
            {"cor_a": 1, "cor_b": 2, "vencedor": 1},
            {"cor_a": 1, "cor_b": 3, "vencedor": 3},
            {"cor_a": 3, "cor_b": 2, "vencedor": None},
            {"cor_a": 1, "cor_b": 2, "vencedor": 2},
        ],
    ))
    assert r.headers["location"] == "/"
    with Fabrica() as s:
        pelada = s.query(Pelada).one()
        assert len(pelada.participacoes) == 21
        assert len(pelada.partidas) == 4
        # A ordem dos jogos e preservada: e ela que conta a historia da noite.
        assert [j.ordem for j in pelada.partidas] == [1, 2, 3, 4]
        assert [j.cor_vencedora_id for j in pelada.partidas] == [1, 3, None, 2]


def test_recusa_jogo_com_cor_que_nao_esta_na_noite(cliente):
    c, Fabrica = cliente
    r = c.post("/lancar", data=_noite(jogos=[{"cor_a": 1, "cor_b": 3, "vencedor": 1}]))
    assert "cor+que+nao+jogou" in r.headers["location"]
    with Fabrica() as s:
        assert s.query(Pelada).count() == 0


def test_recusa_vencedor_que_nao_jogou_a_partida(cliente):
    c, _ = cliente
    r = c.post("/lancar", data=_noite(
        times=[_time(1, 1), _time(2, 8), _time(3, 15)],
        jogos=[{"cor_a": 1, "cor_b": 2, "vencedor": 3}],
    ))
    assert "vencedor" in r.headers["location"]


def test_recusa_jogo_com_a_mesma_cor_dos_dois_lados(cliente):
    c, _ = cliente
    r = c.post("/lancar", data=_noite(jogos=[{"cor_a": 1, "cor_b": 1, "vencedor": 1}]))
    assert "mesma+cor+dos+dois+lados" in r.headers["location"]


def test_recusa_noite_sem_nenhum_jogo(cliente):
    c, Fabrica = cliente
    r = c.post("/lancar", data=_noite(jogos=[]))
    assert "pelo+menos+um+jogo" in r.headers["location"]
    with Fabrica() as s:
        assert s.query(Pelada).count() == 0


# ------------------------------------------------------------------ recusas

def test_recusa_data_no_futuro(cliente):
    # Pelada que ainda nao aconteceu nao pode ser lancada. O calendario apaga
    # essas datas, mas a regra precisa valer no servidor: o navegador nao e
    # uma barreira de confianca.
    c, Fabrica = cliente
    amanha = (date.today() + timedelta(days=1)).isoformat()
    r = c.post("/lancar", data=_noite(data=amanha))
    assert "ainda+nao+chegou" in r.headers["location"]
    with Fabrica() as s:
        assert s.query(Pelada).count() == 0


def test_aceita_a_data_de_hoje(cliente):
    c, Fabrica = cliente
    r = c.post("/lancar", data=_noite(data=date.today().isoformat()))
    assert r.headers["location"] == "/"
    with Fabrica() as s:
        assert s.query(Pelada).one().data == date.today()


def test_recusa_jogador_escalado_em_dois_times(cliente):
    c, Fabrica = cliente
    r = c.post("/lancar", data=_noite(times=[_time(1, 1), _time(2, 5)]))
    assert "mais+de+um+time" in r.headers["location"]
    with Fabrica() as s:
        assert s.query(Pelada).count() == 0


def test_recusa_times_com_a_mesma_cor(cliente):
    c, _ = cliente
    r = c.post("/lancar", data=_noite(times=[_time(1, 1), _time(1, 8)]))
    assert "mesma+cor" in r.headers["location"]


def test_recusa_time_sem_os_sete_titulares(cliente):
    c, Fabrica = cliente
    r = c.post("/lancar", data=_noite(times=[_time(1, 1), _time(2, 8, titulares=6)]))
    assert "titulares" in r.headers["location"]
    with Fabrica() as s:
        assert s.query(Pelada).count() == 0


def test_recusa_noite_com_um_time_so(cliente):
    c, _ = cliente
    r = c.post("/lancar", data=_noite(times=[_time(1, 1)]))
    assert "dois+times" in r.headers["location"]


def test_recusa_duas_peladas_na_mesma_data(cliente):
    c, Fabrica = cliente
    c.post("/lancar", data=_noite())
    r = c.post("/lancar", data=_noite(times=[_time(1, 15), _time(2, 8)]))
    assert "Ja+existe+pelada" in r.headers["location"]
    with Fabrica() as s:
        assert s.query(Pelada).count() == 1


def test_recusa_json_malformado(cliente):
    c, Fabrica = cliente
    r = c.post("/lancar", data={"dados": "isso nao e json"})
    assert "erro" in r.headers["location"]
    with Fabrica() as s:
        assert s.query(Pelada).count() == 0


# ----------------------------------------- cadastro de jogador sem sair da tela

def test_cadastra_jogador_e_devolve_o_id(cliente):
    c, Fabrica = cliente
    r = c.post("/api/jogadores", data={"apelido": "Zezinho"})
    assert r.status_code == 200
    assert r.json()["apelido"] == "Zezinho"
    with Fabrica() as s:
        assert s.query(Jogador).filter_by(apelido="Zezinho").one().id == r.json()["id"]


def test_recusa_apelido_repetido_ignorando_maiusculas(cliente):
    # "ze" e "Ze" seriam duas pessoas na estatistica - a mesma fragmentacao
    # que o id existe para evitar.
    c, Fabrica = cliente
    c.post("/api/jogadores", data={"apelido": "Ze"})
    r = c.post("/api/jogadores", data={"apelido": "  zE "})
    assert r.status_code == 422 and "ja esta no elenco" in r.json()["erro"]
    with Fabrica() as s:
        assert s.query(Jogador).filter(Jogador.apelido.ilike("ze")).count() == 1


def test_recusa_apelido_vazio(cliente):
    c, Fabrica = cliente
    antes = 0
    with Fabrica() as s:
        antes = s.query(Jogador).count()
    r = c.post("/api/jogadores", data={"apelido": "   "})
    assert r.status_code == 422
    with Fabrica() as s:
        assert s.query(Jogador).count() == antes


def test_o_jogador_cadastrado_pode_ser_escalado_na_hora(cliente):
    """O caminho que a tela faz: cadastra e ja usa o id na mesma pelada."""
    c, Fabrica = cliente
    novo = c.post("/api/jogadores", data={"apelido": "Chegou Agora"}).json()
    time_b = _time(2, 8)
    time_b["jogadores"][-1] = {"id": novo["id"], "posicao": "ATA"}
    r = c.post("/lancar", data=_noite(times=[_time(1, 1), time_b]))
    assert r.headers["location"] == "/"
    with Fabrica() as s:
        ids = {p.jogador_id for p in s.query(Pelada).one().participacoes}
        assert novo["id"] in ids
