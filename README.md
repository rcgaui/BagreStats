# BagreStats

Plataforma de estatísticas para pelada entre amigos. Registra quem jogou, de
que lado e quem ganhou — e transforma isso em classificação, aproveitamento
por jogador, sequências, estatística de dupla e histórico.

Feito como projeto de estudo, construído inteiramente em par com IA
(Claude Code): as decisões de produto e modelagem foram discutidas e definidas
por mim, o código foi escrito pelo agente, e cada peça foi explicada durante a
construção. O objetivo não era só ter a ferramenta — era entender o projeto
inteiro, de ponta a ponta.

## O problema

A pelada era registrada numa planilha: uma aba com a data e o vencedor, outra
com a lista de quem jogou de cada lado. Funciona para anotar, mas não responde
nenhuma pergunta interessante — quem mais ganha, com quem eu jogo melhor,
quem é meu freguês, quem nunca perde.

O BagreStats troca a planilha pelo mesmo registro, com as perguntas respondidas.

## As telas

| Tela | O que faz |
|---|---|
| **Classificação** | Tabela no formato de campeonato: J, V, E, D, pontos e aproveitamento |
| **Lançar pelada** | Escolhe as cores dos times, marca quem jogou de cada lado, aponta o resultado |
| **Perfil do jogador** | Aproveitamento, curva de evolução, melhores duplas, fregueses e histórico |
| **Confrontos** | Retrospecto entre as cores de colete |
| **Elenco** | Cadastro de jogadores e de cores |

## As estatísticas

- **Aproveitamento** — percentual dos pontos possíveis (3 por vitória, 1 por empate)
- **Presença** — quantas peladas cada um jogou
- **Sequência sem perder** — quantas peladas desde a última derrota
- **Dupla** — com quem cada jogador mais vence, jogando do mesmo lado
- **Freguês** — contra quem cada jogador mais vence
- **Confronto de cores** — retrospecto entre coletes

## O modelo de dados

Quatro tabelas. As decisões por trás delas são o que sustenta tudo:

| Tabela | Papel |
|---|---|
| `jogador` | id fixo + apelido editável |
| `cor` | as cores dos coletes, com código hexadecimal |
| `partida` | uma pelada. `cor_vencedora_id` vazio significa empate |
| `participacao` | liga jogador + partida + cor |

**Jogador é id, não texto.** Renomear um apelido não quebra o histórico, porque
tudo se liga pelo id. Texto livre fragmentaria a estatística com variações do
mesmo nome.

**Time não é entidade permanente.** Os times são sorteados a cada pelada, então
a cor é só a etiqueta daquele dia. Por isso a estatística acumula no jogador, e
o confronto entre cores existe apenas como curiosidade — assumidamente sem
significado esportivo.

**Empate é a ausência de vencedor**, não uma coluna própria. E derrota não é
gravada: é derivada, perdeu quem não é o vencedor. Cada fato mora num lugar só,
sem espaço para os dois se contradizerem.

**`UNIQUE(partida_id, jogador_id)`** impede o mesmo jogador nos dois times.
A regra vive no banco, não no código: não depende de ninguém lembrar de conferir.

## O que ficou de fora, de propósito

Tão importante quanto o que existe:

- **Gols e artilharia** — exigiriam anotar durante o jogo, que é o atrito que
  mata sistema pessoal. Sem gols também não há nota de desempenho por jogador.
- **Posição em campo** — não alimenta nenhuma estatística atual.
- **Login e hospedagem** — o sistema roda local, um usuário.
- **Postgres e Docker** — SQLite dá conta de uma pelada por semana com folga.
- **Biblioteca de gráficos** — os gráficos são SVG escrito à mão. São três
  formas simples, e o módulo inteiro é menor que a configuração que uma
  biblioteca pediria.

## Stack

Python 3.11 · FastAPI · Jinja2 · SQLAlchemy · Alembic · SQLite · SVG

Uma peça só: o Python recebe a requisição, consulta o banco e devolve o HTML
pronto. Sem build, sem `npm`, sem front separado.

As camadas são separadas de propósito:

```
app/config.py    configuração (lê o .env)
app/db.py        conexão com o banco
app/models.py    as quatro tabelas
app/stats.py     as contas — nenhuma linha sabe o que é HTML
app/graficos.py  geometria dos gráficos
app/main.py      as rotas — nenhuma linha faz conta
app/templates/   as telas
alembic/         migrações do banco
tests/           testes das contas e das validações
```

É essa separação que permite trocar a camada web por uma API JSON para um app
de celular sem tocar nas regras.

## Rodando

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload
```

Abrir <http://127.0.0.1:8000>.

## Testes

```bash
.venv/bin/python -m pytest tests/ -q
```

Os testes cobrem as contas e as validações — onde um erro seria silencioso e a
tela mostraria um número errado com toda a confiança. Não testam se a página
abriu.

## Mudanças no banco

Nunca alterar tabela na mão. Editar `app/models.py` e gerar a migração:

```bash
.venv/bin/alembic revision --autogenerate -m "descrição da mudança"
.venv/bin/alembic upgrade head
```
