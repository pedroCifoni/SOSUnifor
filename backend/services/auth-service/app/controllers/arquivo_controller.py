from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, UploadFile, status
from fastapi.responses import FileResponse

from app.controllers.dependencias import UsuarioAtual, arquivo_service
from app.dtos.arquivo_dto import ArquivoResposta
from app.services.arquivo_service import ArquivoService


router = APIRouter(prefix="/arquivos", tags=["Arquivos"])
Servico = Annotated[ArquivoService, Depends(arquivo_service)]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ArquivoResposta)
async def enviar(
    requisicao: Request, _: UsuarioAtual, servico: Servico, arquivo: UploadFile = File(...)
) -> ArquivoResposta:
    extensao = servico.validar_envio(arquivo.filename, arquivo.content_type, arquivo.size)
    conteudo = await arquivo.read()
    return servico.salvar(arquivo.filename, arquivo.content_type, extensao, conteudo, str(requisicao.base_url))


@router.get("/{nome_armazenado}")
def baixar(nome_armazenado: str, usuario: UsuarioAtual, servico: Servico) -> FileResponse:
    caminho = servico.caminho_para_download(nome_armazenado, usuario)
    return FileResponse(caminho, filename=caminho.name, content_disposition_type="inline")
