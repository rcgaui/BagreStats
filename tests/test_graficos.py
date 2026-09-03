"""Testes da geometria dos graficos: e conta, entao tem teste."""
from app.graficos import linha, proporcoes


def test_escala_vertical_e_fixa_de_zero_a_cem():
    g = linha([("a", 0.0), ("b", 100.0)], largura=100, altura=100, margem=10)
    # 0% encosta embaixo (altura - margem), 100% encosta em cima (margem)
    assert g.pontos[0].y == 90
    assert g.pontos[1].y == 10


def test_ponto_unico_fica_centralizado():
    g = linha([("a", 50.0)], largura=100, altura=100, margem=10)
    assert len(g.pontos) == 1
    assert g.pontos[0].x == 50  # centro do grafico de 100 de largura


def test_serie_vazia_nao_quebra():
    g = linha([])
    assert g.pontos == [] and g.caminho == "" and g.area == ""


def test_valores_fora_da_faixa_sao_aparados():
    g = linha([("a", -20.0), ("b", 300.0)], altura=100, margem=10)
    assert g.pontos[0].y == 90 and g.pontos[1].y == 10


def test_proporcoes_somam_cem():
    assert sum(proporcoes(3, 1, 1)) == 100
    assert proporcoes(1, 0, 0) == [100.0, 0.0, 0.0]


def test_proporcoes_sem_nenhum_jogo_nao_divide_por_zero():
    assert proporcoes(0, 0, 0) == [0.0, 0.0, 0.0]
