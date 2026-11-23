from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.dtos.base import RespostaDTO, validar_email
from app.entities.usuario import Usuario


Perfil = Literal["usuario", "seguranca", "tecnico", "admin"]


# ---------- entrada ----------
class UsuarioEntrada(BaseModel):
    nome: str = Field(min_length=1, max_length=150)
    email: str = Field(min_length=5, max_length=150)
    perfil: Perfil
    senha: str = Field(min_length=6, max_length=100)

    @field_validator("email")
    @classmethod
    def normalizar_email(cls, email: str) -> str:
        return validar_email(email)


class UsuarioAtualizacao(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=150)
    email: str | None = Field(default=None, min_length=5, max_length=150)
    perfil: Perfil | None = None
    senha: str | None = Field(default=None, min_length=6, max_length=100)

    @field_validator("email")
    @classmethod
    def normalizar_email(cls, email: str | None) -> str | None:
        return None if email is None else validar_email(email)


class UsuarioAtualizacaoLote(UsuarioAtualizacao):
    id: str


class UsuarioLoteEntrada(BaseModel):
    criacoes: list[UsuarioEntrada] = Field(default_factory=list, max_length=100)
    atualizacoes: list[UsuarioAtualizacaoLote] = Field(default_factory=list, max_length=100)
    exclusoes: list[str] = Field(default_factory=list, max_length=100)


# ---------- saída ----------
class UsuarioResposta(RespostaDTO):
    id: str
    nome: str
    # Minimização (LGPD, art. 6º, III): o e-mail de outras pessoas só vai para o administrador.
    email: str | None
    perfil: str

    @classmethod
    def de_entidade(cls, usuario: Usuario, com_email: bool = True) -> "UsuarioResposta":
        return cls(
            id=str(usuario.id),
            nome=usuario.nome,
            email=usuario.email if com_email else None,
            perfil=usuario.tipo_usuario,
        )


class UsuarioLoteResposta(RespostaDTO):
    criadas: int
    atualizadas: int
    excluidas: int


class SegurancaNotificadaResposta(RespostaDTO):
    id: str
    nome: str
    viatura: str
    distancia_m: int
    status: str
