from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.credential import Usuario


def buscar_usuario_por_id(banco: Session, usuario_id: UUID) -> Usuario | None:
    return banco.get(Usuario, usuario_id)


def buscar_usuario_por_email(banco: Session, email: str) -> Usuario | None:
    consulta = select(Usuario).where(Usuario.email == email)
    return banco.scalar(consulta)


def buscar_usuario_por_matricula(banco: Session, matricula: str) -> Usuario | None:
    consulta = select(Usuario).where(Usuario.matricula == matricula)
    return banco.scalar(consulta)


def listar_usuarios(banco: Session, inicio: int, quantidade: int) -> list[Usuario]:
    consulta = select(Usuario).offset(inicio).limit(quantidade).order_by(Usuario.email)
    return list(banco.scalars(consulta))


def salvar_usuario(banco: Session, usuario: Usuario) -> Usuario:
    banco.add(usuario)
    # commit é o "agora vai". Antes disso, a alteração ainda está só passeando na sessão.
    banco.commit()
    banco.refresh(usuario)
    return usuario


def remover_usuario(banco: Session, usuario: Usuario) -> None:
    banco.delete(usuario)
    # Aqui o usuário sai da tabela de vez. Delete não tem Ctrl+Z, então cuidado, campeão.
    banco.commit()
