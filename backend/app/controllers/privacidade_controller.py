from typing import Annotated

from fastapi import APIRouter, Depends

from app.controllers.dependencias import UsuarioAtual, privacidade_service
from app.dtos.privacidade_dto import CienciaPrivacidadeEntrada, SituacaoPrivacidadeResposta
from app.services.privacidade_service import PrivacidadeService


router = APIRouter(prefix="/privacidade", tags=["Privacidade"])
Servico = Annotated[PrivacidadeService, Depends(privacidade_service)]


@router.get("/situacao", response_model=SituacaoPrivacidadeResposta)
def consultar_situacao(usuario: UsuarioAtual, servico: Servico) -> SituacaoPrivacidadeResposta:
    """Diz se o usuário logado já declarou ciência da versão vigente da Política de Privacidade."""
    return servico.situacao(usuario)


@router.post("/ciencia", response_model=SituacaoPrivacidadeResposta)
def registrar_ciencia(
    dados: CienciaPrivacidadeEntrada, usuario: UsuarioAtual, servico: Servico
) -> SituacaoPrivacidadeResposta:
    """Registra data e versão da política de que o usuário declarou ciência."""
    return servico.registrar_ciencia(dados, usuario)
