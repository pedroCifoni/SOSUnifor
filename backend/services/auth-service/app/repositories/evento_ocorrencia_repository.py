from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.entities.evento_ocorrencia import EventoOcorrencia


class EventoOcorrenciaRepository:
    def __init__(self, sessao: Session) -> None:
        self.sessao = sessao

    def registrar(self, ocorrencia_id: UUID, tipo: str, descricao: str, autor_id: UUID | None) -> None:
        self.sessao.add(EventoOcorrencia(ocorrencia_id=ocorrencia_id, tipo=tipo, descricao=descricao, autor_id=autor_id))

    def listar_da_ocorrencia(self, ocorrencia_id: UUID) -> list[EventoOcorrencia]:
        consulta = (
            select(EventoOcorrencia)
            .where(EventoOcorrencia.ocorrencia_id == ocorrencia_id)
            .order_by(EventoOcorrencia.criado_em)
        )
        return list(self.sessao.scalars(consulta))
