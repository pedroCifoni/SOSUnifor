from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import gerar_hash_senha
from app.models.credential import Usuario
from app.repositories.credential_repository import (
    buscar_usuario_por_email,
    buscar_usuario_por_id,
    buscar_usuario_por_matricula,
    listar_usuarios,
    remover_usuario,
    salvar_usuario,
)
from app.schemas.auth import UsuarioAtualizar, UsuarioCriar


def obter_usuario(banco: Session, usuario_id: UUID) -> Usuario:
    usuario = buscar_usuario_por_id(banco, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado.")
    return usuario


def criar_usuario(banco: Session, dados: UsuarioCriar) -> Usuario:
    # Primeiro checa duplicidade; depois evita descobrir no banco do jeito mais doloroso possível.
    validar_dados_unicos(banco, dados.email, dados.matricula)
    usuario = Usuario(
        email=dados.email,
        matricula=dados.matricula,
        senha_hash=gerar_hash_senha(dados.senha),
        tipo_usuario=dados.tipo_usuario,
    )
    return salvar_usuario(banco, usuario)


def listar_todos_usuarios(banco: Session, inicio: int, quantidade: int) -> list[Usuario]:
    return listar_usuarios(banco, inicio, quantidade)


def atualizar_usuario(banco: Session, usuario_id: UUID, dados: UsuarioAtualizar) -> Usuario:
    usuario = obter_usuario(banco, usuario_id)
    dados_novos = dados.model_dump(exclude_unset=True)

    if not dados_novos:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Envie ao menos um campo para atualizar.")

    email = dados_novos.get("email")
    matricula = dados_novos.get("matricula")
    validar_dados_unicos(banco, email, matricula, usuario.id)

    senha = dados_novos.pop("senha", None)
    if senha is not None:
        # Mudou a senha? Gera outro hash; jamais joga senha pura na coluna por preguiça.
        usuario.senha_hash = gerar_hash_senha(senha)

    for campo, valor in dados_novos.items():
        setattr(usuario, campo, valor)

    return salvar_usuario(banco, usuario)


def excluir_usuario(banco: Session, usuario_id: UUID) -> None:
    usuario = obter_usuario(banco, usuario_id)
    remover_usuario(banco, usuario)


def validar_dados_unicos(
    banco: Session,
    email: str | None,
    matricula: str | None,
    usuario_id: UUID | None = None,
) -> None:
    # O banco também garante unicidade, mas responder 409 aqui deixa o erro menos misterioso.
    if email is not None:
        usuario_com_email = buscar_usuario_por_email(banco, email)
        if usuario_com_email is not None and usuario_com_email.id != usuario_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="E-mail já cadastrado.")

    if matricula is not None:
        usuario_com_matricula = buscar_usuario_por_matricula(banco, matricula)
        if usuario_com_matricula is not None and usuario_com_matricula.id != usuario_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Matrícula já cadastrada.")
