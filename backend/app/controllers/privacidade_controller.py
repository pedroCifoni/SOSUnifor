"""LGPD: ciência da Política de Privacidade e direitos do titular (art. 18)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.controllers.dependencias import Administrador, UsuarioAtual, privacidade_service
from app.dtos.privacidade_dto import (
    AceiteTermosEntrada,
    AnonimizacaoResposta,
    DadosTitularResposta,
    PedidoExclusaoResposta,
    SolicitacaoExclusaoEntrada,
    SolicitacaoExclusaoResposta,
    TermosResposta,
)
from app.services.privacidade_service import PrivacidadeService


router = APIRouter(tags=["Privacidade (LGPD)"])
Servico = Annotated[PrivacidadeService, Depends(privacidade_service)]


@router.get("/me/termos", response_model=TermosResposta)
def situacao_dos_termos(usuario: UsuarioAtual) -> TermosResposta:
    return PrivacidadeService.situacao_dos_termos(usuario)


@router.post("/me/termos", response_model=TermosResposta)
def aceitar_termos(dados: AceiteTermosEntrada, usuario: UsuarioAtual, servico: Servico) -> TermosResposta:
    return servico.aceitar_termos(usuario, dados)


@router.get("/me/dados", response_model=DadosTitularResposta)
def exportar_dados(usuario: UsuarioAtual, servico: Servico) -> DadosTitularResposta:
    """Cópia dos dados do próprio titular em JSON (acesso e portabilidade)."""
    return servico.exportar_dados(usuario)


@router.post("/me/solicitar-exclusao", response_model=SolicitacaoExclusaoResposta)
def solicitar_exclusao(
    dados: SolicitacaoExclusaoEntrada, usuario: UsuarioAtual, servico: Servico
) -> SolicitacaoExclusaoResposta:
    return servico.solicitar_exclusao(usuario, dados)


# Declarada antes de qualquer /usuarios/{usuario_id} para "pedidos-exclusao" não ser lido como id.
@router.get("/usuarios/pedidos-exclusao", response_model=list[PedidoExclusaoResposta])
def listar_pedidos_de_exclusao(_: Administrador, servico: Servico) -> list[PedidoExclusaoResposta]:
    return servico.listar_pedidos_de_exclusao()


@router.post("/usuarios/{usuario_id}/anonimizar", response_model=AnonimizacaoResposta)
def anonimizar(usuario_id: UUID, administrador: Administrador, servico: Servico) -> AnonimizacaoResposta:
    return servico.anonimizar(usuario_id, administrador)
