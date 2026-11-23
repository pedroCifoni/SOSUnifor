from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.excecoes import ConflitoErro, NaoEncontradoErro, RegraDeNegocioErro
from app.core.seguranca import gerar_hash_senha
from app.dtos.auth_dto import MensagemResposta
from app.dtos.usuario_dto import (
    LIMITE_PADRAO_USUARIOS,
    ResumoUsuariosResposta,
    SegurancaNotificadaResposta,
    UsuarioAdminResposta,
    UsuarioAtualizacao,
    UsuarioEntrada,
    UsuarioLoteEntrada,
    UsuarioLoteResposta,
    UsuarioResposta,
)
from app.entities.usuario import Usuario
from app.repositories.token_redefinicao_senha_repository import TokenRedefinicaoSenhaRepository
from app.repositories.usuario_repository import UsuarioRepository
from app.services.email_service import EmailService
from app.services.verificacao_email_service import VerificacaoEmailService


class UsuarioService:
    def __init__(self, sessao: Session, emails: EmailService | None = None) -> None:
        self.sessao = sessao
        self.usuarios = UsuarioRepository(sessao)
        self.tokens_redefinicao = TokenRedefinicaoSenhaRepository(sessao)
        self.emails = emails or EmailService()
        self.verificacao = VerificacaoEmailService(sessao, self.emails)
        # Contas que mudaram de e-mail nesta operação: recebem o link no endereço novo após o commit.
        self._confirmacoes_pendentes: list[tuple[Usuario, str]] = []

    # ---------- consultas ----------
    def listar_ativos(
        self,
        *,
        busca: str | None = None,
        perfil: str | None = None,
        limite: int = LIMITE_PADRAO_USUARIOS,
        pagina: int = 1,
    ) -> list[UsuarioAdminResposta]:
        usuarios = self.usuarios.listar_ativos(busca=busca, perfil=perfil, limite=limite, pagina=pagina)
        return [UsuarioAdminResposta.de_entidade(usuario) for usuario in usuarios]

    def resumir_ativos(self, *, busca: str | None = None, perfil: str | None = None) -> ResumoUsuariosResposta:
        return ResumoUsuariosResposta(total=self.usuarios.contar_ativos(busca=busca, perfil=perfil))

    def listar_por_perfil(self, perfil: str) -> list[UsuarioResposta]:
        return [UsuarioResposta.de_entidade(usuario) for usuario in self.usuarios.listar_ativos_por_perfil(perfil)]

    def listar_segurancas_notificadas(self) -> list[SegurancaNotificadaResposta]:
        """Equipe de segurança acionada em um SOS. Viatura e distância ainda são simuladas."""
        return [
            SegurancaNotificadaResposta(
                id=str(seguranca.id),
                nome=seguranca.nome,
                viatura=f"Patrulha {indice:02d}",
                distancia_m=indice * 150,
                status="notificado",
            )
            for indice, seguranca in enumerate(self.usuarios.listar_ativos_por_perfil("seguranca"), start=1)
        ]

    # ---------- comandos ----------
    def criar(self, dados: UsuarioEntrada) -> UsuarioAdminResposta:
        usuario = self._novo_usuario(dados)
        self.sessao.flush()
        token = self.verificacao.emitir_token(usuario)
        self.sessao.commit()
        self.sessao.refresh(usuario)
        self._enviar_acesso(usuario, dados.senha, token)
        return UsuarioAdminResposta.de_entidade(usuario)

    def atualizar(self, usuario_id: UUID, dados: UsuarioAtualizacao, administrador: Usuario) -> UsuarioAdminResposta:
        usuario = self._buscar_ativo(usuario_id)
        novos_dados = dados.model_dump(exclude_unset=True)
        if not novos_dados:
            raise RegraDeNegocioErro("Envie ao menos um campo para atualizar.")
        self._aplicar_alteracoes(usuario, novos_dados, administrador)
        self.sessao.commit()
        self.sessao.refresh(usuario)
        self._enviar_confirmacoes_pendentes()
        return UsuarioAdminResposta.de_entidade(usuario)

    def reenviar_verificacao(self, usuario_id: UUID) -> MensagemResposta:
        return self.verificacao.reenviar_pelo_admin(self._buscar_ativo(usuario_id))

    def excluir(self, usuario_id: UUID, administrador: Usuario) -> None:
        self._desativar(self._buscar_ativo(usuario_id), administrador)
        self.sessao.commit()

    def salvar_em_lote(self, dados: UsuarioLoteEntrada, administrador: Usuario) -> UsuarioLoteResposta:
        """Aplica o rascunho do painel administrativo em uma única transação: tudo ou nada."""
        # O banco só enxerga as contas novas depois do flush; por isso e-mails repetidos dentro
        # do próprio lote são barrados aqui (antes viravam IntegrityError e HTTP 500).
        emails_do_lote = [c.email.lower().strip() for c in dados.criacoes] + [
            a.email.lower().strip() for a in dados.atualizacoes if a.email
        ]
        if len(emails_do_lote) != len(set(emails_do_lote)):
            raise ConflitoErro("Há e-mails repetidos entre os usuários salvos.")
        try:
            novos = [(self._novo_usuario(criacao), criacao.senha) for criacao in dados.criacoes]
            self.sessao.flush()
            criados = [(usuario, senha, self.verificacao.emitir_token(usuario)) for usuario, senha in novos]
            for atualizacao in dados.atualizacoes:
                usuario = self._buscar_ativo(UUID(atualizacao.id))
                novos_dados = atualizacao.model_dump(exclude={"id"}, exclude_unset=True)
                if not novos_dados.get("senha"):
                    novos_dados.pop("senha", None)
                self._aplicar_alteracoes(usuario, novos_dados, administrador)
            for usuario_id in dados.exclusoes:
                self._desativar(self._buscar_ativo(UUID(usuario_id)), administrador)
            self.sessao.commit()
        except Exception:
            self.sessao.rollback()
            self._confirmacoes_pendentes.clear()
            raise
        # Só depois do commit: ninguém recebe a senha de uma conta que acabou não sendo criada.
        for usuario, senha, token in criados:
            self._enviar_acesso(usuario, senha, token)
        self._enviar_confirmacoes_pendentes()
        return UsuarioLoteResposta(
            criadas=len(dados.criacoes), atualizadas=len(dados.atualizacoes), excluidas=len(dados.exclusoes)
        )

    # ---------- regras ----------
    def _enviar_acesso(self, usuario: Usuario, senha: str, token_verificacao: str) -> None:
        self.emails.enviar_boas_vindas(usuario.nome, usuario.email, senha, token_verificacao)

    def _enviar_confirmacoes_pendentes(self) -> None:
        for usuario, token in self._confirmacoes_pendentes:
            self.emails.enviar_confirmacao_email(usuario.nome, usuario.email, token)
        self._confirmacoes_pendentes.clear()

    def _trocar_email(self, usuario: Usuario, novo_email: str, administrador: Usuario) -> None:
        """E-mail novo precisa ser confirmado de novo; links antigos (confirmação e senha) deixam de valer."""
        email = self._email_disponivel(novo_email, usuario.id)
        if email == usuario.email:
            return
        # O admin que troca o próprio e-mail fica sem acesso até confirmá-lo. Se o endereço tiver um erro
        # de digitação, só outro admin (ativo e confirmado) consegue corrigir; sem ele, a troca é recusada.
        if usuario.id == administrador.id and self.usuarios.contar_admins_confirmados(exceto=usuario.id) == 0:
            raise RegraDeNegocioErro(
                "Para trocar o seu próprio e-mail, é preciso existir outro administrador com e-mail confirmado. "
                "Peça a ele para fazer a troca ou cadastre um antes."
            )
        agora = datetime.now(timezone.utc)
        usuario.email = email
        usuario.email_verificado_em = None
        self.tokens_redefinicao.invalidar_pendentes(usuario.id, agora)
        self._confirmacoes_pendentes.append((usuario, self.verificacao.emitir_token(usuario, agora)))

    def _novo_usuario(self, dados: UsuarioEntrada) -> Usuario:
        return self.usuarios.adicionar(
            Usuario(
                nome=dados.nome.strip(),
                email=self._email_disponivel(dados.email),
                senha_hash=gerar_hash_senha(dados.senha),
                tipo_usuario=dados.perfil,
            )
        )

    def _aplicar_alteracoes(self, usuario: Usuario, novos_dados: dict, administrador: Usuario) -> None:
        if usuario.id == administrador.id and "perfil" in novos_dados:
            raise RegraDeNegocioErro("Você não pode alterar o próprio perfil.")
        if novos_dados.get("email"):
            self._trocar_email(usuario, novos_dados["email"], administrador)
        if "nome" in novos_dados:
            usuario.nome = novos_dados["nome"].strip()
        if "perfil" in novos_dados:
            self._garantir_ao_menos_um_admin(usuario, novos_dados["perfil"])
            usuario.tipo_usuario = novos_dados["perfil"]
        if "senha" in novos_dados:
            usuario.senha_hash = gerar_hash_senha(novos_dados["senha"])

    def _desativar(self, usuario: Usuario, administrador: Usuario) -> None:
        """Exclusão lógica: o usuário some das listas, mas o histórico das ocorrências continua íntegro."""
        if usuario.id == administrador.id:
            raise RegraDeNegocioErro("Você não pode excluir a si mesmo.")
        self._garantir_ao_menos_um_admin(usuario)
        usuario.ativo = False
        # Links de confirmação de uma conta desativada não servem mais para nada.
        self.verificacao.tokens.apagar_do_usuario(usuario.id)

    def _buscar_ativo(self, usuario_id: UUID) -> Usuario:
        usuario = self.usuarios.buscar_por_id(usuario_id)
        if usuario is None or not usuario.ativo:
            raise NaoEncontradoErro("Usuário não encontrado.")
        return usuario

    def _email_disponivel(self, email: str, usuario_id: UUID | None = None) -> str:
        email_normalizado = email.lower().strip()
        existente = self.usuarios.buscar_por_email(email_normalizado)
        if existente is not None and existente.id != usuario_id:
            raise ConflitoErro("Já existe um usuário com este e-mail.")
        return email_normalizado

    def _garantir_ao_menos_um_admin(self, usuario: Usuario, novo_perfil: str | None = None) -> None:
        if usuario.tipo_usuario != "admin" or novo_perfil == "admin":
            return
        if self.usuarios.contar_ativos_por_perfil("admin") <= 1:
            raise RegraDeNegocioErro("Deve existir ao menos um administrador.")
