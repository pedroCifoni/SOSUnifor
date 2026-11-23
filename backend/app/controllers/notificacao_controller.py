from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.controllers.dependencias import UsuarioAtual, notificacao_service
from app.dtos.notificacao_dto import NotificacaoResposta, ResumoNotificacoesResposta
from app.dtos.ocorrencia_dto import LIMITE_MAXIMO_PAGINA, LIMITE_PADRAO_PAGINA, CursorPagina, ajustar_limite
from app.services.notificacao_service import NotificacaoService


router = APIRouter(prefix="/notificacoes", tags=["Notificações"])
Servico = Annotated[NotificacaoService, Depends(notificacao_service)]


@router.get("", response_model=list[NotificacaoResposta])
def listar(
    usuario: UsuarioAtual,
    servico: Servico,
    limite: Annotated[int, Query(description=f"1 a {LIMITE_MAXIMO_PAGINA}; fora disso é ajustado")] = LIMITE_PADRAO_PAGINA,
    antes_de: Annotated[str | None, Query(description="criadaEm do último item da página anterior (ISO 8601)")] = None,
    antes_id: Annotated[UUID | None, Query(description="id do último item da página anterior")] = None,
) -> list[NotificacaoResposta]:
    return servico.listar(usuario, cursor=CursorPagina.interpretar(antes_de, antes_id), limite=ajustar_limite(limite))


@router.get("/resumo", response_model=ResumoNotificacoesResposta)
def resumir(usuario: UsuarioAtual, servico: Servico) -> ResumoNotificacoesResposta:
    return servico.resumir(usuario)


@router.patch("/lidas", status_code=status.HTTP_204_NO_CONTENT)
def marcar_como_lidas(usuario: UsuarioAtual, servico: Servico) -> None:
    servico.marcar_todas_como_lidas(usuario)
