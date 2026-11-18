from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.entities.area_campus import AreaCampus


class AreaCampusRepository:
    def __init__(self, sessao: Session) -> None:
        self.sessao = sessao

    def buscar_ativa(self, area_id: UUID) -> AreaCampus | None:
        area = self.sessao.get(AreaCampus, area_id)
        return area if area is not None and area.ativo else None

    def listar_para_exibicao(self) -> list[AreaCampus]:
        """Limites primeiro, depois por prioridade e nome."""
        consulta = (
            select(AreaCampus)
            .where(AreaCampus.ativo)
            .order_by(AreaCampus.limite_campus.desc(), AreaCampus.prioridade.desc(), AreaCampus.nome)
        )
        return list(self.sessao.scalars(consulta))

    def listar_por_prioridade(self) -> list[AreaCampus]:
        consulta = select(AreaCampus).where(AreaCampus.ativo).order_by(AreaCampus.prioridade.desc(), AreaCampus.nome)
        return list(self.sessao.scalars(consulta))

    def existe_limite_ativo(self) -> bool:
        consulta = select(AreaCampus.id).where(AreaCampus.ativo, AreaCampus.limite_campus).limit(1)
        return self.sessao.scalar(consulta) is not None

    def adicionar(self, area: AreaCampus) -> AreaCampus:
        self.sessao.add(area)
        return area
