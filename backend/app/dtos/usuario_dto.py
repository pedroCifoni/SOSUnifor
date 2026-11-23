from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.dtos.base import RespostaDTO, validar_email
from app.entities.usuario import Usuario


Perfil = Literal["usuario", "seguranca", "tecnico", "admin"]

LIMITE_PADRAO_USUARIOS = 50
LIMITE_MAXIMO_USUARIOS = 200


def ajustar_limite_usuarios(limite: int) -> int:
    return max(1, min(limite, LIMITE_MAXIMO_USUARIOS))


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
    """Dados públicos de uma conta (ex.: listas de seguranças e técnicos, abertas a qualquer usuário logado)."""

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


class ResumoUsuariosResposta(RespostaDTO):
    total: int


class UsuarioAdminResposta(UsuarioResposta):
    """Visão do administrador: inclui dados internos de gestão, como a confirmação do e-mail."""

    email_verificado: bool

    @classmethod
    def de_entidade(cls, usuario: Usuario) -> "UsuarioAdminResposta":
        return cls(
            id=str(usuario.id),
            nome=usuario.nome,
            email=usuario.email,
            perfil=usuario.tipo_usuario,
            email_verificado=usuario.email_verificado_em is not None,
        )


class UsuarioLoteResposta(RespostaDTO):
    criadas: int
    atualizadas: int
    excluidas: int
    ids_criados: list[str] = Field(default_factory=list)


class SegurancaNotificadaResposta(RespostaDTO):
    id: str
    nome: str
    viatura: str
    distancia_m: int
    status: str
