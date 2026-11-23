from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import PASTA_ARQUIVOS
from app.core.excecoes import ArquivoGrandeDemaisErro, NaoEncontradoErro, RegraDeNegocioErro, TipoDeArquivoInvalidoErro
from app.dtos.arquivo_dto import ArquivoResposta
from app.entities.usuario import Usuario
from app.repositories.ocorrencia_repository import OcorrenciaRepository
from app.services.ocorrencia_service import OcorrenciaService


TAMANHO_MAXIMO_ARQUIVO = 5 * 1024 * 1024
TIPOS_ARQUIVO_PERMITIDOS = {
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
    "image/webp": {".webp"},
    "video/mp4": {".mp4"},
}


class ArquivoService:
    """Anexos das ocorrências, gravados em disco na pasta `uploads/`."""

    def __init__(self, sessao: Session, pasta: Path = PASTA_ARQUIVOS) -> None:
        self.ocorrencias = OcorrenciaRepository(sessao)
        self.pasta = pasta

    def validar_envio(self, nome: str | None, tipo: str | None, tamanho: int | None) -> str:
        """Confere nome, tipo e tamanho informados antes de ler o conteúdo. Devolve a extensão."""
        if not nome:
            raise RegraDeNegocioErro("Selecione um arquivo válido.")
        extensao = Path(nome).suffix.lower()
        extensoes_permitidas = TIPOS_ARQUIVO_PERMITIDOS.get(tipo or "")
        if extensoes_permitidas is None or extensao not in extensoes_permitidas:
            raise TipoDeArquivoInvalidoErro("Envie apenas imagens JPG, PNG, WEBP ou vídeo MP4.")
        if tamanho is not None and tamanho > TAMANHO_MAXIMO_ARQUIVO:
            raise ArquivoGrandeDemaisErro("O arquivo deve ter no máximo 5 MB.")
        return extensao

    def salvar(self, nome: str, tipo: str | None, extensao: str, conteudo: bytes, url_base: str) -> ArquivoResposta:
        self.pasta.mkdir(parents=True, exist_ok=True)
        nome_armazenado = f"{uuid4()}{extensao}"
        if len(conteudo) > TAMANHO_MAXIMO_ARQUIVO:
            raise ArquivoGrandeDemaisErro("O arquivo deve ter no máximo 5 MB.")
        (self.pasta / nome_armazenado).write_bytes(conteudo)
        return ArquivoResposta(nome=nome, url=f"{url_base.rstrip('/')}/arquivos/{nome_armazenado}", tipo=tipo)

    def caminho_para_download(self, nome_armazenado: str, usuario: Usuario) -> Path:
        """Só entrega o arquivo a quem pode ver uma ocorrência que o tenha como anexo."""
        nome_seguro = Path(nome_armazenado).name == nome_armazenado
        if not nome_seguro or not self._usuario_pode_acessar(nome_armazenado, usuario):
            raise NaoEncontradoErro("Arquivo não encontrado.")
        arquivo = self.pasta / nome_armazenado
        if not arquivo.is_file():
            raise NaoEncontradoErro("Arquivo não encontrado.")
        return arquivo

    def _usuario_pode_acessar(self, nome_armazenado: str, usuario: Usuario) -> bool:
        """O banco devolve só as ocorrências cujo JSON de anexos cita o arquivo; aqui se confere a URL exata."""
        sufixo = f"/arquivos/{nome_armazenado}"
        return any(
            OcorrenciaService.pode_acessar(ocorrencia, usuario)
            for ocorrencia in self.ocorrencias.listar_que_citam_arquivo(nome_armazenado)
            if any(isinstance(anexo, dict) and str(anexo.get("url", "")).endswith(sufixo) for anexo in ocorrencia.anexos or [])
        )
