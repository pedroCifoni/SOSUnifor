from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AreaCampus(Base):
    """Polígono do mapa do campus: limite geral, bloco, estacionamento, área verde etc."""

    __tablename__ = "areas_campus"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    nome: Mapped[str] = mapped_column(String(160), nullable=False)
    tipo: Mapped[str] = mapped_column(String(50), nullable=False)
    coordenadas: Mapped[list[dict[str, float]]] = mapped_column(JSON, nullable=False)
    limite_campus: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    prioridade: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
