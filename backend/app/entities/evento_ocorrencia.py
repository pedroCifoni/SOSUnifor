from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EventoOcorrencia(Base):
    """Registro imutável das ações que realmente aconteceram em uma ocorrência."""

    __tablename__ = "eventos_ocorrencia"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    ocorrencia_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("ocorrencias.id"), nullable=False, index=True)
    autor_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("credentials.id"), nullable=True)
    # Pessoa citada pelo nome na descrição (ex.: "Encaminhada para Fulano"). Permite à anonimização
    # trocar só o nome desta pessoa, sem atingir homônimos. Nulo nos eventos antigos e nos que não citam ninguém.
    destinatario_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    tipo: Mapped[str] = mapped_column(String(50), nullable=False)
    descricao: Mapped[str] = mapped_column(String(300), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
