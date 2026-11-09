from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import configuracoes
from app.core.database import obter_banco
from app.models.credential import Usuario


esquema_bearer = HTTPBearer(auto_error=False)


def criar_token(usuario: Usuario) -> str:
    agora = datetime.now(timezone.utc)
    expira_em = agora + timedelta(minutes=configuracoes.access_token_expire_minutes)
    dados = {
        "sub": str(usuario.id),
        "name": usuario.nome,
        "email": usuario.email,
        "role": usuario.tipo_usuario,
        "iat": agora,
        "exp": expira_em,
    }
    return jwt.encode(dados, configuracoes.jwt_secret, algorithm=configuracoes.jwt_algorithm)


def obter_usuario_atual(
    credenciais: Annotated[HTTPAuthorizationCredentials | None, Depends(esquema_bearer)],
    banco: Annotated[Session, Depends(obter_banco)],
) -> Usuario:
    if credenciais is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticação obrigatória.")
    try:
        dados = jwt.decode(credenciais.credentials, configuracoes.jwt_secret, algorithms=[configuracoes.jwt_algorithm])
        usuario_id = UUID(dados["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido ou expirado.") from None

    usuario = banco.get(Usuario, usuario_id)
    if usuario is None or not usuario.ativo:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário sem acesso.")
    agora = datetime.now(timezone.utc)
    if usuario.ultimo_acesso is None or agora - usuario.ultimo_acesso >= timedelta(seconds=20):
        usuario.ultimo_acesso = agora
        banco.commit()
    return usuario


def exigir_perfil(*perfis: str):
    def validar(usuario: Annotated[Usuario, Depends(obter_usuario_atual)]) -> Usuario:
        if usuario.tipo_usuario not in perfis:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Você não tem permissão para esta ação.")
        return usuario

    return validar
