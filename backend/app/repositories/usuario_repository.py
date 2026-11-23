from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.entities.usuario import Usuario


class UsuarioRepository:
    def __init__(self, sessao: Session) -> None:
        self.sessao = sessao

    def buscar_por_id(self, usuario_id: UUID) -> Usuario | None:
        return self.sessao.get(Usuario, usuario_id)

    def buscar_por_email(self, email: str) -> Usuario | None:
        return self.sessao.scalar(select(Usuario).where(Usuario.email == email.lower().strip()))

    def listar_ativos(self) -> list[Usuario]:
        return list(self.sessao.scalars(select(Usuario).where(Usuario.ativo).order_by(Usuario.nome)))

    def listar_ativos_por_perfil(self, perfil: str) -> list[Usuario]:
        consulta = select(Usuario).where(Usuario.ativo, Usuario.tipo_usuario == perfil).order_by(Usuario.nome)
        return list(self.sessao.scalars(consulta))

    def ids_ativos_por_perfil(self, perfil: str) -> list[UUID]:
        return list(self.sessao.scalars(select(Usuario.id).where(Usuario.ativo, Usuario.tipo_usuario == perfil)))

    def contar_ativos_por_perfil(self, perfil: str) -> int:
        consulta = select(func.count()).select_from(Usuario).where(Usuario.tipo_usuario == perfil, Usuario.ativo)
        return self.sessao.scalar(consulta) or 0

    def travar_e_contar_ativos_por_perfil(self, perfil: str) -> int:
        """Conta as contas ativas do perfil travando as linhas (SELECT ... FOR UPDATE) até o fim da transação.

        Duas transações que alteram contas deste perfil ao mesmo tempo passam a contar uma de cada vez:
        a segunda espera a primeira terminar e já enxerga o resultado dela.
        """
        consulta = select(Usuario.id).where(Usuario.tipo_usuario == perfil, Usuario.ativo).with_for_update()
        return len(list(self.sessao.scalars(consulta)))

    def existe_outro_com_nome(self, nome: str, exceto_id: UUID) -> bool:
        consulta = select(Usuario.id).where(Usuario.nome == nome, Usuario.id != exceto_id).limit(1)
        return self.sessao.scalar(consulta) is not None

    def ids_de_usuarios_online(self, desde: datetime) -> list[UUID]:
        """Usuários comuns que fizeram alguma requisição autenticada a partir de `desde`."""
        consulta = select(Usuario.id).where(
            Usuario.ativo,
            Usuario.tipo_usuario == "usuario",
            Usuario.ultimo_acesso.is_not(None),
            Usuario.ultimo_acesso >= desde,
        )
        return list(self.sessao.scalars(consulta))

    def listar_com_exclusao_pendente(self) -> list[Usuario]:
        """Titulares que pediram a eliminação dos dados e ainda não foram anonimizados."""
        consulta = (
            select(Usuario)
            .where(Usuario.exclusao_solicitada_em.is_not(None), Usuario.anonimizado_em.is_(None))
            .order_by(Usuario.exclusao_solicitada_em)
        )
        return list(self.sessao.scalars(consulta))

    def adicionar(self, usuario: Usuario) -> Usuario:
        self.sessao.add(usuario)
        return usuario
