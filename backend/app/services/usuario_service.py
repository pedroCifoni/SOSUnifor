from uuid import UUID

from sqlalchemy.orm import Session

from app.core.excecoes import ConflitoErro, NaoEncontradoErro, RegraDeNegocioErro
from app.core.seguranca import gerar_hash_senha
from app.dtos.usuario_dto import (
    SegurancaNotificadaResposta,
    UsuarioAtualizacao,
    UsuarioEntrada,
    UsuarioLoteEntrada,
    UsuarioLoteResposta,
    UsuarioResposta,
)
from app.entities.usuario import Usuario
from app.repositories.usuario_repository import UsuarioRepository


class UsuarioService:
    def __init__(self, sessao: Session) -> None:
        self.sessao = sessao
        self.usuarios = UsuarioRepository(sessao)

    # ---------- consultas ----------
    def listar_ativos(self) -> list[UsuarioResposta]:
        return [UsuarioResposta.de_entidade(usuario) for usuario in self.usuarios.listar_ativos()]

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
    def criar(self, dados: UsuarioEntrada) -> UsuarioResposta:
        usuario = self._novo_usuario(dados)
        self.sessao.commit()
        self.sessao.refresh(usuario)
        return UsuarioResposta.de_entidade(usuario)

    def atualizar(self, usuario_id: UUID, dados: UsuarioAtualizacao, administrador: Usuario) -> UsuarioResposta:
        usuario = self._buscar_ativo(usuario_id)
        novos_dados = dados.model_dump(exclude_unset=True)
        if not novos_dados:
            raise RegraDeNegocioErro("Envie ao menos um campo para atualizar.")
        self._aplicar_alteracoes(usuario, novos_dados, administrador)
        self.sessao.commit()
        self.sessao.refresh(usuario)
        return UsuarioResposta.de_entidade(usuario)

    def excluir(self, usuario_id: UUID, administrador: Usuario) -> None:
        self._desativar(self._buscar_ativo(usuario_id), administrador)
        self.sessao.commit()

    def salvar_em_lote(self, dados: UsuarioLoteEntrada, administrador: Usuario) -> UsuarioLoteResposta:
        """Aplica o rascunho do painel administrativo em uma única transação: tudo ou nada."""
        try:
            for criacao in dados.criacoes:
                self._novo_usuario(criacao)
            self.sessao.flush()
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
            raise
        return UsuarioLoteResposta(
            criadas=len(dados.criacoes), atualizadas=len(dados.atualizacoes), excluidas=len(dados.exclusoes)
        )

    # ---------- regras ----------
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
        if "email" in novos_dados:
            usuario.email = self._email_disponivel(novos_dados["email"], usuario.id)
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
