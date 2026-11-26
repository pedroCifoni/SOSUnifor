import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.aspectos import PontoDeJuncao, auditar
from app.core.config import configuracoes
from app.core.excecoes import (
    AcessoNegadoErro,
    EmailNaoVerificadoErro,
    MuitasTentativasErro,
    NaoAutenticadoErro,
    RegraDeNegocioErro,
)
from app.core.seguranca import conferir_senha, criar_token, gerar_hash_senha, ler_id_do_token
from app.dtos.auth_dto import (
    EsqueciSenhaEntrada,
    LoginEntrada,
    MensagemResposta,
    RedefinirSenhaEntrada,
    RenovarSessaoEntrada,
    TokenResposta,
)
from app.entities.sessao import TokenSessao
from app.entities.token_redefinicao_senha import TokenRedefinicaoSenha
from app.entities.usuario import Usuario
from app.repositories.sessao_repository import TentativaLoginRepository, TokenSessaoRepository
from app.repositories.token_redefinicao_senha_repository import TokenRedefinicaoSenhaRepository
from app.repositories.token_verificacao_email_repository import TokenVerificacaoEmailRepository
from app.repositories.usuario_repository import UsuarioRepository
from app.services.email_service import EmailService


# Intervalo mínimo entre duas gravações de `ultimo_acesso`, para não escrever no banco a cada requisição.
INTERVALO_REGISTRO_ACESSO = timedelta(seconds=20)

# Limite de pedidos de "esqueci minha senha" por conta, para impedir que alguém encha a caixa de e-mail de outra pessoa.
LIMITE_PEDIDOS_REDEFINICAO = 3
JANELA_PEDIDOS_REDEFINICAO = timedelta(hours=1)

# Mesma resposta exista ou não a conta: assim a tela não revela quais e-mails estão cadastrados.
MENSAGEM_PEDIDO_REDEFINICAO = (
    "Se o e-mail estiver cadastrado, você receberá em instantes um link para criar uma nova senha."
)
MENSAGEM_LINK_INVALIDO = "Este link de redefinição é inválido ou expirou. Peça um novo na tela de login."
MENSAGEM_MUITAS_TENTATIVAS = "Muitas tentativas de login. Aguarde alguns minutos e tente de novo."
MENSAGEM_SESSAO_INVALIDA = "Sessão expirada. Entre novamente."
MENSAGEM_EMAIL_NAO_VERIFICADO = (
    "Seu e-mail ainda não foi confirmado. Use o link que enviamos para a sua caixa de entrada ou peça um novo."
)


def _hash_do_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _dono_do_link(ponto: PontoDeJuncao) -> UUID | None:
    return ponto.lembrar("dono_do_link", lambda: ponto.instancia.dono_do_link(ponto.resolver("dados.token")))


class AuthService:
    def __init__(self, sessao: Session, emails: EmailService | None = None) -> None:
        self.sessao = sessao
        self.usuarios = UsuarioRepository(sessao)
        self.tokens_redefinicao = TokenRedefinicaoSenhaRepository(sessao)
        self.tokens_verificacao = TokenVerificacaoEmailRepository(sessao)
        self.tokens_sessao = TokenSessaoRepository(sessao)
        self.tentativas = TentativaLoginRepository(sessao)
        self.emails = emails or EmailService()

    def entrar(self, dados: LoginEntrada, ip: str | None = None) -> TokenResposta:
        agora = datetime.now(timezone.utc)
        email_hash = _hash_do_token(dados.email.lower().strip())
        # Força bruta: barra antes do Argon2, por e-mail (uma conta) e por IP (várias contas).
        desde = agora - timedelta(minutes=configuracoes.login_janela_falhas_minutos)
        if self.tentativas.contar_por_email(email_hash, desde) >= configuracoes.login_max_falhas_por_email or (
            ip and self.tentativas.contar_por_ip(ip, desde) >= configuracoes.login_max_falhas_por_ip
        ):
            raise MuitasTentativasErro(MENSAGEM_MUITAS_TENTATIVAS)

        usuario = self.usuarios.buscar_por_email(dados.email)
        # Devolve a conexão ao pool ANTES do Argon2: o hash é lento de propósito (e mais ainda com a
        # CPU disputada) e não precisa do banco. Segurá-la esgotava o pool sob muitos logins.
        # close() não expira os atributos já carregados, então `usuario` continua legível.
        self.sessao.close()
        if usuario is None or not usuario.ativo or not conferir_senha(dados.senha, usuario.senha_hash):
            self.tentativas.registrar(email_hash, ip, agora)
            self.sessao.commit()
            raise NaoAutenticadoErro("E-mail ou senha inválidos.")
        # Só depois de a senha conferir: assim esta resposta não ajuda ninguém a descobrir senhas.
        if usuario.email_verificado_em is None:
            raise EmailNaoVerificadoErro(MENSAGEM_EMAIL_NAO_VERIFICADO)
        self.tentativas.limpar_do_email(email_hash)
        refresh_token = self._emitir_refresh_token(usuario.id, agora)
        self.sessao.commit()
        return TokenResposta(token=criar_token(usuario), refresh_token=refresh_token)

    # ---------- sessão (refresh token com rotação) ----------
    def _emitir_refresh_token(self, usuario_id: UUID, agora: datetime) -> str:
        token = secrets.token_urlsafe(32)
        self.tokens_sessao.adicionar(
            TokenSessao(
                usuario_id=usuario_id,
                token_hash=_hash_do_token(token),
                criado_em=agora,
                expira_em=agora + timedelta(days=configuracoes.refresh_token_expire_dias),
            )
        )
        return token

    def renovar(self, dados: RenovarSessaoEntrada) -> TokenResposta:
        """Troca um refresh token válido por um novo par de tokens (o antigo deixa de valer)."""
        agora = datetime.now(timezone.utc)
        registro = self.tokens_sessao.buscar_por_hash_para_uso(_hash_do_token(dados.refresh_token))
        if registro is None or registro.expira_em <= agora:
            raise NaoAutenticadoErro(MENSAGEM_SESSAO_INVALIDA)
        if registro.revogado_em is not None:
            # Token já usado de novo: alguém tem uma cópia. Encerra todas as sessões da conta.
            self.tokens_sessao.revogar_todos(registro.usuario_id, agora)
            self.sessao.commit()
            raise NaoAutenticadoErro(MENSAGEM_SESSAO_INVALIDA)
        usuario = self.usuarios.buscar_por_id(registro.usuario_id)
        if usuario is None or not usuario.ativo or usuario.email_verificado_em is None:
            raise NaoAutenticadoErro(MENSAGEM_SESSAO_INVALIDA)
        registro.revogado_em = agora
        novo = self._emitir_refresh_token(usuario.id, agora)
        self.sessao.commit()
        # O access token novo traz nome e perfil atualizados (ex.: depois de editar o perfil).
        return TokenResposta(token=criar_token(usuario), refresh_token=novo)

    def sair(self, dados: RenovarSessaoEntrada) -> None:
        """Logout: revoga o refresh token desta sessão. Idempotente e sem revelar se o token existia."""
        registro = self.tokens_sessao.buscar_por_hash_para_uso(_hash_do_token(dados.refresh_token))
        if registro is not None and registro.revogado_em is None:
            registro.revogado_em = datetime.now(timezone.utc)
            self.sessao.commit()

    # ---------- esqueci minha senha ----------
    def solicitar_redefinicao_senha(self, dados: EsqueciSenhaEntrada) -> MensagemResposta:
        """Gera um token de uso único e envia o link por e-mail. A resposta é sempre a mesma."""
        resposta = MensagemResposta(mensagem=MENSAGEM_PEDIDO_REDEFINICAO)
        usuario = self.usuarios.buscar_por_email(dados.email)
        if usuario is None or not usuario.ativo:
            return resposta

        agora = datetime.now(timezone.utc)
        if self.tokens_redefinicao.contar_pedidos_desde(usuario.id, agora - JANELA_PEDIDOS_REDEFINICAO) >= LIMITE_PEDIDOS_REDEFINICAO:
            return resposta

        token = secrets.token_urlsafe(32)
        self.tokens_redefinicao.invalidar_pendentes(usuario.id, agora)
        self.tokens_redefinicao.adicionar(
            TokenRedefinicaoSenha(
                usuario_id=usuario.id,
                token_hash=_hash_do_token(token),
                criado_em=agora,
                expira_em=agora + timedelta(minutes=configuracoes.redefinicao_senha_expira_minutos),
            )
        )
        self.sessao.commit()
        self.emails.enviar_redefinicao_senha(usuario.nome, usuario.email, token)
        return resposta

    # Rota pública: tentativas com um link que nem existe não são auditadas (ator e entidade
    # seriam nulos), senão qualquer script anônimo encheria a trilha. O dono do link é
    # consultado uma vez só por chamada (memória do ponto de junção).
    @auditar(
        "auth.redefinir_senha",
        entidade="usuario",
        entidade_id=lambda ponto, _: _dono_do_link(ponto),
        ator=lambda ponto, _: _dono_do_link(ponto),
        registrar_se=lambda ponto, _: _dono_do_link(ponto) is not None,
    )
    def redefinir_senha(self, dados: RedefinirSenhaEntrada) -> MensagemResposta:
        agora = datetime.now(timezone.utc)
        registro = self.tokens_redefinicao.buscar_por_hash_para_uso(_hash_do_token(dados.token))
        if registro is None or registro.usado_em is not None or registro.expira_em <= agora:
            raise RegraDeNegocioErro(MENSAGEM_LINK_INVALIDO)
        usuario = self.usuarios.buscar_por_id(registro.usuario_id)
        if usuario is None or not usuario.ativo:
            raise RegraDeNegocioErro(MENSAGEM_LINK_INVALIDO)

        usuario.senha_hash = gerar_hash_senha(dados.nova_senha)
        self.tokens_redefinicao.invalidar_pendentes(usuario.id, agora)
        # Senha nova: as sessões abertas (talvez de quem descobriu a antiga) deixam de renovar.
        self.tokens_sessao.revogar_todos(usuario.id, agora)
        # O link chegou à caixa de entrada da conta, então também comprova que o e-mail é dela.
        if usuario.email_verificado_em is None:
            usuario.email_verificado_em = agora
            self.tokens_verificacao.invalidar_pendentes(usuario.id, agora)
        self.sessao.commit()
        self.emails.enviar_aviso_senha_alterada(usuario.nome, usuario.email)
        return MensagemResposta(mensagem="Senha alterada. Você já pode entrar com a nova senha.")

    def dono_do_link(self, token: str | None) -> UUID | None:
        """Id da conta dona de um link de redefinição (usado ou não); None se o link não existe."""
        return self.tokens_redefinicao.buscar_usuario_id_por_hash(_hash_do_token(token)) if token else None

    def usuario_do_token(self, token: str | None) -> Usuario:
        """Identifica o usuário do token e registra o último acesso (usado para saber quem está online)."""
        if token is None:
            raise NaoAutenticadoErro("Autenticação obrigatória.")
        usuario = self.usuarios.buscar_por_id(ler_id_do_token(token))
        if usuario is None or not usuario.ativo:
            raise NaoAutenticadoErro("Usuário sem acesso.")
        # Vale também para sessões já abertas: se o admin trocar o e-mail da conta, o acesso para na hora.
        if usuario.email_verificado_em is None:
            raise EmailNaoVerificadoErro(MENSAGEM_EMAIL_NAO_VERIFICADO)
        agora = datetime.now(timezone.utc)
        if usuario.ultimo_acesso is None or agora - usuario.ultimo_acesso >= INTERVALO_REGISTRO_ACESSO:
            usuario.ultimo_acesso = agora
            self.sessao.commit()
        return usuario

    @staticmethod
    def exigir_perfil(usuario: Usuario, perfis: tuple[str, ...]) -> Usuario:
        if usuario.tipo_usuario not in perfis:
            raise AcessoNegadoErro("Você não tem permissão para esta ação.")
        return usuario
