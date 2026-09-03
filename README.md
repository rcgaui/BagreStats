# BagreStats

Acompanhamento de estatísticas da pelada com os amigos.
A pelada costuma ser na quinta, mas a data é livre: nada no código depende
do dia da semana.

## Rodar

```bash
python3 -m venv .venv                     # só na primeira vez
.venv/bin/pip install -r requirements.txt # só na primeira vez
cp .env.example .env                      # só na primeira vez
.venv/bin/alembic upgrade head            # cria/atualiza as tabelas
.venv/bin/uvicorn app.main:app --reload
```

Abrir <http://127.0.0.1:8000>.

## Testes

```bash
.venv/bin/python -m pytest tests/ -q
```

## Carga inicial

Importa `PELADA.xlsx` para o banco. Roda uma vez, pode repetir sem duplicar:

```bash
.venv/bin/python scripts/carga_inicial.py
```

## Estrutura

```
app/config.py    configuração (lê o .env)
app/db.py        conexão com o banco
app/models.py    as quatro tabelas
app/stats.py     as contas (aproveitamento, duplas, fregueses, confrontos)
app/main.py      as rotas web
app/templates/   as telas
alembic/         migrações do banco
tests/           testes das contas e das validações
```

As camadas são separadas de propósito: `stats.py` não sabe o que é HTML, e
`main.py` não faz conta. É isso que permite trocar a camada web por um app de
celular sem mexer nas regras.

## Mudanças no banco

Nunca alterar tabela na mão. Edite `app/models.py` e gere a migração:

```bash
.venv/bin/alembic revision --autogenerate -m "descrição da mudança"
.venv/bin/alembic upgrade head
```
