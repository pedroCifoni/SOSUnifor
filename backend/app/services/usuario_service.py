"""Gestão das contas pelo administrador.

As contas são criadas pelo próprio titular (CadastroService, POST /auth/cadastro). Aqui o administrador
só consulta, muda o perfil, corrige o nome, desativa e reativa contas. E-mail e senha pertencem ao titular:
o e-mail é comprovado por ele (link de confirmação) e a senha só ele conhece ("Esqueci minha senha").
"""

from collections.abc import Iterator
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.aspectos import auditar, nomes_dos_campos_enviados
from app.core.excecoes import NaoEncontradoErro, RegraDeNegocioErro
from app.core.exportacao import DocumentoTabular, Exportador
from app.dtos.auth_dto import MensagemResposta
from app.dtos.usuario_dto import (
    LIMITE_PADRAO_USUARIOS,
    ResumoUsuariosResposta,
    SegurancaNotificadaResposta,
    UsuarioAdminResposta,
    UsuarioAtualizacao,
    UsuarioAtualizacaoLote,
    UsuarioLoteEntrada,
    UsuarioLoteResposta,
    UsuarioResposta,
)
from app.entities.usuario import Usuario
from app.repositories.usuario_repository import UsuarioRepository
from app.services.email_service import EmailService
from app.services.verificacao_email_service import VerificacaoEmailService


def _campos_alterados_no_lote(atualizacao: UsuarioAtualizacaoLote) -> str:
    """Nomes (nunca valores) dos campos que o lote alterou."""
    return ",".join(sorted(atualizacao.model_dump(exclude={"id"}, exclude_unset=True)))


def _itens_do_lote(dados: UsuarioLoteEntrada, _resultado: UsuarioLoteResposta) -> list[dict]:
    """Um registro de auditoria por conta afetada pelo lote, com o mesmo vocabulário das rotas individuais."""
    return [
        *(
            {
                "acao": "usuario.editar",
                "entidade_id": atualizacao.id,
                "detalhes": {"campos_alterados": _campos_alterados_no_lote(atualizacao)},
            }
            for atualizacao in dados.atualizacoes
        ),
        *({"acao": "usuario.excluir", "entidade_id": usuario_id, "detalhes": {}} for usuario_id in dados.exclusoes),
    ]


class UsuarioService:
    def __init__(self, sessao: Session, emails: EmailService | None = None) -> None:
        self.sessao = sessao
        self.usuarios = UsuarioRepository(sessao)
        self.emails = emails or EmailService()
        self.verificacao = VerificacaoEmailService(sessao, self.emails)

    # ---------- consultas ----------
    def listar(
        self,
        *,
        desativados: bool = False,
        busca: str | None = None,
        perfil: str | None = None,
        limite: int = LIMITE_PADRAO_USUARIOS,
        pagina: int = 1,
    ) -> list[UsuarioAdminResposta]:
        usuarios = self.usuarios.listar(
            desativados=desativados, busca=busca, perfil=perfil, limite=limite, pagina=pagina
        )
        return [UsuarioAdminResposta.de_entidade(usuario) for usuario in usuarios]

    def resumir(
        self, *, desativados: bool = False, busca: str | None = None, perfil: str | None = None
    ) -> ResumoUsuariosResposta:
        return ResumoUsuariosResposta(total=self.usuarios.contar(desativados=desativados, busca=busca, perfil=perfil))

    @auditar("usuario.exportar", entidade="usuario", detalhes=lambda ponto, _r: {"formato": ponto.argumentos["exportador"].extensao})
    def exportar(
        self,
        exportador: Exportador,
        *,
        desativados: bool = False,
        busca: str | None = None,
        perfil: str | None = None,
    ) -> Iterator[bytes]:
        """Lista de contas em CSV ou PDF (Strategy escolhida pela factory no controller)."""
        nomes_perfil = {"usuario": "Usuário", "seguranca": "Segurança", "tecnico": "Técnico", "admin": "Administrador"}
        linhas = (
            [
                usuario.nome,
                usuario.email,
                nomes_perfil.get(usuario.tipo_usuario, usuario.tipo_usuario),
                "Sim" if usuario.email_verificado_em else "Não",
                "Ativa" if usuario.ativo else "Desativada",
                usuario.ultimo_acesso.strftime("%d/%m/%Y %H:%M") if usuario.ultimo_acesso else "Nunca",
            ]
            for usuario in self.usuarios.iterar_para_exportacao(desativados=desativados, busca=busca, perfil=perfil)
        )
        filtros = [
            f"situação: {'desativadas' if desativados else 'ativas'}",
            f"perfil: {nomes_perfil[perfil] if perfil else 'todos'}",
        ]
        if busca:
            filtros.append(f"busca: {busca}")
        documento = DocumentoTabular(
            titulo="Contas de usuários · Uni SOS",
            cabecalho=("Nome", "E-mail", "Perfil", "E-mail confirmado", "Situação", "Último acesso"),
            linhas=linhas if exportador.extensao == "csv" else list(linhas),
            informacoes=[f"Filtros: {' · '.join(filtros)}"],
            larguras_mm=(60, 70, 30, 30, 30, 35),
            mensagem_vazio="Nenhuma conta encontrada.",
        )
        return exportador.gerar(documento)

    def listar_por_perfil(self, perfil: str, com_email: bool = False) -> list[UsuarioResposta]:
        return [
            UsuarioResposta.de_entidade(usuario, com_email=com_email)
            for usuario in self.usuarios.listar_ativos_por_perfil(perfil)
        ]

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
    @auditar(
        "usuario.editar",
        entidade="usuario",
        entidade_id="usuario_id",
        ator="administrador.id",
        detalhes=nomes_dos_campos_enviados("dados"),
    )
    def atualizar(self, usuario_id: UUID, dados: UsuarioAtualizacao, administrador: Usuario) -> UsuarioAdminResposta:
        usuario = self._buscar_ativo(usuario_id)
        novos_dados = dados.model_dump(exclude_unset=True)
        if not novos_dados:
            raise RegraDeNegocioErro("Envie ao menos um campo para atualizar.")
        self._aplicar_alteracoes(usuario, novos_dados, administrador)
        self.sessao.commit()
        self.sessao.refresh(usuario)
        return UsuarioAdminResposta.de_entidade(usuario)

    def reenviar_verificacao(self, usuario_id: UUID) -> MensagemResposta:
        return self.verificacao.reenviar_pelo_admin(self._buscar_ativo(usuario_id))

    @auditar("usuario.excluir", entidade="usuario", entidade_id="usuario_id", ator="administrador.id")
    def excluir(self, usuario_id: UUID, administrador: Usuario) -> None:
        self._desativar(self._buscar_ativo(usuario_id), administrador)
        self.sessao.commit()

    @auditar("usuario.reativar", entidade="usuario", entidade_id="usuario_id", ator="administrador.id")
    def reativar(self, usuario_id: UUID, administrador: Usuario) -> UsuarioAdminResposta:
        """Desfaz a desativação. A conta volta com o mesmo perfil, nome, e-mail e senha.

        Contas anonimizadas a pedido do titular (LGPD) não voltam: os dados pessoais já foram apagados.
        Se o e-mail ainda não tinha sido confirmado, a pessoa continua precisando confirmá-lo
        (os links antigos foram apagados na desativação; ela pede um novo no login, ou o admin reenvia).
        """
        usuario = self.usuarios.buscar_por_id(usuario_id)
        if usuario is None:
            raise NaoEncontradoErro("Usuário não encontrado.")
        if usuario.anonimizado_em is not None:
            raise RegraDeNegocioErro("Esta conta foi anonimizada a pedido do titular (LGPD) e não pode ser reativada.")
        if usuario.ativo:
            raise RegraDeNegocioErro("Esta conta já está ativa.")
        usuario.ativo = True
        self.sessao.commit()
        self.sessao.refresh(usuario)
        return UsuarioAdminResposta.de_entidade(usuario)

    @auditar(
        "usuario.salvar_em_lote",
        entidade="usuario",
        ator="administrador.id",
        detalhes=lambda ponto, _: {
            "atualizacoes": len(ponto.resolver("dados.atualizacoes") or []),
            "exclusoes": len(ponto.resolver("dados.exclusoes") or []),
        },
        itens=lambda ponto, resultado: _itens_do_lote(ponto.resolver("dados"), resultado),
    )
    def salvar_em_lote(self, dados: UsuarioLoteEntrada, administrador: Usuario) -> UsuarioLoteResposta:
        """Aplica o rascunho do painel administrativo em uma única transação: tudo ou nada."""
        try:
            for atualizacao in dados.atualizacoes:
                usuario = self._buscar_ativo(self._uuid(atualizacao.id))
                novos_dados = atualizacao.model_dump(exclude={"id"}, exclude_unset=True)
                self._aplicar_alteracoes(usuario, novos_dados, administrador)
            for usuario_id in dados.exclusoes:
                self._desativar(self._buscar_ativo(self._uuid(usuario_id)), administrador)
            self.sessao.commit()
        except Exception:
            self.sessao.rollback()
            raise
        return UsuarioLoteResposta(atualizadas=len(dados.atualizacoes), excluidas=len(dados.exclusoes))

    # ---------- regras ----------
    def _aplicar_alteracoes(self, usuario: Usuario, novos_dados: dict, administrador: Usuario) -> None:
        if usuario.id == administrador.id and "perfil" in novos_dados:
            raise RegraDeNegocioErro("Você não pode alterar o próprio perfil.")
        if novos_dados.get("nome"):
            usuario.nome = novos_dados["nome"]
        if novos_dados.get("perfil"):
            self._garantir_ao_menos_um_admin(usuario, novos_dados["perfil"])
            usuario.tipo_usuario = novos_dados["perfil"]

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

    @staticmethod
    def _uuid(valor: str) -> UUID:
        try:
            return UUID(valor)
        except ValueError:
            raise NaoEncontradoErro("Usuário não encontrado.") from None

    def _garantir_ao_menos_um_admin(self, usuario: Usuario, novo_perfil: str | None = None) -> None:
        if usuario.tipo_usuario != "admin" or novo_perfil == "admin":
            return
        if self.usuarios.contar_ativos_por_perfil("admin") <= 1:
            raise RegraDeNegocioErro("Deve existir ao menos um administrador.")
