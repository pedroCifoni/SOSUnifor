from typing import Annotated

from fastapi import APIRouter, Depends

from app.controllers.dependencias import auth_service, auth_service_com_email
from app.dtos.auth_dto import EsqueciSenhaEntrada, LoginEntrada, MensagemResposta, RedefinirSenhaEntrada, TokenResposta
from app.services.auth_service import AuthService


router = APIRouter(prefix="/auth", tags=["Autenticação"])
ServicoComEmail = Annotated[AuthService, Depends(auth_service_com_email)]


@router.post("/login", response_model=TokenResposta)
def entrar(dados: LoginEntrada, servico: Annotated[AuthService, Depends(auth_service)]) -> TokenResposta:
    return servico.entrar(dados)


@router.post("/esqueci-senha", response_model=MensagemResposta)
def esqueci_senha(dados: EsqueciSenhaEntrada, servico: ServicoComEmail) -> MensagemResposta:
    """Envia um link de redefinição para o e-mail, se ele estiver cadastrado. A resposta não revela se existe."""
    return servico.solicitar_redefinicao_senha(dados)


@router.post("/redefinir-senha", response_model=MensagemResposta)
def redefinir_senha(dados: RedefinirSenhaEntrada, servico: ServicoComEmail) -> MensagemResposta:
    return servico.redefinir_senha(dados)
