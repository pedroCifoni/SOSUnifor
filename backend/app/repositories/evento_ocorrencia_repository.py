from uuid import UUID

from sqlalchemy import func, select, update
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

    def listar_das_ocorrencias(self, ocorrencia_ids: list[UUID]) -> list[EventoOcorrencia]:
        if not ocorrencia_ids:
            return []
        consulta = (
            select(EventoOcorrencia)
            .where(EventoOcorrencia.ocorrencia_id.in_(ocorrencia_ids))
            .order_by(EventoOcorrencia.criado_em)
        )
        return list(self.sessao.scalars(consulta))

    def substituir_nas_descricoes(self, trecho: str, substituto: str) -> None:
        """Troca um texto (ex.: o nome de um titular anonimizado) em todas as descrições que o contêm."""
        if not trecho:
            return
        self.sessao.execute(
            update(EventoOcorrencia)
            .where(EventoOcorrencia.descricao.contains(trecho, autoescape=True))
            .values(descricao=func.replace(EventoOcorrencia.descricao, trecho, substituto))
            .execution_options(synchronize_session=False)
        )
