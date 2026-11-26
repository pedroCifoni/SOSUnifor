"""Perfil do próprio usuário (GET/PUT /me, PUT /me/senha, /me/avatar)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.dtos.auth_dto import TAMANHO_MAXIMO_SENHA, TAMANHO_MINIMO_SENHA
from app.dtos.base import RespostaDTO
from app.entities.usuario import Usuario


class PerfilResposta(RespostaDTO):
    id: str
    nome: str
    email: str
    perfil: str
    email_verificado_em: datetime | None
    ultimo_acesso: datetime | None
    tem_avatar: bool

    @classmethod
    def de_entidade(cls, usuario: Usuario) -> "PerfilResposta":
        return cls(
            id=str(usuario.id),
            nome=usuario.nome,
            email=usuario.email,
            perfil=usuario.tipo_usuario,
            email_verificado_em=usuario.email_verificado_em,
            ultimo_acesso=usuario.ultimo_acesso,
            tem_avatar=usuario.avatar_tipo is not None,
        )


class PerfilAtualizacao(BaseModel):
    """O titular corrige o próprio nome (LGPD, art. 18, III). E-mail e perfil não mudam por aqui."""

    model_config = ConfigDict(extra="forbid")

    nome: str = Field(min_length=3, max_length=150)

    @field_validator("nome")
    @classmethod
    def normalizar_nome(cls, nome: str) -> str:
        nome_limpo = " ".join(nome.split())
        if len(nome_limpo) < 3:
            raise ValueError("Informe o nome completo.")
        return nome_limpo


class TrocaSenhaEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    senha_atual: str = Field(min_length=1, max_length=TAMANHO_MAXIMO_SENHA)
    nova_senha: str = Field(min_length=TAMANHO_MINIMO_SENHA, max_length=TAMANHO_MAXIMO_SENHA)

    @field_validator("nova_senha")
    @classmethod
    def recusar_senha_em_branco(cls, senha: str) -> str:
        if not senha.strip():
            raise ValueError("A senha não pode ser só espaços.")
        return senha

    @model_validator(mode="after")
    def senha_nova_diferente(self) -> "TrocaSenhaEntrada":
        if self.senha_atual == self.nova_senha:
            raise ValueError("A nova senha precisa ser diferente da atual.")
        return self
