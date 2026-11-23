from datetime import datetime
from uuid import UUID

from sqlalchemy import select, tuple_
from sqlalchemy.dialects.postgresql import insert as insert_postgres
from sqlalchemy.orm import Session

from app.entities.registro_auditoria import RegistroAuditoria
from app.entities.usuario import Usuario


class AuditoriaRepository:
    def __init__(self, sessao: Session) -> None:
        self.sessao = sessao

    def registrar_se_novo(self, valores: dict) -> bool:
        """INSERT idempotente pelo id do evento. Devolve False se o evento já estava gravado."""
        if self.sessao.get_bind().dialect.name == "postgresql":
            comando = (
                insert_postgres(RegistroAuditoria)
                .values(**valores)
                .on_conflict_do_nothing(index_elements=[RegistroAuditoria.id])
                .returning(RegistroAuditoria.id)
            )
            return self.sessao.execute(comando).scalar() is not None
        if self.sessao.get(RegistroAuditoria, valores["id"]) is not None:
            return False
        self.sessao.add(RegistroAuditoria(**valores))
        self.sessao.flush()
        return True

    def listar_com_nome_do_ator(
        self,
        tipo: str | None = None,
        desde: datetime | None = None,
        ate: datetime | None = None,
        antes_de: datetime | None = None,
        antes_id: UUID | None = None,
        limite: int = 50,
    ) -> list[tuple[RegistroAuditoria, str | None]]:
        """Uma página dos registros mais recentes primeiro, com paginação por cursor (ocorrido_em, id).

        ``tipo`` filtra pelo prefixo: "auditoria.usuario" traz todas as ações sobre usuários.
        """
        consulta = (
            select(RegistroAuditoria, Usuario.nome)
            .outerjoin(Usuario, Usuario.id == RegistroAuditoria.ator_id)
            .order_by(RegistroAuditoria.ocorrido_em.desc(), RegistroAuditoria.id.desc())
            .limit(limite)
        )
        if tipo:
            consulta = consulta.where(RegistroAuditoria.tipo.startswith(tipo, autoescape=True))
        if desde is not None:
            consulta = consulta.where(RegistroAuditoria.ocorrido_em >= desde)
        if ate is not None:
            consulta = consulta.where(RegistroAuditoria.ocorrido_em <= ate)
        if antes_de is not None and antes_id is not None:
            consulta = consulta.where(
                tuple_(RegistroAuditoria.ocorrido_em, RegistroAuditoria.id) < tuple_(antes_de, antes_id)
            )
        return [(registro, nome) for registro, nome in self.sessao.execute(consulta).all()]
