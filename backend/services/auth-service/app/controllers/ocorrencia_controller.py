from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.controllers.dependencias import Administrador, UsuarioAtual, UsuarioComum, ocorrencia_service
from app.dtos.ocorrencia_dto import (
    EncaminhamentoEntrada,
    OcorrenciaDetalheResposta,
    OcorrenciaEntrada,
    OcorrenciaResposta,
    StatusEntrada,
)
from app.services.ocorrencia_service import OcorrenciaService


router = APIRouter(prefix="/ocorrencias", tags=["Ocorrências"])
Servico = Annotated[OcorrenciaService, Depends(ocorrencia_service)]


@router.get("", response_model=list[OcorrenciaResposta])
def listar(usuario: UsuarioAtual, servico: Servico) -> list[OcorrenciaResposta]:
    return servico.listar(usuario)


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
