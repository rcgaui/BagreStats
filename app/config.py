"""Configuracao do projeto.

Nada de endereco de banco escrito no meio do codigo: tudo vem do arquivo
.env, que fica fora do git. E isso que permite a mesma aplicacao rodar na
sua maquina e num servidor sem alterar uma linha de codigo.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'bagre.db'}")

# SQLite guarda o caminho relativo a partir de onde o programa roda, o que
# quebra dependendo da pasta. Transformamos em caminho absoluto.
if DATABASE_URL.startswith("sqlite:///") and not DATABASE_URL.startswith("sqlite:////"):
    nome = DATABASE_URL.removeprefix("sqlite:///")
    DATABASE_URL = f"sqlite:///{BASE_DIR / nome}"
