"""Confirmação de que a pessoa é dona do e-mail da conta.

Segue o mesmo padrão dos links de redefinição de senha: token aleatório de uso único,
só o hash SHA-256 no banco, prazo de validade e um novo pedido invalida os anteriores.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import configuracoes
from app.core.excecoes import MuitasTentativasErro, RegraDeNegocioErro
from app.dtos.auth_dto import MensagemResposta, ReenviarVerificacaoEntrada, VerificarEmailEntrada
from app.entities.token_verificacao_email import TokenVerificacaoEmail
from app.entities.usuario import Usuario
from app.repositories.token_verificacao_email_repository import TokenVerificacaoEmailRepository
from app.repositories.usuario_repository import UsuarioRepository
from app.services.email_service import EmailService


# Limite de links de confirmação por conta, para ninguém encher a caixa de e-mail de outra pessoa.
LIMITE_ENVIOS_VERIFICACAO = 3
JANELA_ENVIOS_VERIFICACAO = timedelta(hours=1)
# Links vencidos há mais que isto são apagados (bem depois da janela do limite de envios).
RETENCAO_LINKS_VENCIDOS = timedelta(days=7)

# Mesma resposta exista ou não a conta (e esteja ou não confirmada): a tela não revela quais e-mails existem.
MENSAGEM_REENVIO_VERIFICACAO = (
    "Se o e-mail estiver cadastrado e ainda não tiver sido confirmado, "
    "você receberá em instantes um novo link de confirmação."
)
MENSAGEM_LINK_INVALIDO = "Este link de confirmação é inválido ou expirou. Peça um novo na tela de login."
MENSAGEM_EMAIL_CONFIRMADO = "E-mail confirmado. Você já pode entrar no sistema."


def hash_do_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def hash_do_endereco(token: str, email: str) -> str:
    """Prende o link ao endereço sem guardá-lo: só quem tem o token consegue refazer este hash."""
    return hashlib.sha256(f"{token}:{email}".encode()).hexdigest()


class VerificacaoEmailService:
    def __init__(self, sessao: Session, emails: EmailService | None = None) -> None:
        self.sessao = sessao
        self.usuarios = UsuarioRepository(sessao)
        self.tokens = TokenVerificacaoEmailRepository(sessao)
        self.emails = emails or EmailService()

    # ---------- emissão (usada também pelo cadastro de usuários) ----------
    def emitir_token(self, usuario: Usuario, agora: datetime | None = None) -> str:
        """Gera um link novo para o e-mail atual da conta e invalida os anteriores. Não faz commit.

        A conta precisa já ter id (depois do flush). O token devolvido só deve ser enviado após o commit.
        """
        agora = agora or datetime.now(timezone.utc)
        token = secrets.token_urlsafe(32)
        self.tokens.apagar_vencidos_antes_de(agora - RETENCAO_LINKS_VENCIDOS)
        self.tokens.invalidar_pendentes(usuario.id, agora)
        self.tokens.adicionar(
            TokenVerificacaoEmail(
                usuario_id=usuario.id,
                email_hash=hash_do_endereco(token, usuario.email),
                token_hash=hash_do_token(token),
                criado_em=agora,
                expira_em=agora + timedelta(hours=configuracoes.verificacao_email_expira_horas),
            )
        )
        return token

    def limite_atingido(self, usuario: Usuario, agora: datetime) -> bool:
        """Trava a conta antes de contar: pedidos simultâneos esperam um ao outro e não furam o limite."""
        self.usuarios.travar(usuario.id)
        enviados = self.tokens.contar_pedidos_desde(usuario.id, agora - JANELA_ENVIOS_VERIFICACAO)
        return enviados >= LIMITE_ENVIOS_VERIFICACAO

    # ---------- pedidos ----------
    def reenviar(self, dados: ReenviarVerificacaoEntrada) -> MensagemResposta:
        """Reenvio pedido na tela de login. A resposta é sempre a mesma."""
        resposta = MensagemResposta(mensagem=MENSAGEM_REENVIO_VERIFICACAO)
        usuario = self.usuarios.buscar_por_email(dados.email)
        if usuario is None or not usuario.ativo or usuario.email_verificado_em is not None:
            return resposta
        agora = datetime.now(timezone.utc)
        if self.limite_atingido(usuario, agora):
            return resposta
        self._emitir_e_enviar(usuario, agora)
        return resposta

    def reenviar_pelo_admin(self, usuario: Usuario) -> MensagemResposta:
        """Reenvio pedido pelo administrador: aqui não há o que esconder, então os erros são explícitos."""
        if usuario.email_verificado_em is not None:
            raise RegraDeNegocioErro("O e-mail desta conta já foi confirmado.")
        agora = datetime.now(timezone.utc)
        if self.limite_atingido(usuario, agora):
            raise MuitasTentativasErro("Já foram enviados vários links nesta última hora. Tente novamente mais tarde.")
        self._emitir_e_enviar(usuario, agora)
        return MensagemResposta(mensagem=f"Enviamos um novo link de confirmação para {usuario.email}.")

    def confirmar(self, dados: VerificarEmailEntrada) -> MensagemResposta:
        agora = datetime.now(timezone.utc)
        registro = self.tokens.buscar_por_hash_para_uso(hash_do_token(dados.token))
        if registro is None or registro.usado_em is not None or registro.expira_em <= agora:
            raise RegraDeNegocioErro(MENSAGEM_LINK_INVALIDO)
        usuario = self.usuarios.buscar_por_id(registro.usuario_id)
        # O link comprova o endereço para o qual foi enviado; se a conta mudou de e-mail, não serve mais.
        if usuario is None or not usuario.ativo or hash_do_endereco(dados.token, usuario.email) != registro.email_hash:
            raise RegraDeNegocioErro(MENSAGEM_LINK_INVALIDO)

        if usuario.email_verificado_em is None:
            usuario.email_verificado_em = agora
        self.tokens.invalidar_pendentes(usuario.id, agora)
        self.sessao.commit()
        return MensagemResposta(mensagem=MENSAGEM_EMAIL_CONFIRMADO)

    def _emitir_e_enviar(self, usuario: Usuario, agora: datetime) -> None:
        token = self.emitir_token(usuario, agora)
        self.sessao.commit()
        self.emails.enviar_confirmacao_email(usuario.nome, usuario.email, token)
