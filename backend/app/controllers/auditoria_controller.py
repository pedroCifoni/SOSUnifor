from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.controllers.dependencias import Administrador, auditoria_service
from app.dtos.auditoria_dto import RegistroAuditoriaResposta
from app.dtos.ocorrencia_dto import LIMITE_MAXIMO_PAGINA, LIMITE_PADRAO_PAGINA, CursorPagina, ajustar_limite
from app.services.auditoria_service import AuditoriaService


router = APIRouter(prefix="/auditoria", tags=["Auditoria"])
Servico = Annotated[AuditoriaService, Depends(auditoria_service)]


@router.get("", response_model=list[RegistroAuditoriaResposta])
def listar(
    _: Administrador,
    servico: Servico,
    limite: Annotated[int, Query(description=f"1 a {LIMITE_MAXIMO_PAGINA}; fora disso é ajustado")] = LIMITE_PADRAO_PAGINA,
    antes_de: Annotated[str | None, Query(description="ocorridoEm do último item da página anterior (ISO 8601)")] = None,
    antes_id: Annotated[UUID | None, Query(description="id do último item da página anterior")] = None,
    tipo: Annotated[
        str | None,
        Query(max_length=80, description='Prefixo do tipo: "auditoria.usuario", "auditoria.ocorrencia.criar", "ocorrencia."…'),
    ] = None,
    desde: Annotated[datetime | None, Query(description="Início do período (ISO 8601)")] = None,
    ate: Annotated[datetime | None, Query(description="Fim do período (ISO 8601)")] = None,
) -> list[RegistroAuditoriaResposta]:
    """Trilha de auditoria (só administradores), dos registros mais recentes para os mais antigos."""
    return servico.listar(
        cursor=CursorPagina.interpretar(antes_de, antes_id),
        limite=ajustar_limite(limite),
        tipo=tipo,
        desde=desde,
        ate=ate,
    )
