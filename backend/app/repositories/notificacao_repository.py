from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, select, tuple_, update
from sqlalchemy.orm import Session

from app.entities.notificacao import Notificacao


class NotificacaoRepository:
    def __init__(self, sessao: Session) -> None:
        self.sessao = sessao

    def adicionar(self, notificacao: Notificacao) -> None:
        self.sessao.add(notificacao)

    def existe_do_tipo(self, destinatario_id: UUID, tipo: str) -> bool:
        consulta = select(Notificacao.id).where(Notificacao.destinatario_id == destinatario_id, Notificacao.tipo == tipo).limit(1)
        return self.sessao.scalar(consulta) is not None

    def listar_do_destinatario(
        self,
        destinatario_id: UUID,
        antes_de: datetime | None = None,
        antes_id: UUID | None = None,
        limite: int = 50,
    ) -> list[Notificacao]:
        """Uma página das mais recentes primeiro, com paginação por cursor (criada_em, id)."""
        consulta = (
            select(Notificacao)
            .where(Notificacao.destinatario_id == destinatario_id)
            .order_by(Notificacao.criada_em.desc(), Notificacao.id.desc())
            .limit(limite)
        )
        if antes_de is not None and antes_id is not None:
            consulta = consulta.where(tuple_(Notificacao.criada_em, Notificacao.id) < tuple_(antes_de, antes_id))
        return list(self.sessao.scalars(consulta))

    def contar_nao_lidas(self, destinatario_id: UUID) -> int:
        consulta = (
            select(func.count())
            .select_from(Notificacao)
            .where(Notificacao.destinatario_id == destinatario_id, Notificacao.lida.is_(False))
        )
        return self.sessao.scalar(consulta) or 0

    def marcar_todas_como_lidas(self, destinatario_id: UUID) -> None:
        """Um único UPDATE em lote, sem carregar as notificações."""
        self.sessao.execute(
            update(Notificacao)
            .where(Notificacao.destinatario_id == destinatario_id, Notificacao.lida.is_(False))
            .values(lida=True)
            .execution_options(synchronize_session=False)
        )

    def listar_todas_do_destinatario(self, destinatario_id: UUID) -> list[Notificacao]:
        consulta = (
            select(Notificacao)
            .where(Notificacao.destinatario_id == destinatario_id)
            .order_by(Notificacao.criada_em.desc(), Notificacao.id.desc())
        )
        return list(self.sessao.scalars(consulta))

    def apagar_do_destinatario(self, destinatario_id: UUID) -> None:
        self.sessao.execute(delete(Notificacao).where(Notificacao.destinatario_id == destinatario_id))
