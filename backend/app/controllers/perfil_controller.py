"""Perfil do usuário logado."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response

from app.controllers.dependencias import UsuarioAtual, perfil_service
from app.dtos.auth_dto import MensagemResposta
from app.dtos.perfil_dto import PerfilAtualizacao, PerfilResposta, TrocaSenhaEntrada
from app.services.perfil_service import TAMANHO_MAXIMO_AVATAR, PerfilService


router = APIRouter(prefix="/me", tags=["Perfil"])
Servico = Annotated[PerfilService, Depends(perfil_service)]


@router.get("", response_model=PerfilResposta)
def consultar(usuario: UsuarioAtual) -> PerfilResposta:
    return PerfilService.consultar(usuario)


@router.put("", response_model=PerfilResposta)
def atualizar(dados: PerfilAtualizacao, usuario: UsuarioAtual, servico: Servico) -> PerfilResposta:
    return servico.atualizar(usuario, dados)


@router.put("/senha", response_model=MensagemResposta)
def trocar_senha(dados: TrocaSenhaEntrada, usuario: UsuarioAtual, servico: Servico) -> MensagemResposta:
    return servico.trocar_senha(usuario, dados)


@router.get("/avatar")
def baixar_avatar(usuario: UsuarioAtual) -> Response:
    conteudo, tipo = PerfilService.obter_avatar(usuario)
    return Response(content=conteudo, media_type=tipo, headers={"Cache-Control": "private, max-age=300"})


@router.put("/avatar", response_model=PerfilResposta)
def trocar_avatar(usuario: UsuarioAtual, servico: Servico, arquivo: UploadFile = File(...)) -> PerfilResposta:
    # Lê no máximo 1 byte além do limite: um arquivo enorme não ocupa a memória inteira.
    conteudo = arquivo.file.read(TAMANHO_MAXIMO_AVATAR + 1)
    return servico.trocar_avatar(usuario, arquivo.content_type, conteudo)


@router.delete("/avatar", response_model=PerfilResposta)
def remover_avatar(usuario: UsuarioAtual, servico: Servico) -> PerfilResposta:
    return servico.remover_avatar(usuario)
