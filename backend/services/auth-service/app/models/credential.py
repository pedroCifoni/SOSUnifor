from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Usuario(Base):
    __tablename__ = "credentials"

    # UUID não entrega a quantidade de usuários como ID 1, 2, 3... menos pista para curioso.
    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    # E-mail e matrícula são únicos: duas pessoas usando a mesma identidade? Aí é roteiro de novela.
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=False)
    matricula: Mapped[str | None] = mapped_column(String(30), unique=True, index=True, nullable=True)
    # Só guardamos o hash; a senha de verdade nunca deve acampar no banco.
    senha_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    tipo_usuario: Mapped[str] = mapped_column(String(50), nullable=False, default="aluno")
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ultimo_acesso: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
