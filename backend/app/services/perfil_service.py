"""Perfil do próprio usuário: consultar, corrigir o nome, trocar a senha e a foto."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.aspectos import auditar
from app.core.excecoes import ArquivoGrandeDemaisErro, NaoEncontradoErro, SenhaNaoConfereErro, TipoDeArquivoInvalidoErro
from app.core.seguranca import conferir_senha, gerar_hash_senha
from app.dtos.auth_dto import MensagemResposta
from app.dtos.perfil_dto import PerfilAtualizacao, PerfilResposta, TrocaSenhaEntrada
from app.entities.usuario import Usuario
from app.repositories.sessao_repository import TokenSessaoRepository
from app.services.email_service import EmailService


TAMANHO_MAXIMO_AVATAR = 1024 * 1024
# Assinatura (primeiros bytes) de cada formato aceito: o tipo informado pelo navegador não basta.
ASSINATURAS_AVATAR = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/webp": (b"RIFF",),
}


class PerfilService:
    def __init__(self, sessao: Session, emails: EmailService | None = None) -> None:
        self.sessao = sessao
        self.emails = emails or EmailService()

    @staticmethod
    def consultar(usuario: Usuario) -> PerfilResposta:
        return PerfilResposta.de_entidade(usuario)

    @auditar("perfil.editar", entidade="usuario", entidade_id="usuario.id", ator="usuario.id")
    def atualizar(self, usuario: Usuario, dados: PerfilAtualizacao) -> PerfilResposta:
        usuario.nome = dados.nome
        self.sessao.commit()
        return PerfilResposta.de_entidade(usuario)

    @auditar("perfil.trocar_senha", entidade="usuario", entidade_id="usuario.id", ator="usuario.id")
    def trocar_senha(self, usuario: Usuario, dados: TrocaSenhaEntrada) -> MensagemResposta:
        if not conferir_senha(dados.senha_atual, usuario.senha_hash):
            raise SenhaNaoConfereErro("A senha atual não confere.")
        usuario.senha_hash = gerar_hash_senha(dados.nova_senha)
        # As outras sessões abertas deixam de renovar; esta continua até o access token vencer.
        TokenSessaoRepository(self.sessao).revogar_todos(usuario.id, datetime.now(timezone.utc))
        self.sessao.commit()
        self.emails.enviar_aviso_senha_alterada(usuario.nome, usuario.email)
        return MensagemResposta(mensagem="Senha alterada.")

    @auditar("perfil.trocar_foto", entidade="usuario", entidade_id="usuario.id", ator="usuario.id")
    def trocar_avatar(self, usuario: Usuario, tipo: str | None, conteudo: bytes) -> PerfilResposta:
        assinaturas = ASSINATURAS_AVATAR.get(tipo or "")
        if assinaturas is None or not conteudo.startswith(assinaturas):
            raise TipoDeArquivoInvalidoErro("Envie uma imagem JPG, PNG ou WEBP.")
        if tipo == "image/webp" and conteudo[8:12] != b"WEBP":
            raise TipoDeArquivoInvalidoErro("Envie uma imagem JPG, PNG ou WEBP.")
        if len(conteudo) > TAMANHO_MAXIMO_AVATAR:
            raise ArquivoGrandeDemaisErro("A foto deve ter no máximo 1 MB.")
        usuario.avatar = conteudo
        usuario.avatar_tipo = tipo
        self.sessao.commit()
        return PerfilResposta.de_entidade(usuario)

    @auditar("perfil.remover_foto", entidade="usuario", entidade_id="usuario.id", ator="usuario.id")
    def remover_avatar(self, usuario: Usuario) -> PerfilResposta:
        usuario.avatar = None
        usuario.avatar_tipo = None
        self.sessao.commit()
        return PerfilResposta.de_entidade(usuario)

    @staticmethod
    def obter_avatar(usuario: Usuario) -> tuple[bytes, str]:
        if usuario.avatar is None or usuario.avatar_tipo is None:
            raise NaoEncontradoErro("Nenhuma foto de perfil.")
        return usuario.avatar, usuario.avatar_tipo
