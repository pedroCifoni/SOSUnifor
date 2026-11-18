"""Hash de senhas e tokens JWT."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from pwdlib import PasswordHash

from app.core.config import configuracoes
from app.core.excecoes import NaoAutenticadoErro
from app.entities.usuario import Usuario


_gerador_de_hash = PasswordHash.recommended()


def gerar_hash_senha(senha: str) -> str:
    return _gerador_de_hash.hash(senha)


def conferir_senha(senha: str, senha_hash: str) -> bool:
    return _gerador_de_hash.verify(senha, senha_hash)


def criar_token(usuario: Usuario) -> str:
    agora = datetime.now(timezone.utc)
    dados = {
        "sub": str(usuario.id),
        "name": usuario.nome,
        "email": usuario.email,
        "role": usuario.tipo_usuario,
        "iat": agora,
        "exp": agora + timedelta(minutes=configuracoes.access_token_expire_minutes),
    }
    return jwt.encode(dados, configuracoes.jwt_secret, algorithm=configuracoes.jwt_algorithm)


def ler_id_do_token(token: str) -> UUID:
    """Valida assinatura e validade do token e devolve o id do usuário."""
    try:
        dados = jwt.decode(token, configuracoes.jwt_secret, algorithms=[configuracoes.jwt_algorithm])
        return UUID(dados["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise NaoAutenticadoErro("Token inválido ou expirado.") from None
