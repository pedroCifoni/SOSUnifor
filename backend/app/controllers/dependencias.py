"""Injeção de dependências da camada HTTP: usuário autenticado e services."""

from typing import Annotated
from uuid import UUID

from fastapi import BackgroundTasks, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core import mensageria
from app.core.database import obter_banco
from app.entities.usuario import Usuario
from app.services.area_campus_service import AreaCampusService
from app.services.arquivo_service import ArquivoService
from app.services.auth_service import AuthService
from app.services.email_service import EmailService
from app.services.notificacao_service import NotificacaoService
from app.services.ocorrencia_service import OcorrenciaService
from app.services.usuario_service import UsuarioService
from app.services.verificacao_email_service import VerificacaoEmailService


Banco = Annotated[Session, Depends(obter_banco)]
_esquema_bearer = HTTPBearer(auto_error=False)


# ---------- services ----------
def _avisador(tarefas: BackgroundTasks):
    """Agenda o aviso para depois que a resposta for enviada (RabbitMQ; sem ele, só este processo)."""

    def avisar(destinatarios: list[UUID]) -> None:
        tarefas.add_task(mensageria.publicar, destinatarios)

    return avisar


def _emails(tarefas: BackgroundTasks) -> EmailService:
    """E-mails são enviados depois que a resposta sai, para a requisição não esperar o servidor SMTP."""
    return EmailService(agendar=tarefas.add_task)


def auth_service(banco: Banco) -> AuthService:
    return AuthService(banco)


def auth_service_com_email(banco: Banco, tarefas: BackgroundTasks) -> AuthService:
    return AuthService(banco, emails=_emails(tarefas))


def verificacao_email_service(banco: Banco, tarefas: BackgroundTasks) -> VerificacaoEmailService:
    return VerificacaoEmailService(banco, emails=_emails(tarefas))


def usuario_service(banco: Banco, tarefas: BackgroundTasks) -> UsuarioService:
    return UsuarioService(banco, emails=_emails(tarefas))


def area_campus_service(banco: Banco) -> AreaCampusService:
    return AreaCampusService(banco)


def ocorrencia_service(banco: Banco, tarefas: BackgroundTasks) -> OcorrenciaService:
    return OcorrenciaService(banco, avisar=_avisador(tarefas))


def notificacao_service(banco: Banco) -> NotificacaoService:
    return NotificacaoService(banco)


def arquivo_service(banco: Banco) -> ArquivoService:
    return ArquivoService(banco)


# ---------- autenticação ----------
def usuario_atual(
    credenciais: Annotated[HTTPAuthorizationCredentials | None, Depends(_esquema_bearer)],
    servico: Annotated[AuthService, Depends(auth_service)],
) -> Usuario:
    return servico.usuario_do_token(credenciais.credentials if credenciais else None)


def exigir_perfil(*perfis: str):
    def validar(usuario: Annotated[Usuario, Depends(usuario_atual)]) -> Usuario:
        return AuthService.exigir_perfil(usuario, perfis)

    return validar


UsuarioAtual = Annotated[Usuario, Depends(usuario_atual)]
Administrador = Annotated[Usuario, Depends(exigir_perfil("admin"))]
UsuarioComum = Annotated[Usuario, Depends(exigir_perfil("usuario"))]
