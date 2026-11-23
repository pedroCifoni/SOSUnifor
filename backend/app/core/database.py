from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import configuracoes


class Base(DeclarativeBase):
    pass


def _argumentos_de_conexao() -> dict:
    """Sem prepared statements quando o banco fica atrás de um pooler em modo transação (ex.: Neon "-pooler")."""
    if not configuracoes.db_prepared_statements and configuracoes.database_url.startswith("postgresql+psycopg"):
        return {"prepare_threshold": None}
    return {}


def _opcoes_de_pool() -> dict:
    """O SQLite (usado só em testes rápidos) não aceita as opções de pool do QueuePool."""
    if configuracoes.database_url.startswith("sqlite"):
        return {}
    return {
        "pool_size": configuracoes.db_pool_size,
        "max_overflow": configuracoes.db_max_overflow,
        "pool_timeout": configuracoes.db_pool_timeout,
        "pool_recycle": configuracoes.db_pool_recycle,
    }


engine = create_engine(
    configuracoes.database_url,
    pool_pre_ping=True,
    connect_args=_argumentos_de_conexao(),
    **_opcoes_de_pool(),
)
FabricaSessao = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def obter_banco() -> Generator[Session, None, None]:
    """Abre uma sessão por requisição e a fecha ao final."""
    banco = FabricaSessao()
    try:
        yield banco
    finally:
        banco.close()
