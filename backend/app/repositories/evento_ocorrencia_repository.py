from uuid import UUID

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session

from app.entities.evento_ocorrencia import EventoOcorrencia
from app.entities.ocorrencia import Ocorrencia


class EventoOcorrenciaRepository:
    def __init__(self, sessao: Session) -> None:
        self.sessao = sessao

    def registrar(
        self,
        ocorrencia_id: UUID,
        tipo: str,
        descricao: str,
        autor_id: UUID | None,
        destinatario_id: UUID | None = None,
    ) -> None:
        self.sessao.add(
            EventoOcorrencia(
                ocorrencia_id=ocorrencia_id,
                tipo=tipo,
                descricao=descricao,
                autor_id=autor_id,
                destinatario_id=destinatario_id,
            )
        )

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

    def substituir_nome_do_destinatario(
        self, destinatario_id: UUID, nome: str, substituto: str, *, legados_em_qualquer_ocorrencia: bool
    ) -> None:
        """Troca "para {nome};" por "para {substituto};" só nos eventos que citam esta pessoa.

        Eventos novos guardam `destinatario_id`. Os antigos (sem ele) só são alterados nas ocorrências
        em que a pessoa é a responsável atual, a não ser que `legados_em_qualquer_ocorrencia` seja
        verdadeiro (quem chama garante que não há outra conta com o mesmo nome).
        """
        if not nome:
            return
        trecho, novo = f"para {nome};", f"para {substituto};"
        legados = and_(EventoOcorrencia.destinatario_id.is_(None), EventoOcorrencia.tipo == "encaminhada")
        if not legados_em_qualquer_ocorrencia:
            legados = and_(
                legados,
                EventoOcorrencia.ocorrencia_id.in_(
                    select(Ocorrencia.id).where(Ocorrencia.responsavel_id == destinatario_id)
                ),
            )
        self.sessao.execute(
            update(EventoOcorrencia)
            .where(
                or_(EventoOcorrencia.destinatario_id == destinatario_id, legados),
                EventoOcorrencia.descricao.contains(trecho, autoescape=True),
            )
            .values(descricao=func.replace(EventoOcorrencia.descricao, trecho, novo))
            .execution_options(synchronize_session=False)
        )
