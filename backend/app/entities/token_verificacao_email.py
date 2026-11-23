from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TokenVerificacaoEmail(Base):
    """Link de confirmação de e-mail. Só o hash SHA-256 do token é guardado: o token em si vai apenas no e-mail.

    O link fica preso ao endereço para o qual foi enviado: se o e-mail da conta mudar depois, o link
    antigo deixa de valer (ele comprovaria o endereço errado). Para isso guarda `email_hash`, o SHA-256
    do token junto com o endereço, e nunca o endereço em texto claro: sem o token (que só existe no
    e-mail) não dá para descobrir o endereço a partir do banco, nem por tentativa.
    """

    __tablename__ = "tokens_verificacao_email"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    usuario_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("credentials.id"), nullable=False, index=True)
    email_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    usado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
