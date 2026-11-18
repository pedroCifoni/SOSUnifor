from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Notificacao(Base):
    __tablename__ = "notificacoes"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    destinatario_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("credentials.id"), nullable=False, index=True)
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    titulo: Mapped[str] = mapped_column(String(160), nullable=False)
    mensagem: Mapped[str] = mapped_column(String(300), nullable=False)
    ocorrencia_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("ocorrencias.id"), nullable=False)
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    lida: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
