from typing import Literal

from pydantic import BaseModel, Field, field_validator


Perfil = Literal["usuario", "seguranca", "tecnico", "admin"]
TipoOcorrencia = Literal["sos", "manutencao", "denuncia"]
StatusOcorrencia = Literal["pendente", "aguardando_aceite", "em_atendimento", "concluido", "cancelado"]


class CredenciaisLogin(BaseModel):
    email: str = Field(min_length=5, max_length=150)
    senha: str = Field(min_length=6, max_length=100)


class UsuarioEntrada(BaseModel):
    nome: str = Field(min_length=1, max_length=150)
    email: str = Field(min_length=5, max_length=150)
    perfil: Perfil
    senha: str = Field(min_length=6, max_length=100)

    @field_validator("email")
    @classmethod
    def validar_email(cls, email: str) -> str:
        email_normalizado = email.lower().strip()
        if email_normalizado.count("@") != 1 or email_normalizado.startswith("@") or email_normalizado.endswith("@"):
            raise ValueError("Informe um e-mail válido.")
        return email_normalizado


class UsuarioAtualizacao(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=150)
    email: str | None = Field(default=None, min_length=5, max_length=150)
    perfil: Perfil | None = None
    senha: str | None = Field(default=None, min_length=6, max_length=100)

    @field_validator("email")
    @classmethod
    def validar_email(cls, email: str | None) -> str | None:
        if email is None:
            return None
        email_normalizado = email.lower().strip()
        if email_normalizado.count("@") != 1 or email_normalizado.startswith("@") or email_normalizado.endswith("@"):
            raise ValueError("Informe um e-mail válido.")
        return email_normalizado


class UsuarioAtualizacaoLote(UsuarioAtualizacao):
    id: str


class UsuarioLoteEntrada(BaseModel):
    criacoes: list[UsuarioEntrada] = Field(default_factory=list, max_length=100)
    atualizacoes: list[UsuarioAtualizacaoLote] = Field(default_factory=list, max_length=100)
    exclusoes: list[str] = Field(default_factory=list, max_length=100)


class AnexoEntrada(BaseModel):
    nome: str = Field(min_length=1, max_length=255)
    url: str | None = Field(default=None, max_length=1000)
    tipo: str | None = Field(default=None, max_length=100)


class OcorrenciaEntrada(BaseModel):
    titulo: str = Field(min_length=1, max_length=160)
    descricao: str | None = Field(default=None, max_length=5000)
    local: str = Field(min_length=1, max_length=200)
    tipo: TipoOcorrencia
    anonima: bool = False
    anexos: list[AnexoEntrada] = Field(default_factory=list, max_length=10)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    precisao_metros: float | None = Field(default=None, alias="precisaoMetros", ge=0, le=10000)


class EncaminhamentoEntrada(BaseModel):
    responsavel_id: str = Field(alias="responsavelId")


class StatusEntrada(BaseModel):
    status: StatusOcorrencia


class EventoOcorrenciaResposta(BaseModel):
    tipo: str
    descricao: str
    criado_em: str = Field(alias="criadoEm")


class CoordenadasEntrada(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class PontoMapaEntrada(CoordenadasEntrada):
    pass


class AreaCampusEntrada(BaseModel):
    nome: str = Field(min_length=2, max_length=160)
    tipo: str = Field(min_length=2, max_length=50)
    coordenadas: list[PontoMapaEntrada] = Field(min_length=3, max_length=200)
    limite_campus: bool = Field(default=False, alias="limiteCampus")
    prioridade: int = Field(default=0, ge=0, le=1000)
