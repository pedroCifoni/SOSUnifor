from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.controllers.dependencias import UsuarioAtual, notificacao_service
from app.dtos.notificacao_dto import NotificacaoResposta
from app.services.notificacao_service import NotificacaoService


router = APIRouter(prefix="/notificacoes", tags=["Notificações"])
Servico = Annotated[NotificacaoService, Depends(notificacao_service)]


@router.get("", response_model=list[NotificacaoResposta])
def listar(usuario: UsuarioAtual, servico: Servico) -> list[NotificacaoResposta]:
    return servico.listar(usuario)


@router.patch("/lidas", status_code=status.HTTP_204_NO_CONTENT)
def marcar_como_lidas(usuario: UsuarioAtual, servico: Servico) -> None:
    servico.marcar_todas_como_lidas(usuario)
