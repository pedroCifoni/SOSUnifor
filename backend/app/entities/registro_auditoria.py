from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RegistroAuditoria(Base):
    """Trilha de auditoria: um registro por evento publicado em "unisos.eventos".

    O id é o próprio id do evento. Assim, se o RabbitMQ reentregar a mesma mensagem
    (ou dois workers a receberem), o segundo INSERT é ignorado e não há duplicidade.
    Não há chave estrangeira em ``ator_id``: a trilha precisa sobreviver a qualquer
    mudança nas contas.
    """

    __tablename__ = "auditoria"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    tipo: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    versao: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    ocorrido_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ator_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    entidade: Mapped[str | None] = mapped_column(String(40), nullable=True)
    entidade_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resultado: Mapped[str] = mapped_column(String(10), nullable=False, default="sucesso")
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # "broker" (gravado pelo consumidor da fila) ou "direto" (fallback sem RabbitMQ).
    origem: Mapped[str] = mapped_column(String(10), nullable=False, default="broker")
    dados: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    registrado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
