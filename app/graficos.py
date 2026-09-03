"""Converte series de numeros em coordenadas de SVG.

ponytail: SVG escrito a mao em vez de uma biblioteca de graficos. Sao tres
formas simples (linha, barra empilhada, barra horizontal) e o arquivo inteiro
tem menos linhas do que a chamada de configuracao de uma biblioteca teria -
alem de funcionar sem internet e sem carregar 200kb no navegador.
Teto: se um dia precisar de zoom, tooltip ou eixo de tempo de verdade, trocar
por uma biblioteca dedicada.

Este modulo so faz geometria. Nao sabe o que e pelada, jogador ou vitoria.
"""
from dataclasses import dataclass


@dataclass
class Ponto:
    x: float
    y: float
    valor: float
    rotulo: str


@dataclass
class Linha:
    """Um grafico de linha pronto para o template desenhar."""

    pontos: list[Ponto]
    largura: float
    altura: float

    @property
    def caminho(self) -> str:
        """O atributo points de um <polyline>."""
        return " ".join(f"{p.x:.1f},{p.y:.1f}" for p in self.pontos)

    @property
    def area(self) -> str:
        """O mesmo caminho fechado embaixo, para pintar a area sob a curva."""
        if not self.pontos:
            return ""
        primeiro, ultimo = self.pontos[0], self.pontos[-1]
        return (
            f"M{primeiro.x:.1f},{self.altura} L{self.caminho.replace(' ', ' L')} "
            f"L{ultimo.x:.1f},{self.altura} Z"
        )


def linha(serie: list[tuple[str, float]], largura=520.0, altura=120.0, margem=10.0) -> Linha:
    """Espalha a serie na horizontal e escala 0-100% na vertical.

    A escala vertical e fixa em 0-100 de proposito: aproveitamento de 40% tem
    que parecer 40% em qualquer grafico. Escala automatica faria uma queda de
    2% parecer um desastre.
    """
    if not serie:
        return Linha(pontos=[], largura=largura, altura=altura)

    util = altura - 2 * margem
    passo = (largura - 2 * margem) / max(len(serie) - 1, 1)
    pontos = [
        Ponto(
            x=margem + (i * passo if len(serie) > 1 else (largura - 2 * margem) / 2),
            y=margem + util * (1 - min(max(valor, 0), 100) / 100),
            valor=valor,
            rotulo=rotulo,
        )
        for i, (rotulo, valor) in enumerate(serie)
    ]
    return Linha(pontos=pontos, largura=largura, altura=altura)


def proporcoes(*valores: int) -> list[float]:
    """Converte contagens em porcentagens que somam 100, para barra empilhada.

    Devolve zeros quando nao ha nada, em vez de dividir por zero.
    """
    total = sum(valores)
    return [0.0] * len(valores) if not total else [100 * v / total for v in valores]
