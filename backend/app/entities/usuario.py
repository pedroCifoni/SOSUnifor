from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, LargeBinary, String, Uuid
from sqlalchemy.orm import Mapped, deferred, mapped_column

from app.core.database import Base


class Usuario(Base):
    """Conta de acesso ao sistema. A tabela mantém o nome legado `credentials`."""

    __tablename__ = "credentials"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=False)
    matricula: Mapped[str | None] = mapped_column(String(30), unique=True, index=True, nullable=True)
    senha_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    tipo_usuario: Mapped[str] = mapped_column(String(50), nullable=False, default="usuario")
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ultimo_acesso: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Quando a pessoa comprovou ser dona do e-mail. Nulo = ainda não confirmado (o login é recusado).
    email_verificado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # LGPD: ciência da Política de Privacidade, pedido de eliminação e anonimização.
    termos_aceitos_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    termos_versao: Mapped[str | None] = mapped_column(String(20), nullable=True)
    exclusao_solicitada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    anonimizado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Foto de perfil guardada no banco (no máximo 1 MB): sobrevive aos deploys, ao contrário do disco do Render.
    # "deferred": só é lida quando pedida, então listar contas não carrega as imagens.
    avatar: Mapped[bytes | None] = deferred(mapped_column(LargeBinary, nullable=True))
    avatar_tipo: Mapped[str | None] = mapped_column(String(20), nullable=True)
