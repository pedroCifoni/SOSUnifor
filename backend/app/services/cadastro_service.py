"""Autocadastro: qualquer pessoa com e-mail @unifor.br cria a própria conta, sempre com o perfil "usuario".

Regras de segurança:
- A resposta é sempre a mesma, exista ou não uma conta com o e-mail (não revela quem está cadastrado).
  O hash Argon2 da senha é calculado em todos os casos, para o tempo de resposta também não revelar.
- A conta nasce sem e-mail confirmado e não entra até a pessoa abrir o link enviado ao endereço
  e digitar a senha escolhida (veja VerificacaoEmailService.confirmar).
- Cadastrar de novo um e-mail ainda não confirmado substitui nome e senha e manda um link novo
  (os anteriores deixam de valer). Isso respeita o mesmo limite de envios por hora do reenvio.
- E-mail já confirmado ou conta desativada: nada muda e nada é enviado.
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.aspectos import auditar
from app.core.excecoes import RegraDeNegocioErro
from app.core.privacidade import VERSAO_TERMOS
from app.core.seguranca import gerar_hash_senha
from app.dtos.auth_dto import CadastroEntrada, MensagemResposta
from app.entities.usuario import Usuario
from app.repositories.usuario_repository import UsuarioRepository
from app.services.email_service import EmailService
from app.services.verificacao_email_service import VerificacaoEmailService


PERFIL_DO_AUTOCADASTRO = "usuario"

MENSAGEM_CADASTRO = (
    "Se este e-mail ainda não tiver uma conta confirmada, enviamos para ele um link de confirmação. "
    "Abra o link e digite a sua senha para ativar a conta. Se você já tem conta, entre ou use "
    "\"Esqueci minha senha\"."
)
MENSAGEM_TERMOS_DESATUALIZADOS = "A Política de Privacidade foi atualizada. Recarregue a página e leia a versão atual."


def _conta_afetada(ponto, resultado) -> UUID | None:
    return resultado


class CadastroService:
    def __init__(self, sessao: Session, emails: EmailService | None = None) -> None:
        self.sessao = sessao
        self.usuarios = UsuarioRepository(sessao)
        self.emails = emails or EmailService()
        self.verificacao = VerificacaoEmailService(sessao, self.emails)

    def cadastrar(self, dados: CadastroEntrada) -> MensagemResposta:
        if dados.versao_termos != VERSAO_TERMOS:
            raise RegraDeNegocioErro(MENSAGEM_TERMOS_DESATUALIZADOS)

        # Sempre calculado (antes de saber se a conta existe): mantém o tempo de resposta parecido nos dois casos.
        senha_hash = gerar_hash_senha(dados.senha)
        agora = datetime.now(timezone.utc)
        existente = self.usuarios.buscar_por_email(dados.email)

        if existente is None:
            self._criar_conta(dados, senha_hash, agora)
        elif existente.ativo and existente.email_verificado_em is None:
            self._refazer_cadastro_pendente(existente, dados, senha_hash, agora)
        return MensagemResposta(mensagem=MENSAGEM_CADASTRO)

    # O próprio titular é o ator: a conta acabou de ser criada por ele, sem login.
    @auditar(
        "usuario.cadastrar",
        entidade="usuario",
        entidade_id=_conta_afetada,
        ator=_conta_afetada,
        registrar_se=lambda _ponto, resultado: resultado is not None,
    )
    def _criar_conta(self, dados: CadastroEntrada, senha_hash: str, agora: datetime) -> UUID | None:
        usuario = self.usuarios.adicionar(
            Usuario(
                nome=dados.nome,
                email=dados.email,
                senha_hash=senha_hash,
                tipo_usuario=PERFIL_DO_AUTOCADASTRO,
                termos_versao=VERSAO_TERMOS,
                termos_aceitos_em=agora,
            )
        )
        try:
            self.sessao.flush()
        except IntegrityError:
            # Dois cadastros simultâneos com o mesmo e-mail: o outro venceu. A resposta continua a mesma.
            self.sessao.rollback()
            return None
        token = self.verificacao.emitir_token(usuario, agora)
        self.sessao.commit()
        # Só depois do commit: ninguém recebe link de uma conta que não foi gravada.
        self.emails.enviar_confirmacao_email(usuario.nome, usuario.email, token)
        return usuario.id

    @auditar(
        "usuario.refazer_cadastro",
        entidade="usuario",
        entidade_id=_conta_afetada,
        ator=_conta_afetada,
        registrar_se=lambda _ponto, resultado: resultado is not None,
    )
    def _refazer_cadastro_pendente(
        self, usuario: Usuario, dados: CadastroEntrada, senha_hash: str, agora: datetime
    ) -> UUID | None:
        """Conta ainda não confirmada: quem cadastra de novo define nome e senha e recebe um link novo.

        Não dá acesso a ninguém: a conta só é ativada por quem abre o link (dono do e-mail) E sabe a
        senha gravada. Se outra pessoa cadastrou o e-mail antes, o dono substitui a senha aqui.
        """
        if self.verificacao.limite_atingido(usuario, agora):
            self.sessao.rollback()  # libera a trava da conta
            return None
        usuario.nome = dados.nome
        usuario.senha_hash = senha_hash
        usuario.termos_versao = VERSAO_TERMOS
        usuario.termos_aceitos_em = agora
        token = self.verificacao.emitir_token(usuario, agora)  # invalida os links anteriores
        self.sessao.commit()
        self.emails.enviar_confirmacao_email(usuario.nome, usuario.email, token)
        return usuario.id
