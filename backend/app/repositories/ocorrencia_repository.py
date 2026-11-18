from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.entities.ocorrencia import Ocorrencia


class OcorrenciaRepository:
    def __init__(self, sessao: Session) -> None:
        self.sessao = sessao

    def buscar_por_id(self, ocorrencia_id: UUID) -> Ocorrencia | None:
        return self.sessao.get(Ocorrencia, ocorrencia_id)

    def listar(self, autor_id: UUID | None = None, responsavel_id: UUID | None = None) -> list[Ocorrencia]:
        """Lista as mais recentes primeiro, opcionalmente filtrando por autor ou responsável."""
        consulta = select(Ocorrencia).order_by(Ocorrencia.criado_em.desc())
        if autor_id is not None:
            consulta = consulta.where(Ocorrencia.autor_id == autor_id)
        if responsavel_id is not None:
            consulta = consulta.where(Ocorrencia.responsavel_id == responsavel_id)
        return list(self.sessao.scalars(consulta))

    def listar_com_anexos(self) -> list[Ocorrencia]:
        return list(self.sessao.scalars(select(Ocorrencia).where(Ocorrencia.anexos.is_not(None))))

    def contar(self) -> int:
        return self.sessao.scalar(select(func.count()).select_from(Ocorrencia)) or 0

    def adicionar(self, ocorrencia: Ocorrencia) -> Ocorrencia:
        self.sessao.add(ocorrencia)
        self.sessao.flush()
        return ocorrencia
