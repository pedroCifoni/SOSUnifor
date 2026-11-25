from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.dtos.base import RespostaDTO
from app.entities.usuario import Usuario


Perfil = Literal["usuario", "seguranca", "tecnico", "admin"]
# Filtro da lista do admin: contas ativas ou desativadas (que podem ser reativadas).
SituacaoConta = Literal["ativos", "desativados"]

LIMITE_PADRAO_USUARIOS = 50
LIMITE_MAXIMO_USUARIOS = 200


def ajustar_limite_usuarios(limite: int) -> int:
    return max(1, min(limite, LIMITE_MAXIMO_USUARIOS))


# ---------- entrada ----------
# As contas são criadas pelo próprio titular (POST /auth/cadastro). O administrador só muda o perfil,
# corrige o nome (LGPD, art. 18, III) e desativa contas. E-mail e senha são do titular: o admin não os
# altera (o e-mail é comprovado pelo dono; a senha só ele conhece). Campos extras são recusados (422),
# para um cliente antigo que ainda envie "email" ou "senha" não achar que a mudança foi aplicada.
class UsuarioAtualizacao(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome: str | None = Field(default=None, min_length=1, max_length=150)
    perfil: Perfil | None = None

    @field_validator("nome")
    @classmethod
    def normalizar_nome(cls, nome: str | None) -> str | None:
        if nome is None:
            return None
        nome_limpo = " ".join(nome.split())
        if not nome_limpo:
            raise ValueError("Informe o nome.")
        return nome_limpo


class UsuarioAtualizacaoLote(UsuarioAtualizacao):
    id: str


class UsuarioLoteEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
    ativo: bool

    @classmethod
    def de_entidade(cls, usuario: Usuario) -> "UsuarioAdminResposta":
        return cls(
            id=str(usuario.id),
            nome=usuario.nome,
            email=usuario.email,
            perfil=usuario.tipo_usuario,
            email_verificado=usuario.email_verificado_em is not None,
            ativo=usuario.ativo,
        )


class UsuarioLoteResposta(RespostaDTO):
    atualizadas: int
    excluidas: int


class SegurancaNotificadaResposta(RespostaDTO):
    id: str
    nome: str
    viatura: str
    distancia_m: int
    status: str
