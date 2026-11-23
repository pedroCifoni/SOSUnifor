from typing import Annotated

from fastapi import APIRouter, Depends

from app.controllers.dependencias import auth_service, auth_service_com_email, verificacao_email_service
from app.dtos.auth_dto import (
    EsqueciSenhaEntrada,
    LoginEntrada,
    MensagemResposta,
    ReenviarVerificacaoEntrada,
    RedefinirSenhaEntrada,
    TokenResposta,
    VerificarEmailEntrada,
)
from app.services.auth_service import AuthService
from app.services.verificacao_email_service import VerificacaoEmailService


router = APIRouter(prefix="/auth", tags=["Autenticação"])
ServicoComEmail = Annotated[AuthService, Depends(auth_service_com_email)]
ServicoVerificacao = Annotated[VerificacaoEmailService, Depends(verificacao_email_service)]


@router.post("/login", response_model=TokenResposta)
def entrar(dados: LoginEntrada, servico: Annotated[AuthService, Depends(auth_service)]) -> TokenResposta:
    """401 para credenciais inválidas; 403 com `codigo: "email_nao_verificado"` se a senha confere mas o e-mail não."""
    return servico.entrar(dados)


@router.post("/esqueci-senha", response_model=MensagemResposta)
def esqueci_senha(dados: EsqueciSenhaEntrada, servico: ServicoComEmail) -> MensagemResposta:
    """Envia um link de redefinição para o e-mail, se ele estiver cadastrado. A resposta não revela se existe."""
    return servico.solicitar_redefinicao_senha(dados)


@router.post("/redefinir-senha", response_model=MensagemResposta)
def redefinir_senha(dados: RedefinirSenhaEntrada, servico: ServicoComEmail) -> MensagemResposta:
    return servico.redefinir_senha(dados)


@router.post("/verificar-email", response_model=MensagemResposta)
def verificar_email(dados: VerificarEmailEntrada, servico: ServicoVerificacao) -> MensagemResposta:
    return servico.confirmar(dados)


@router.post("/reenviar-verificacao", response_model=MensagemResposta)
def reenviar_verificacao(dados: ReenviarVerificacaoEntrada, servico: ServicoVerificacao) -> MensagemResposta:
    """Envia um novo link de confirmação, se a conta existir e ainda não estiver confirmada. A resposta é sempre igual."""
    return servico.reenviar(dados)
