from pydantic import BaseModel, Field


class LoginEntrada(BaseModel):
    email: str = Field(min_length=5, max_length=150)
    senha: str = Field(min_length=6, max_length=100)


class TokenResposta(BaseModel):
    token: str
