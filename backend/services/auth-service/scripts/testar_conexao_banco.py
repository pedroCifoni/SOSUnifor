"""Confere se a API consegue se conectar ao banco configurado em DATABASE_URL.

Uso, a partir de backend/services/auth-service:
    python -m scripts.testar_conexao_banco
"""

from sqlalchemy import text

from app.core.database import engine


def testar_conexao() -> None:
    with engine.connect() as conexao:
        print("Banco conectado:", conexao.execute(text("SELECT 1")).scalar())


if __name__ == "__main__":
    testar_conexao()
