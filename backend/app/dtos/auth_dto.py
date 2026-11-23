from pydantic import BaseModel, Field


class LoginEntrada(BaseModel):
    email: str = Field(min_length=5, max_length=150)
    senha: str = Field(min_length=6, max_length=100)


class TokenResposta(BaseModel):
    token: str


class EsqueciSenhaEntrada(BaseModel):
    email: str = Field(min_length=3, max_length=150)


class RedefinirSenhaEntrada(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    nova_senha: str = Field(min_length=6, max_length=100)


class MensagemResposta(BaseModel):
    mensagem: str
