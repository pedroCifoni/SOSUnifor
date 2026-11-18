from typing import Annotated

from fastapi import APIRouter, Depends

from app.controllers.dependencias import auth_service
from app.dtos.auth_dto import LoginEntrada, TokenResposta
from app.services.auth_service import AuthService


router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post("/login", response_model=TokenResposta)
def entrar(dados: LoginEntrada, servico: Annotated[AuthService, Depends(auth_service)]) -> TokenResposta:
    return servico.entrar(dados)
