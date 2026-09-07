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
from app.models import Cor, Jogador, Participacao, Partida, Pelada
from app.stats import classificacao, confrontos, perfil


@pytest.fixture
def sessao():
    """Banco de mentira, na memoria, refeito a cada teste."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as s:
        yield s


def _monta(sessao, cores_nomes, jogadores_nomes):
    cores = {n: Cor(nome=n, codigo="#000") for n in cores_nomes}
    jogadores = {n: Jogador(apelido=n) for n in jogadores_nomes}
    sessao.add_all([*cores.values(), *jogadores.values()])
    sessao.flush()
    return cores, jogadores


def _noite(sessao, dia, escalacao, jogos):
    """escalacao: {cor: [jogadores]} · jogos: [(corA, corB, vencedor|None)]"""
    pelada = Pelada(data=dia)
    sessao.add(pelada)
    sessao.flush()
    for cor, elenco in escalacao.items():
        for j in elenco:
            sessao.add(
                Participacao(pelada_id=pelada.id, jogador_id=j.id, cor_id=cor.id)
            )
    for i, (a, b, vencedor) in enumerate(jogos, start=1):
        sessao.add(
            Partida(
                pelada_id=pelada.id, ordem=i, cor_a_id=a.id, cor_b_id=b.id,
                cor_vencedora_id=vencedor.id if vencedor else None,
            )
        )
    sessao.flush()
    return pelada


@pytest.fixture
def dois_times(sessao):
    """Tres noites com dois times: preto ganha, branco ganha, empate."""
    cores, j = _monta(sessao, ["PRETO", "BRANCO"], list("ABCD"))
    p, b = cores["PRETO"], cores["BRANCO"]
    _noite(sessao, date(2026, 1, 1), {p: [j["A"], j["B"]], b: [j["C"], j["D"]]},
           [(p, b, p)])
    _noite(sessao, date(2026, 1, 8), {p: [j["A"], j["C"]], b: [j["B"], j["D"]]},
           [(p, b, b)])
    _noite(sessao, date(2026, 1, 15), {p: [j["A"], j["B"]], b: [j["C"], j["D"]]},
           [(p, b, None)])
    sessao.commit()
    return sessao


@pytest.fixture
def tres_times(sessao):
    """Uma noite de tres times com quatro jogos, no rodizio de quem ganha fica.

    PRETO: A, B   ·   BRANCO: C, D   ·   VERMELHO: E, F

      jogo 1: PRETO   x BRANCO   -> PRETO      (vermelho sentou)
      jogo 2: PRETO   x VERMELHO -> VERMELHO   (branco sentou)
      jogo 3: VERMELHO x BRANCO  -> empate     (preto sentou)
      jogo 4: PRETO   x BRANCO   -> BRANCO     (vermelho sentou)
    """
    cores, j = _monta(sessao, ["PRETO", "BRANCO", "VERMELHO"], list("ABCDEF"))
    p, b, v = cores["PRETO"], cores["BRANCO"], cores["VERMELHO"]
    _noite(
        sessao, date(2026, 2, 5),
        {p: [j["A"], j["B"]], b: [j["C"], j["D"]], v: [j["E"], j["F"]]},
        [(p, b, p), (p, v, v), (v, b, None), (p, b, b)],
    )
    sessao.commit()
    return sessao


def _linha(tabela, apelido):
    return next(l for l in tabela if l.jogador.apelido == apelido)


def _id(sessao, apelido):
    return sessao.query(Jogador).filter_by(apelido=apelido).one().id


# --------------------------------------------------------------- dois times

def test_pontos_seguem_o_criterio_de_pontos_corridos(dois_times):
    tabela = classificacao(dois_times)
    # B ganhou duas e empatou uma: 3 + 3 + 1
    assert _linha(tabela, "B").pontos == 7
    # A ganhou, perdeu e empatou: 3 + 0 + 1
    assert _linha(tabela, "A").pontos == 4
    assert _linha(tabela, "C").pontos == 1


def test_aproveitamento_e_percentual_dos_pontos_possiveis(dois_times):
    tabela = classificacao(dois_times)
    assert _linha(tabela, "B").aproveitamento == pytest.approx(77.78, abs=0.01)
    assert _linha(tabela, "A").aproveitamento == pytest.approx(44.44, abs=0.01)


def test_empate_nao_conta_como_vitoria_nem_derrota(dois_times):
    linha = _linha(classificacao(dois_times), "A")
    assert (linha.vitorias, linha.empates, linha.derrotas) == (1, 1, 1)
    assert linha.jogos == 3


def test_classificacao_ordenada_por_pontos(dois_times):
    assert [l.jogador.apelido for l in classificacao(dois_times)][0] == "B"


def test_sequencia_sem_perder_para_na_ultima_derrota(dois_times):
    assert perfil(dois_times, _id(dois_times, "A")).sem_perder == 1
    assert perfil(dois_times, _id(dois_times, "B")).sem_perder == 3


def test_dupla_conta_so_jogos_no_mesmo_time(dois_times):
    p = perfil(dois_times, _id(dois_times, "A"))
    duplas = {d.jogador.apelido: d for d in p.duplas}
    assert (duplas["B"].jogos, duplas["B"].vitorias) == (2, 1)
    assert (duplas["C"].jogos, duplas["C"].vitorias) == (1, 0)
    assert "D" not in duplas  # nunca foram do mesmo time


def test_freguês_conta_so_jogos_em_times_opostos(dois_times):
    p = perfil(dois_times, _id(dois_times, "A"))
    contra = {f.jogador.apelido: f for f in p.fregueses}
    assert (contra["D"].jogos, contra["D"].vitorias) == (3, 1)
    assert (contra["B"].jogos, contra["B"].vitorias) == (1, 0)


def test_confronto_de_cores_junta_os_dois_sentidos(dois_times):
    (c,) = confrontos(dois_times)
    assert (c.cor_a, c.cor_b) == ("BRANCO", "PRETO")
    assert (c.vitorias_a, c.vitorias_b, c.empates) == (1, 1, 1)


def test_jogador_sem_pelada_nao_quebra(sessao):
    novato = Jogador(apelido="Novato")
    sessao.add(novato)
    sessao.commit()
    p = perfil(sessao, novato.id)
    assert p.linha.jogos == 0 and p.linha.aproveitamento == 0.0
    assert p.evolucao == []


# --------------------------------------------------------------- tres times

def test_conta_por_jogo_e_nao_por_noite(tres_times):
    """Numa noite so, cada time joga um numero diferente de partidas."""
    tabela = classificacao(tres_times)
    # PRETO jogou 3 (jogos 1, 2 e 4): venceu 1, perdeu 2
    assert (_linha(tabela, "A").vitorias, _linha(tabela, "A").derrotas) == (1, 2)
    assert _linha(tabela, "A").jogos == 3
    # BRANCO jogou 3 (jogos 1, 3 e 4): venceu 1, empatou 1, perdeu 1
    linha_c = _linha(tabela, "C")
    assert (linha_c.vitorias, linha_c.empates, linha_c.derrotas) == (1, 1, 1)
    # VERMELHO jogou 2 (jogos 2 e 3): venceu 1, empatou 1
    linha_e = _linha(tabela, "E")
    assert (linha_e.vitorias, linha_e.empates, linha_e.derrotas) == (1, 1, 0)
    assert linha_e.jogos == 2


def test_quem_sentou_nao_pontua_no_jogo_que_nao_disputou(tres_times):
    """VERMELHO ficou fora dos jogos 1 e 4; nao pode levar V nem D por eles."""
    linha = _linha(classificacao(tres_times), "E")
    assert linha.jogos == 2  # e nao 4


def test_uma_noite_so_conta_uma_pelada_mesmo_com_varios_jogos(tres_times):
    linha = _linha(classificacao(tres_times), "A")
    assert linha.peladas == 1
    assert linha.jogos == 3


def test_freguês_com_tres_times_separa_por_jogo(tres_times):
    """A (PRETO) enfrentou BRANCO em dois jogos e VERMELHO em um."""
    p = perfil(tres_times, _id(tres_times, "A"))
    contra = {f.jogador.apelido: f for f in p.fregueses}
    assert contra["C"].jogos == 2  # branco, jogos 1 e 4
    assert contra["C"].vitorias == 1  # venceu o 1, perdeu o 4
    assert contra["E"].jogos == 1  # vermelho, jogo 2
    assert contra["E"].vitorias == 0


def test_dupla_conta_todos_os_jogos_da_noite_juntos(tres_times):
    """A e B foram do mesmo time a noite toda: 3 jogos juntos."""
    p = perfil(tres_times, _id(tres_times, "A"))
    duplas = {d.jogador.apelido: d for d in p.duplas}
    assert (duplas["B"].jogos, duplas["B"].vitorias) == (3, 1)
    assert "C" not in duplas  # nunca foram do mesmo time


def test_confronto_de_cores_separa_os_tres_pares(tres_times):
    pares = {(c.cor_a, c.cor_b): c for c in confrontos(tres_times)}
    assert set(pares) == {("BRANCO", "PRETO"), ("PRETO", "VERMELHO"),
                          ("BRANCO", "VERMELHO")}
    pb = pares[("BRANCO", "PRETO")]
    assert (pb.vitorias_a, pb.vitorias_b, pb.jogos) == (1, 1, 2)
    bv = pares[("BRANCO", "VERMELHO")]
    assert (bv.empates, bv.jogos) == (1, 1)


def test_historico_tem_uma_linha_por_jogo(tres_times):
    p = perfil(tres_times, _id(tres_times, "A"))
    assert len(p.historico) == 3
    assert [r for _, _, r in p.historico] == ["D", "D", "V"]  # mais recente primeiro


def test_evolucao_avanca_jogo_a_jogo(tres_times):
    p = perfil(tres_times, _id(tres_times, "A"))
    # venceu (3/3), perdeu (3/6), perdeu (3/9)
    assert [round(v, 1) for _, v in p.evolucao] == [100.0, 50.0, 33.3]
