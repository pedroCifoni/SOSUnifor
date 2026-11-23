from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.entities.token_redefinicao_senha import TokenRedefinicaoSenha


class TokenRedefinicaoSenhaRepository:
    def __init__(self, sessao: Session) -> None:
        self.sessao = sessao

    def buscar_por_hash_para_uso(self, token_hash: str) -> TokenRedefinicaoSenha | None:
        """Busca e trava a linha até o fim da transação, para o mesmo link não ser usado duas vezes ao mesmo tempo."""
        consulta = select(TokenRedefinicaoSenha).where(TokenRedefinicaoSenha.token_hash == token_hash).with_for_update()
        return self.sessao.scalar(consulta)

    def buscar_usuario_id_por_hash(self, token_hash: str) -> UUID | None:
        return self.sessao.scalar(select(TokenRedefinicaoSenha.usuario_id).where(TokenRedefinicaoSenha.token_hash == token_hash))

    def contar_pedidos_desde(self, usuario_id: UUID, desde: datetime) -> int:
        consulta = (
            select(func.count())
            .select_from(TokenRedefinicaoSenha)
            .where(TokenRedefinicaoSenha.usuario_id == usuario_id, TokenRedefinicaoSenha.criado_em >= desde)
        )
        return self.sessao.scalar(consulta) or 0

    def invalidar_pendentes(self, usuario_id: UUID, agora: datetime) -> None:
        """Marca como usados os tokens ainda abertos do usuário, para que só o mais recente funcione."""
        self.sessao.execute(
            update(TokenRedefinicaoSenha)
            .where(TokenRedefinicaoSenha.usuario_id == usuario_id, TokenRedefinicaoSenha.usado_em.is_(None))
            .values(usado_em=agora)
        )

    def adicionar(self, token: TokenRedefinicaoSenha) -> TokenRedefinicaoSenha:
        self.sessao.add(token)
        return token
