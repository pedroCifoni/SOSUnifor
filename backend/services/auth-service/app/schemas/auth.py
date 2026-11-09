from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UsuarioCriar(BaseModel):
    email: str = Field(min_length=5, max_length=150)
    matricula: str = Field(min_length=1, max_length=30)
    senha: str = Field(min_length=6, max_length=100)
    tipo_usuario: str = Field(default="aluno", min_length=1, max_length=50)


class UsuarioAtualizar(BaseModel):
    email: str | None = Field(default=None, min_length=5, max_length=150)
    matricula: str | None = Field(default=None, min_length=1, max_length=30)
    senha: str | None = Field(default=None, min_length=6, max_length=100)
    tipo_usuario: str | None = Field(default=None, min_length=1, max_length=50)
    ativo: bool | None = None


class UsuarioResposta(BaseModel):
    id: UUID
    email: str
    matricula: str
    tipo_usuario: str
    ativo: bool

    model_config = ConfigDict(from_attributes=True)
