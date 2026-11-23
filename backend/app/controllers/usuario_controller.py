from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.controllers.dependencias import Administrador, UsuarioAtual, usuario_service
from app.dtos.auth_dto import MensagemResposta
from app.dtos.usuario_dto import (
    LIMITE_MAXIMO_USUARIOS,
    LIMITE_PADRAO_USUARIOS,
    Perfil,
    ResumoUsuariosResposta,
    SegurancaNotificadaResposta,
    UsuarioAdminResposta,
    UsuarioAtualizacao,
    UsuarioEntrada,
    UsuarioLoteEntrada,
    UsuarioLoteResposta,
    UsuarioResposta,
    ajustar_limite_usuarios,
)
from app.services.usuario_service import UsuarioService


router = APIRouter(tags=["Usuários"])
Servico = Annotated[UsuarioService, Depends(usuario_service)]


@router.get("/usuarios", response_model=list[UsuarioAdminResposta])
def listar(
    _: Administrador,
    servico: Servico,
    busca: Annotated[str | None, Query(max_length=150, description="Texto livre em nome ou e-mail")] = None,
    perfil: Perfil | None = None,
    limite: Annotated[int, Query(description=f"1 a {LIMITE_MAXIMO_USUARIOS}; fora disso é ajustado")] = LIMITE_PADRAO_USUARIOS,
    pagina: Annotated[int, Query(ge=1, description="Página da listagem (a partir de 1)")] = 1,
) -> list[UsuarioAdminResposta]:
    return servico.listar_ativos(
        busca=busca,
        perfil=perfil,
        limite=ajustar_limite_usuarios(limite),
        pagina=pagina,
    )


# Declarada antes de /usuarios/{usuario_id} para "resumo" não ser lido como UUID.
@router.get("/usuarios/resumo", response_model=ResumoUsuariosResposta)
def resumir(
    _: Administrador,
    servico: Servico,
    busca: Annotated[str | None, Query(max_length=150, description="Texto livre em nome ou e-mail")] = None,
    perfil: Perfil | None = None,
) -> ResumoUsuariosResposta:
    return servico.resumir_ativos(busca=busca, perfil=perfil)


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
