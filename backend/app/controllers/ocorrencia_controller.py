from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.controllers.dependencias import Administrador, UsuarioAtual, UsuarioComum, ocorrencia_service
from app.dtos.ocorrencia_dto import (
    LIMITE_MAXIMO_PAGINA,
    LIMITE_PADRAO_PAGINA,
    CursorPagina,
    EncaminhamentoEntrada,
    OcorrenciaDetalheResposta,
    OcorrenciaEntrada,
    OcorrenciaResposta,
    ResumoOcorrenciasResposta,
    StatusEntrada,
    StatusOcorrencia,
    TipoOcorrencia,
    ajustar_limite,
)
from app.services.ocorrencia_service import OcorrenciaService


router = APIRouter(prefix="/ocorrencias", tags=["Ocorrências"])
Servico = Annotated[OcorrenciaService, Depends(ocorrencia_service)]


@router.get("", response_model=list[OcorrenciaResposta])
def listar(
    usuario: UsuarioAtual,
    servico: Servico,
    limite: Annotated[int, Query(description=f"1 a {LIMITE_MAXIMO_PAGINA}; fora disso é ajustado")] = LIMITE_PADRAO_PAGINA,
    antes_de: Annotated[str | None, Query(description="criadoEm do último item da página anterior (ISO 8601)")] = None,
    antes_id: Annotated[UUID | None, Query(description="id do último item da página anterior")] = None,
    status: StatusOcorrencia | None = None,
    tipo: TipoOcorrencia | None = None,
) -> list[OcorrenciaResposta]:
    cursor = CursorPagina.interpretar(antes_de, antes_id)
    return servico.listar(usuario, cursor=cursor, limite=ajustar_limite(limite), status=status, tipo=tipo)


# Declarada antes de /{ocorrencia_id} para "resumo" não ser lido como id.
@router.get("/resumo", response_model=ResumoOcorrenciasResposta)
def resumir(usuario: UsuarioAtual, servico: Servico) -> ResumoOcorrenciasResposta:
    return servico.resumir(usuario)


@router.get("/{ocorrencia_id}", response_model=OcorrenciaDetalheResposta)
def detalhar(ocorrencia_id: UUID, usuario: UsuarioAtual, servico: Servico) -> OcorrenciaDetalheResposta:
    return servico.detalhar(ocorrencia_id, usuario)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=OcorrenciaResposta)
def criar(dados: OcorrenciaEntrada, autor: UsuarioComum, servico: Servico) -> OcorrenciaResposta:
    return servico.criar(dados, autor)


@router.patch("/{ocorrencia_id}/encaminhar", response_model=OcorrenciaResposta)
def encaminhar(
    ocorrencia_id: UUID, dados: EncaminhamentoEntrada, administrador: Administrador, servico: Servico
) -> OcorrenciaResposta:
    return servico.encaminhar(ocorrencia_id, dados, administrador)


@router.patch("/{ocorrencia_id}/status", response_model=OcorrenciaResposta)
def atualizar_status(ocorrencia_id: UUID, dados: StatusEntrada, usuario: UsuarioAtual, servico: Servico) -> OcorrenciaResposta:
    return servico.atualizar_status(ocorrencia_id, dados, usuario)
