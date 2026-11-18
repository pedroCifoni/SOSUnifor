from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.entities.notificacao import Notificacao


class NotificacaoRepository:
    def __init__(self, sessao: Session) -> None:
        self.sessao = sessao

    def adicionar(self, notificacao: Notificacao) -> None:
        self.sessao.add(notificacao)

    def listar_do_destinatario(self, destinatario_id: UUID) -> list[Notificacao]:
        consulta = (
            select(Notificacao)
            .where(Notificacao.destinatario_id == destinatario_id)
            .order_by(Notificacao.criada_em.desc())
        )
        return list(self.sessao.scalars(consulta))

    def listar_nao_lidas(self, destinatario_id: UUID) -> list[Notificacao]:
        consulta = select(Notificacao).where(Notificacao.destinatario_id == destinatario_id, Notificacao.lida.is_(False))
        return list(self.sessao.scalars(consulta))
