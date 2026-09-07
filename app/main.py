"""Camada web: so recebe requisicao, chama as regras e devolve HTML.

Nenhuma conta acontece aqui. Se um dia esta camada devolver JSON em vez de
HTML, o app de celular funciona sem que nada em stats.py mude.
"""
import json
from datetime import date
from urllib.parse import quote_plus

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import graficos, stats
from app.config import BASE_DIR
from app.db import get_session
from app.models import POSICOES, Cor, Jogador, Participacao, Partida, Pelada

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
            "total_peladas": sessao.query(Pelada).count(),
            "total_jogos": sessao.query(Partida).count(),
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


class JogadorEscalado(BaseModel):
    id: int
    posicao: str | None = None


class TimeDaNoite(BaseModel):
    cor_id: int
    jogadores: list[JogadorEscalado]


class JogoDaNoite(BaseModel):
    cor_a: int
    cor_b: int
    vencedor: int | None = None  # ausente = empate


class Lancamento(BaseModel):
    """O que a tela envia: a noite inteira de uma vez.

    Vem como um campo JSON so, em vez de dezenas de campos paralelos: com
    numero variavel de times e de jogos, listas paralelas ficariam faceis de
    desalinhar sem ninguem perceber.
    """

    data: date
    times: list[TimeDaNoite]
    jogos: list[JogoDaNoite]


TITULARES = 7  # vagas do campo; reservas nao contam


def _criticar(lanc: Lancamento, sessao: Session) -> str | None:
    """A primeira coisa errada com o lancamento, ou None se esta tudo certo."""
    if lanc.data > date.today():
        return "Essa data ainda nao chegou"
    if sessao.scalar(select(Pelada).where(Pelada.data == lanc.data)):
        return f"Ja existe pelada em {lanc.data.strftime('%d/%m/%Y')}"
    if len(lanc.times) < 2:
        return "A pelada precisa de pelo menos dois times"

    cores = [t.cor_id for t in lanc.times]
    if len(set(cores)) != len(cores):
        return "Dois times estao com a mesma cor"

    vistos: set[int] = set()
    for time in lanc.times:
        ids = [j.id for j in time.jogadores]
        if vistos & set(ids):
            return "Tem jogador escalado em mais de um time"
        vistos |= set(ids)
        if sum(1 for j in time.jogadores if j.posicao != "RES") < TITULARES:
            return f"Todo time precisa de {TITULARES} titulares"

    if not lanc.jogos:
        return "Registre pelo menos um jogo da noite"
    for i, jogo in enumerate(lanc.jogos, start=1):
        if jogo.cor_a == jogo.cor_b:
            return f"O jogo {i} esta com a mesma cor dos dois lados"
        if jogo.cor_a not in cores or jogo.cor_b not in cores:
            return f"O jogo {i} usa uma cor que nao jogou nesta pelada"
        if jogo.vencedor is not None and jogo.vencedor not in (jogo.cor_a, jogo.cor_b):
            return f"O vencedor do jogo {i} nao e um dos times que jogaram"
    return None


@app.post("/lancar")
def salvar_pelada(dados: str = Form(...), sessao: Session = Depends(get_session)):
    try:
        lanc = Lancamento.model_validate_json(dados)
    except ValidationError:
        return RedirectResponse("/lancar?erro=Nao+entendi+os+dados+enviados", 303)

    # As regras valem aqui, nao so na tela: o navegador nao e barreira de
    # confianca, e uma pelada torta contamina a estatistica inteira.
    if problema := _criticar(lanc, sessao):
        return RedirectResponse(f"/lancar?erro={quote_plus(problema)}", 303)

    pelada = Pelada(data=lanc.data)
    sessao.add(pelada)
    sessao.flush()
    for time in lanc.times:
        for jogador in time.jogadores:
            sessao.add(
                Participacao(
                    pelada_id=pelada.id,
                    jogador_id=jogador.id,
                    cor_id=time.cor_id,
                    posicao=jogador.posicao or None,
                )
            )
    for ordem, jogo in enumerate(lanc.jogos, start=1):
        sessao.add(
            Partida(
                pelada_id=pelada.id,
                ordem=ordem,
                cor_a_id=jogo.cor_a,
                cor_b_id=jogo.cor_b,
                cor_vencedora_id=jogo.vencedor,
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


def _cadastrar_jogador(sessao: Session, apelido: str) -> tuple[Jogador | None, str]:
    """Cria o jogador, ou devolve o motivo de nao ter criado."""
    nome = apelido.strip()
    if not nome:
        return None, "O apelido nao pode ficar vazio"
    # Comparacao sem diferenciar maiusculas: "ze" e "Ze" seriam duas pessoas
    # diferentes na estatistica, que e exatamente a fragmentacao que o id evita.
    ja_existe = sessao.scalar(
        select(Jogador).where(func.lower(Jogador.apelido) == nome.lower())
    )
    if ja_existe:
        return None, f"{ja_existe.apelido} ja esta no elenco"
    jogador = Jogador(apelido=nome)
    sessao.add(jogador)
    sessao.commit()
    return jogador, ""


@app.post("/jogadores")
def novo_jogador(apelido: str = Form(...), sessao: Session = Depends(get_session)):
    _cadastrar_jogador(sessao, apelido)
    return RedirectResponse("/jogadores", 303)


@app.post("/api/jogadores")
def novo_jogador_json(apelido: str = Form(...), sessao: Session = Depends(get_session)):
    """Cadastro sem sair da pagina.

    A tela de lancar pelada precisa disso: um POST comum recarregaria a
    pagina e levaria junto toda a escalacao montada ate ali.
    """
    jogador, motivo = _cadastrar_jogador(sessao, apelido)
    if jogador is None:
        return JSONResponse({"erro": motivo}, status_code=422)
    return {"id": jogador.id, "apelido": jogador.apelido}


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
