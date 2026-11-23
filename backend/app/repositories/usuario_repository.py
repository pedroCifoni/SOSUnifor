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

    def contar_admins_confirmados(self, exceto: UUID | None = None) -> int:
        consulta = (
            select(func.count())
            .select_from(Usuario)
            .where(Usuario.tipo_usuario == "admin", Usuario.ativo, Usuario.email_verificado_em.is_not(None))
        )
        if exceto is not None:
            consulta = consulta.where(Usuario.id != exceto)
        return self.sessao.scalar(consulta) or 0

    def travar(self, usuario_id: UUID) -> None:
        """Trava a linha da conta até o fim da transação (SELECT ... FOR UPDATE).

        Serializa pedidos simultâneos da mesma conta, como contar e gravar links enviados por e-mail.
        """
        self.sessao.execute(select(Usuario.id).where(Usuario.id == usuario_id).with_for_update())

    def ids_de_usuarios_online(self, desde: datetime) -> list[UUID]:
        """Usuários comuns que fizeram alguma requisição autenticada a partir de `desde`."""
        consulta = select(Usuario.id).where(
            Usuario.ativo,
            Usuario.tipo_usuario == "usuario",
            Usuario.ultimo_acesso.is_not(None),
            Usuario.ultimo_acesso >= desde,
        )
        return list(self.sessao.scalars(consulta))

    def adicionar(self, usuario: Usuario) -> Usuario:
        self.sessao.add(usuario)
        return usuario
