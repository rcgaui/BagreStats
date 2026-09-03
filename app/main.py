"""Camada web: so recebe requisicao, chama as regras e devolve HTML.

Nenhuma conta acontece aqui. Se um dia esta camada devolver JSON em vez de
HTML, o app de celular funciona sem que nada em stats.py mude.
"""
import json
from datetime import date

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import graficos, stats
from app.config import BASE_DIR
from app.db import get_session
from app.models import POSICOES, Cor, Jogador, Participacao, Partida

app = FastAPI(title="BagreStats")
app.mount("/static", StaticFiles(directory=BASE_DIR / "app" / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")


def _iniciais(apelido: str) -> str:
    partes = apelido.split()
    return (partes[0][0] + partes[-1][0]).upper() if len(partes) > 1 else apelido[:2].upper()


def _cor_do_apelido(apelido: str) -> str:
    """Cor estavel derivada do proprio nome: o mesmo jogador tem sempre a mesma."""
    return f"hsl({sum(map(ord, apelido)) * 47 % 360}, 62%, 68%)"


templates.env.filters["iniciais"] = _iniciais
templates.env.filters["cor_do_apelido"] = _cor_do_apelido
templates.env.globals["proporcoes"] = graficos.proporcoes


def _cores(sessao: Session) -> list[Cor]:
    return list(sessao.scalars(select(Cor).order_by(Cor.nome)))


def _jogadores(sessao: Session) -> list[Jogador]:
    return list(sessao.scalars(select(Jogador).order_by(Jogador.apelido)))


@app.get("/")
def classificacao(request: Request, sessao: Session = Depends(get_session)):
    return templates.TemplateResponse(
        "classificacao.html",
        {
            "request": request,
            "pagina": "tabela",
            "tabela": stats.classificacao(sessao),
            "total_partidas": sessao.query(Partida).count(),
        },
    )


@app.get("/lancar")
def form_lancar(request: Request, erro: str = "", sessao: Session = Depends(get_session)):
    jogadores = _jogadores(sessao)
    return templates.TemplateResponse(
        "lancar.html",
        {
            "request": request,
            "pagina": "lancar",
            "jogadores": jogadores,
            "jogadores_json": json.dumps(
                [{"id": j.id, "apelido": j.apelido} for j in jogadores]
            ),
            "cores": _cores(sessao),
            "posicoes": POSICOES,
            "hoje": date.today().isoformat(),
            "erro": erro,
        },
    )


@app.post("/lancar")
def salvar_pelada(
    data: str = Form(...),
    cor_a: int = Form(...),
    cor_b: int = Form(...),
    vencedor: str = Form(...),
    time_a: list[int] = Form(default=[]),
    time_b: list[int] = Form(default=[]),
    # Paralelas a time_a/time_b: posicoes_a[i] eh a vaga de time_a[i].
    # A tela sempre envia os dois pares juntos, na mesma ordem.
    posicoes_a: list[str] = Form(default=[]),
    posicoes_b: list[str] = Form(default=[]),
    sessao: Session = Depends(get_session),
):
    dia = date.fromisoformat(data)

    # Validacoes na camada web: mensagem amigavel antes de o banco reclamar.
    if cor_a == cor_b:
        return RedirectResponse("/lancar?erro=Os+dois+times+estao+com+a+mesma+cor", 303)
    repetidos = set(time_a) & set(time_b)
    if repetidos:
        return RedirectResponse("/lancar?erro=Tem+jogador+escalado+nos+dois+times", 303)
    if not time_a or not time_b:
        return RedirectResponse("/lancar?erro=Os+dois+times+precisam+de+jogadores", 303)
    if sessao.scalar(select(Partida).where(Partida.data == dia)):
        return RedirectResponse(f"/lancar?erro=Ja+existe+partida+em+{dia}", 303)

    vencedora = {"A": cor_a, "B": cor_b}.get(vencedor)  # ausente = empate
    partida = Partida(data=dia, cor_vencedora_id=vencedora)
    sessao.add(partida)
    sessao.flush()
    for ids, posicoes, cor in (
        (time_a, posicoes_a, cor_a),
        (time_b, posicoes_b, cor_b),
    ):
        for jogador_id, posicao in zip(ids, posicoes):
            sessao.add(
                Participacao(
                    partida_id=partida.id,
                    jogador_id=jogador_id,
                    cor_id=cor,
                    posicao=posicao or None,
                )
            )
    sessao.commit()
    return RedirectResponse("/", 303)


@app.get("/jogador/{jogador_id}")
def ver_jogador(jogador_id: int, request: Request, sessao: Session = Depends(get_session)):
    perfil = stats.perfil(sessao, jogador_id)
    if perfil is None:
        return RedirectResponse("/jogadores", 303)
    curva = graficos.linha(
        [(d.strftime("%d/%m"), v) for d, v in perfil.evolucao], largura=520, altura=130
    )
    return templates.TemplateResponse(
        "perfil.html",
        {"request": request, "pagina": "jogadores", "p": perfil, "curva": curva},
    )


@app.post("/jogador/{jogador_id}/renomear")
def renomear(
    jogador_id: int,
    apelido: str = Form(...),
    sessao: Session = Depends(get_session),
):
    jogador = sessao.get(Jogador, jogador_id)
    if jogador and apelido.strip():
        # O historico nao sente: tudo se liga pelo id, nunca pelo texto.
        jogador.apelido = apelido.strip()
        sessao.commit()
    return RedirectResponse(f"/jogador/{jogador_id}", 303)


@app.get("/jogadores")
def lista_jogadores(request: Request, sessao: Session = Depends(get_session)):
    return templates.TemplateResponse(
        "jogadores.html",
        {"request": request, "pagina": "jogadores", "jogadores": _jogadores(sessao), "cores": _cores(sessao)},
    )


@app.post("/jogadores")
def novo_jogador(apelido: str = Form(...), sessao: Session = Depends(get_session)):
    if apelido.strip() and not sessao.scalar(
        select(Jogador).where(Jogador.apelido == apelido.strip())
    ):
        sessao.add(Jogador(apelido=apelido.strip()))
        sessao.commit()
    return RedirectResponse("/jogadores", 303)


@app.post("/cores")
def nova_cor(
    nome: str = Form(...), codigo: str = Form("#888888"), sessao: Session = Depends(get_session)
):
    nome = nome.strip().upper()
    if nome and not sessao.scalar(select(Cor).where(Cor.nome == nome)):
        sessao.add(Cor(nome=nome, codigo=codigo))
        sessao.commit()
    return RedirectResponse("/jogadores", 303)


@app.get("/confrontos")
def ver_confrontos(request: Request, sessao: Session = Depends(get_session)):
    return templates.TemplateResponse(
        "confrontos.html",
        {
            "request": request,
            "pagina": "confrontos",
            "confrontos": stats.confrontos(sessao),
            "cores": {c.nome: c.codigo for c in _cores(sessao)},
        },
    )
