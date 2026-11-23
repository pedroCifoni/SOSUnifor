from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.controllers.dependencias import Administrador, UsuarioAtual, usuario_service
from app.dtos.auth_dto import MensagemResposta
from app.dtos.usuario_dto import (
    SegurancaNotificadaResposta,
    UsuarioAdminResposta,
    UsuarioAtualizacao,
    UsuarioEntrada,
    UsuarioLoteEntrada,
    UsuarioLoteResposta,
    UsuarioResposta,
)
from app.services.usuario_service import UsuarioService


router = APIRouter(tags=["Usuários"])
Servico = Annotated[UsuarioService, Depends(usuario_service)]


@router.get("/usuarios", response_model=list[UsuarioAdminResposta])
def listar(_: Administrador, servico: Servico) -> list[UsuarioAdminResposta]:
    return servico.listar_ativos()


@router.get("/usuarios/segurancas", response_model=list[UsuarioResposta])
def listar_segurancas(_: UsuarioAtual, servico: Servico) -> list[UsuarioResposta]:
    return servico.listar_por_perfil("seguranca")


@router.get("/usuarios/tecnicos", response_model=list[UsuarioResposta])
def listar_tecnicos(_: UsuarioAtual, servico: Servico) -> list[UsuarioResposta]:
    return servico.listar_por_perfil("tecnico")


@router.post("/usuarios", status_code=status.HTTP_201_CREATED, response_model=UsuarioAdminResposta)
def criar(dados: UsuarioEntrada, _: Administrador, servico: Servico) -> UsuarioAdminResposta:
    return servico.criar(dados)


@router.post("/usuarios/lote", response_model=UsuarioLoteResposta)
def salvar_em_lote(dados: UsuarioLoteEntrada, administrador: Administrador, servico: Servico) -> UsuarioLoteResposta:
    return servico.salvar_em_lote(dados, administrador)


@router.put("/usuarios/{usuario_id}", response_model=UsuarioAdminResposta)
def atualizar(usuario_id: UUID, dados: UsuarioAtualizacao, administrador: Administrador, servico: Servico) -> UsuarioAdminResposta:
    return servico.atualizar(usuario_id, dados, administrador)


@router.post("/usuarios/{usuario_id}/reenviar-verificacao", response_model=MensagemResposta)
def reenviar_verificacao(usuario_id: UUID, _: Administrador, servico: Servico) -> MensagemResposta:
    return servico.reenviar_verificacao(usuario_id)


@router.delete("/usuarios/{usuario_id}",status_code=status.HTTP_204_NO_CONTENT)
def excluir(usuario_id: UUID, administrador: Administrador, servico: Servico) -> None:
    servico.excluir(usuario_id, administrador)


@router.get("/segurancas/notificadas", response_model=list[SegurancaNotificadaResposta])
def listar_segurancas_notificadas(_: UsuarioAtual, servico: Servico) -> list[SegurancaNotificadaResposta]:
    return servico.listar_segurancas_notificadas()
