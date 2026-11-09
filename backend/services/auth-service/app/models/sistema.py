from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Ocorrencia(Base):
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


class EventoOcorrencia(Base):
    """Registro imutável das ações que realmente aconteceram em um chamado."""

    __tablename__ = "eventos_ocorrencia"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    ocorrencia_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("ocorrencias.id"), nullable=False, index=True)
    autor_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("credentials.id"), nullable=True)
    tipo: Mapped[str] = mapped_column(String(50), nullable=False)
    descricao: Mapped[str] = mapped_column(String(300), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AreaCampus(Base):
    __tablename__ = "areas_campus"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    nome: Mapped[str] = mapped_column(String(160), nullable=False)
    tipo: Mapped[str] = mapped_column(String(50), nullable=False)
    coordenadas: Mapped[list[dict[str, float]]] = mapped_column(JSON, nullable=False)
    limite_campus: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    prioridade: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
