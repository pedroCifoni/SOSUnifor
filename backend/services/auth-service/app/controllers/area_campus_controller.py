from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.controllers.dependencias import Administrador, UsuarioAtual, area_campus_service
from app.dtos.area_campus_dto import AreaCampusEntrada, AreaCampusResposta, CoordenadasEntrada, LocalizacaoResposta
from app.services.area_campus_service import AreaCampusService


router = APIRouter(prefix="/areas-campus", tags=["Áreas do campus"])
Servico = Annotated[AreaCampusService, Depends(area_campus_service)]


@router.get("", response_model=list[AreaCampusResposta])
def listar(_: UsuarioAtual, servico: Servico) -> list[AreaCampusResposta]:
    return servico.listar()


@router.post("", status_code=status.HTTP_201_CREATED, response_model=AreaCampusResposta)
def criar(dados: AreaCampusEntrada, _: Administrador, servico: Servico) -> AreaCampusResposta:
    return servico.criar(dados)


@router.post("/identificar", response_model=LocalizacaoResposta)
def identificar(dados: CoordenadasEntrada, _: UsuarioAtual, servico: Servico) -> LocalizacaoResposta:
    return servico.identificar(dados.latitude, dados.longitude)


@router.put("/{area_id}", response_model=AreaCampusResposta)
def atualizar(area_id: UUID, dados: AreaCampusEntrada, _: Administrador, servico: Servico) -> AreaCampusResposta:
    return servico.atualizar(area_id, dados)


@router.delete("/{area_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir(area_id: UUID, _: Administrador, servico: Servico) -> None:
    servico.excluir(area_id)
