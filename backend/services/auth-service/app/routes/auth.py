from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.database import obter_banco
from app.schemas.auth import UsuarioAtualizar, UsuarioCriar, UsuarioResposta
from app.services.auth_service import (
    atualizar_usuario,
    criar_usuario,
    excluir_usuario,
    listar_todos_usuarios,
    obter_usuario,
)


rotas_usuarios = APIRouter(prefix="/usuarios", tags=["Usuários"])


@rotas_usuarios.post("", response_model=UsuarioResposta, status_code=status.HTTP_201_CREATED)
def criar(dados: UsuarioCriar, banco: Session = Depends(obter_banco)) -> UsuarioResposta:
    # A rota só recebe e entrega; a regra de negócio mora no serviço, como gente civilizada.
    return criar_usuario(banco, dados)


@rotas_usuarios.get("", response_model=list[UsuarioResposta])
def listar(
    inicio: int = 0,
    quantidade: int = 20,
    banco: Session = Depends(obter_banco),
) -> list[UsuarioResposta]:
    # Trava em 100 para alguém não pedir a tabela inteira e transformar a API em carroça.
    inicio = max(inicio, 0)
    quantidade = min(max(quantidade, 1), 100)
    return listar_todos_usuarios(banco, inicio, quantidade)


@rotas_usuarios.get("/{usuario_id}", response_model=UsuarioResposta)
def buscar(usuario_id: UUID, banco: Session = Depends(obter_banco)) -> UsuarioResposta:
    return obter_usuario(banco, usuario_id)


@rotas_usuarios.put("/{usuario_id}", response_model=UsuarioResposta)
def atualizar(
    usuario_id: UUID,
    dados: UsuarioAtualizar,
    banco: Session = Depends(obter_banco),
) -> UsuarioResposta:
    return atualizar_usuario(banco, usuario_id, dados)


@rotas_usuarios.delete("/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir(usuario_id: UUID, banco: Session = Depends(obter_banco)) -> Response:
    excluir_usuario(banco, usuario_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
