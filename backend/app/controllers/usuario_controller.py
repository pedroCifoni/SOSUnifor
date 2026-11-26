from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse

from app.controllers.dependencias import Administrador, UsuarioAtual, usuario_service
from app.core.exportacao import criar_exportador
from app.dtos.auth_dto import MensagemResposta
from app.dtos.usuario_dto import (
    LIMITE_MAXIMO_USUARIOS,
    LIMITE_PADRAO_USUARIOS,
    Perfil,
    ResumoUsuariosResposta,
    SegurancaNotificadaResposta,
    SituacaoConta,
    UsuarioAdminResposta,
    UsuarioAtualizacao,
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
    situacao: Annotated[SituacaoConta, Query(description="Contas ativas (padrão) ou desativadas")] = "ativos",
    limite: Annotated[int, Query(description=f"1 a {LIMITE_MAXIMO_USUARIOS}; fora disso é ajustado")] = LIMITE_PADRAO_USUARIOS,
    pagina: Annotated[int, Query(ge=1, description="Página da listagem (a partir de 1)")] = 1,
) -> list[UsuarioAdminResposta]:
    return servico.listar(
        desativados=situacao == "desativados",
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
    situacao: Annotated[SituacaoConta, Query(description="Contas ativas (padrão) ou desativadas")] = "ativos",
) -> ResumoUsuariosResposta:
    return servico.resumir(desativados=situacao == "desativados", busca=busca, perfil=perfil)


@router.get("/usuarios/exportar.{formato}")
def exportar(
    formato: Literal["csv", "pdf"],
    _: Administrador,
    servico: Servico,
    busca: Annotated[str | None, Query(max_length=150)] = None,
    perfil: Perfil | None = None,
    situacao: SituacaoConta = "ativos",
) -> StreamingResponse:
    """Exporta a lista de contas (mesmos filtros da tela) em CSV ou PDF."""
    exportador = criar_exportador(formato)
    conteudo = servico.exportar(exportador, desativados=situacao == "desativados", busca=busca, perfil=perfil)
    return StreamingResponse(
        conteudo,
        media_type=exportador.media_type,
        headers={"Content-Disposition": f'attachment; filename="usuarios_{situacao}.{exportador.extensao}"'},
    )


@router.get("/usuarios/segurancas", response_model=list[UsuarioResposta])
def listar_segurancas(usuario: UsuarioAtual, servico: Servico) -> list[UsuarioResposta]:
    return servico.listar_por_perfil("seguranca", com_email=usuario.tipo_usuario == "admin")


@router.get("/usuarios/tecnicos", response_model=list[UsuarioResposta])
def listar_tecnicos(usuario: UsuarioAtual, servico: Servico) -> list[UsuarioResposta]:
    return servico.listar_por_perfil("tecnico", com_email=usuario.tipo_usuario == "admin")


# Não há rota de criação aqui: as contas são criadas pelo próprio titular em POST /auth/cadastro.
@router.post("/usuarios/lote", response_model=UsuarioLoteResposta)
def salvar_em_lote(dados: UsuarioLoteEntrada, administrador: Administrador, servico: Servico) -> UsuarioLoteResposta:
    return servico.salvar_em_lote(dados, administrador)


@router.put("/usuarios/{usuario_id}", response_model=UsuarioAdminResposta)
def atualizar(usuario_id: UUID, dados: UsuarioAtualizacao, administrador: Administrador, servico: Servico) -> UsuarioAdminResposta:
    return servico.atualizar(usuario_id, dados, administrador)


@router.post("/usuarios/{usuario_id}/reativar", response_model=UsuarioAdminResposta)
def reativar(usuario_id: UUID, administrador: Administrador, servico: Servico) -> UsuarioAdminResposta:
    """Reativa uma conta desativada (não vale para contas anonimizadas a pedido do titular)."""
    return servico.reativar(usuario_id, administrador)


@router.post("/usuarios/{usuario_id}/reenviar-verificacao", response_model=MensagemResposta)
def reenviar_verificacao(usuario_id: UUID, _: Administrador, servico: Servico) -> MensagemResposta:
    return servico.reenviar_verificacao(usuario_id)


@router.delete("/usuarios/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir(usuario_id: UUID, administrador: Administrador, servico: Servico) -> None:
    servico.excluir(usuario_id, administrador)


@router.get("/segurancas/notificadas", response_model=list[SegurancaNotificadaResposta])
def listar_segurancas_notificadas(_: UsuarioAtual, servico: Servico) -> list[SegurancaNotificadaResposta]:
    return servico.listar_segurancas_notificadas()
