# BagreStats

Estatísticas da pelada. Contexto de produto em `PRODUCT.md`; decisões de
arquitetura e o que ficou de fora de propósito em `docs/DECISOES.md`.

## Commits

```
<tipo>(<escopo>): <descrição imperativa em português>

[corpo opcional explicando o porquê, não o quê]
```

| Tipo | Quando usar |
|---|---|
| `feat` | Nova funcionalidade |
| `fix` | Correção de bug |
| `refactor` | Refatoração sem mudança de comportamento |
| `migration` | Nova migration Alembic |
| `test` | Adição ou correção de testes |
| `chore` | Configuração, dependências, CI |
| `docs` | Documentação apenas |

**Escopos neste projeto:** `models`, `stats`, `routers` (`app/main.py`),
`templates`, `graficos`, `migrations`, `database` (`app/db.py`),
`core` (`app/config.py`).

**Regras:**

- Uma responsabilidade por commit — migrations sempre em commit separado do
  código que as usa.
- Nunca commitar `.env` ou arquivos com credenciais.
- Nunca usar `--no-verify`.

## Como rodar

```bash
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload
.venv/bin/python -m pytest tests/ -q
```

## Estrutura

`app/stats.py` não sabe o que é HTML; `app/main.py` não faz conta. É o que
permite servir JSON para um app depois sem tocar nas regras.

O repositório é **público**: apelidos reais dos jogadores não entram em
código, comentário ou teste.
