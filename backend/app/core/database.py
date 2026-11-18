from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import configuracoes


class Base(DeclarativeBase):
    pass


engine = create_engine(configuracoes.database_url, pool_pre_ping=True)
FabricaSessao = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def obter_banco() -> Generator[Session, None, None]:
    """Abre uma sessão por requisição e a fecha ao final."""
    banco = FabricaSessao()
    try:
        yield banco
    finally:
        banco.close()
