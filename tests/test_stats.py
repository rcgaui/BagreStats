"""Testes das contas do BagreStats.

Testamos so a camada de regras: aproveitamento, sequencia, dupla, freguês e
confronto de cores. E onde um erro fica INVISIVEL - a tela mostra 63% com
toda a confianca e ninguem descobre que a conta esta errada.
"""
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Cor, Jogador, Participacao, Partida
from app.stats import classificacao, confrontos, perfil


@pytest.fixture
def sessao():
    """Banco de mentira, na memoria, refeito a cada teste."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as s:
        yield s


@pytest.fixture
def pelada(sessao):
    """Tres quintas: preto ganha, branco ganha, empate."""
    preto = Cor(nome="PRETO", codigo="#000")
    branco = Cor(nome="BRANCO", codigo="#fff")
    a, b, c, d = (Jogador(apelido=n) for n in "ABCD")
    sessao.add_all([preto, branco, a, b, c, d])
    sessao.flush()

    def quinta(dia, vencedor, time_preto, time_branco):
        p = Partida(data=dia, cor_vencedora_id=vencedor.id if vencedor else None)
        sessao.add(p)
        sessao.flush()
        for jogador, cor in [(j, preto) for j in time_preto] + [(j, branco) for j in time_branco]:
            sessao.add(Participacao(partida_id=p.id, jogador_id=jogador.id, cor_id=cor.id))
        sessao.flush()

    quinta(date(2026, 1, 1), preto, [a, b], [c, d])
    quinta(date(2026, 1, 8), branco, [a, c], [b, d])
    quinta(date(2026, 1, 15), None, [a, b], [c, d])
    sessao.commit()
    return sessao


def _linha(tabela, apelido):
    return next(l for l in tabela if l.jogador.apelido == apelido)


def test_pontos_seguem_o_criterio_de_pontos_corridos(pelada):
    tabela = classificacao(pelada)
    # B ganhou duas e empatou uma: 3 + 3 + 1
    assert _linha(tabela, "B").pontos == 7
    # A ganhou, perdeu e empatou: 3 + 0 + 1
    assert _linha(tabela, "A").pontos == 4
    # C perdeu duas e empatou uma
    assert _linha(tabela, "C").pontos == 1


def test_aproveitamento_e_percentual_dos_pontos_possiveis(pelada):
    tabela = classificacao(pelada)
    # 7 pontos de 9 possiveis em 3 jogos
    assert _linha(tabela, "B").aproveitamento == pytest.approx(77.78, abs=0.01)
    assert _linha(tabela, "A").aproveitamento == pytest.approx(44.44, abs=0.01)


def test_empate_nao_conta_como_vitoria_nem_derrota(pelada):
    linha = _linha(classificacao(pelada), "A")
    assert (linha.vitorias, linha.empates, linha.derrotas) == (1, 1, 1)
    assert linha.jogos == 3


def test_classificacao_ordenada_por_pontos(pelada):
    assert [l.jogador.apelido for l in classificacao(pelada)][0] == "B"


def test_sequencia_sem_perder_para_na_ultima_derrota(pelada):
    # A: venceu, perdeu, empatou -> so o empate conta
    assert perfil(pelada, _id(pelada, "A")).sem_perder == 1
    # B: venceu, venceu, empatou -> nunca perdeu
    assert perfil(pelada, _id(pelada, "B")).sem_perder == 3


def _id(sessao, apelido):
    return sessao.query(Jogador).filter_by(apelido=apelido).one().id


def test_dupla_conta_so_jogos_no_mesmo_time(pelada):
    p = perfil(pelada, _id(pelada, "A"))
    duplas = {d.jogador.apelido: d for d in p.duplas}
    # A jogou com B nas quintas 1 e 3 (venceu uma, empatou outra)
    assert (duplas["B"].jogos, duplas["B"].vitorias) == (2, 1)
    # A jogou com C so na quinta 2, e perdeu
    assert (duplas["C"].jogos, duplas["C"].vitorias) == (1, 0)
    assert "D" not in duplas  # nunca foram do mesmo time


def test_freguês_conta_so_jogos_em_times_opostos(pelada):
    p = perfil(pelada, _id(pelada, "A"))
    contra = {f.jogador.apelido: f for f in p.fregueses}
    # A enfrentou D nas tres quintas e so venceu a primeira
    assert (contra["D"].jogos, contra["D"].vitorias) == (3, 1)
    # B aparece dos dois lados: parceiro em duas, adversario na quinta 2
    assert (contra["B"].jogos, contra["B"].vitorias) == (1, 0)


def test_confronto_de_cores_junta_os_dois_sentidos(pelada):
    (c,) = confrontos(pelada)
    assert (c.cor_a, c.cor_b) == ("BRANCO", "PRETO")
    assert (c.vitorias_a, c.vitorias_b, c.empates) == (1, 1, 1)
    assert c.jogos == 3


def test_jogador_sem_partida_nao_quebra(sessao):
    novato = Jogador(apelido="Novato")
    sessao.add(novato)
    sessao.commit()
    p = perfil(sessao, novato.id)
    assert p.linha.jogos == 0
    assert p.linha.aproveitamento == 0.0
