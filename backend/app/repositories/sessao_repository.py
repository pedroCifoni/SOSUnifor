from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.entities.sessao import TentativaLogin, TokenSessao


class TokenSessaoRepository:
    def __init__(self, sessao: Session) -> None:
        self.sessao = sessao

    def adicionar(self, token: TokenSessao) -> None:
        self.sessao.add(token)

    def buscar_por_hash_para_uso(self, token_hash: str) -> TokenSessao | None:
        """Trava a linha: duas renovações simultâneas com o mesmo token não geram duas sessões."""
        consulta = select(TokenSessao).where(TokenSessao.token_hash == token_hash).with_for_update()
        return self.sessao.scalar(consulta)

    def revogar_todos(self, usuario_id: UUID, agora: datetime) -> int:
        resultado = self.sessao.execute(
            update(TokenSessao)
            .where(TokenSessao.usuario_id == usuario_id, TokenSessao.revogado_em.is_(None))
            .values(revogado_em=agora)
        )
        return resultado.rowcount or 0

    def apagar_vencidos(self, limite: datetime) -> int:
        resultado = self.sessao.execute(
            delete(TokenSessao).where(or_(TokenSessao.expira_em < limite, TokenSessao.revogado_em < limite))
        )
        return resultado.rowcount or 0


class TentativaLoginRepository:
    def __init__(self, sessao: Session) -> None:
        self.sessao = sessao

    def registrar(self, email_hash: str, ip: str | None, agora: datetime) -> None:
        self.sessao.add(TentativaLogin(email_hash=email_hash, ip=ip, criada_em=agora))

    def contar_por_email(self, email_hash: str, desde: datetime) -> int:
        consulta = select(func.count()).select_from(TentativaLogin).where(
            TentativaLogin.email_hash == email_hash, TentativaLogin.criada_em >= desde
        )
        return int(self.sessao.scalar(consulta) or 0)

    def contar_por_ip(self, ip: str, desde: datetime) -> int:
        consulta = select(func.count()).select_from(TentativaLogin).where(
            TentativaLogin.ip == ip, TentativaLogin.criada_em >= desde
        )
        return int(self.sessao.scalar(consulta) or 0)

    def limpar_do_email(self, email_hash: str) -> None:
        self.sessao.execute(delete(TentativaLogin).where(TentativaLogin.email_hash == email_hash))

    def apagar_antigas(self, limite: datetime) -> int:
        return self.sessao.execute(delete(TentativaLogin).where(TentativaLogin.criada_em < limite)).rowcount or 0
