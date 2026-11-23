from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.entities.token_verificacao_email import TokenVerificacaoEmail


class TokenVerificacaoEmailRepository:
    def __init__(self, sessao: Session) -> None:
        self.sessao = sessao

    def buscar_por_hash_para_uso(self, token_hash: str) -> TokenVerificacaoEmail | None:
        """Busca e trava a linha até o fim da transação, para o mesmo link não ser usado duas vezes ao mesmo tempo."""
        consulta = select(TokenVerificacaoEmail).where(TokenVerificacaoEmail.token_hash == token_hash).with_for_update()
        return self.sessao.scalar(consulta)

    def contar_pedidos_desde(self, usuario_id: UUID, desde: datetime) -> int:
        consulta = (
            select(func.count())
            .select_from(TokenVerificacaoEmail)
            .where(TokenVerificacaoEmail.usuario_id == usuario_id, TokenVerificacaoEmail.criado_em >= desde)
        )
        return self.sessao.scalar(consulta) or 0

    def invalidar_pendentes(self, usuario_id: UUID, agora: datetime) -> None:
        """Marca como usados os links ainda abertos do usuário, para que só o mais recente funcione."""
        self.sessao.execute(
            update(TokenVerificacaoEmail)
            .where(TokenVerificacaoEmail.usuario_id == usuario_id, TokenVerificacaoEmail.usado_em.is_(None))
            .values(usado_em=agora)
        )

    def adicionar(self, token: TokenVerificacaoEmail) -> TokenVerificacaoEmail:
        self.sessao.add(token)
        return token
