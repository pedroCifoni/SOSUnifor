from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TokenSessao(Base):
    """Refresh token de uma sessão. Só o hash SHA-256 é guardado; o token vai apenas para o cliente.

    Cada renovação gera um token novo e revoga o anterior (rotação). Reapresentar um token já
    revogado indica roubo: todas as sessões da conta são encerradas.
    """

    __tablename__ = "tokens_sessao"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    usuario_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("credentials.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revogado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TentativaLogin(Base):
    """Falha de login, para limitar tentativas por e-mail e por IP (força bruta).

    O e-mail é guardado só como hash: a tabela não revela quem tentou entrar.
    """

    __tablename__ = "tentativas_login"
    __table_args__ = (
        Index("ix_tentativas_login_email_hash_criada_em", "email_hash", "criada_em"),
        Index("ix_tentativas_login_ip_criada_em", "ip", "criada_em"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    email_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
