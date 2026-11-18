from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Ocorrencia(Base):
    """SOS, chamado de manutenção ou denúncia aberto por um usuário."""

    __tablename__ = "ocorrencias"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    protocolo: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    titulo: Mapped[str] = mapped_column(String(160), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    local: Mapped[str] = mapped_column(String(200), nullable=False)
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pendente")
    autor_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("credentials.id"), nullable=False)
    responsavel_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("credentials.id"), nullable=True)
    anonima: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    anexos: Mapped[list[dict[str, str | None]]] = mapped_column(JSON, nullable=False, default=list)
    latitude: Mapped[float | None] = mapped_column(nullable=True)
    longitude: Mapped[float | None] = mapped_column(nullable=True)
    precisao_metros: Mapped[float | None] = mapped_column(nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
