from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import configuracoes


class Base(DeclarativeBase):
    pass


engine = create_engine(configuracoes.database_url, pool_pre_ping=True)
# A fábrica faz sessões novas; não é para uma requisição ficar dividindo banco igual senha de Netflix.
FabricaSessao = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def obter_banco() -> Generator[Session, None, None]:
    """Abre uma sessão para a requisição e a fecha ao final."""
    # Abriu a requisição? Abre a sessão. Acabou? Fecha. Banco não é porta de geladeira.
    banco = FabricaSessao()
    try:
        yield banco
    finally:
        banco.close()
