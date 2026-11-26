import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.dtos.base import RespostaDTO, validar_email_institucional


# Senhas: mínimo de 8 caracteres (recomendação NIST SP 800-63B), sem exigir combinações de símbolos.
# O máximo acompanha o do login, para que toda senha cadastrada consiga entrar.
TAMANHO_MINIMO_SENHA = 8
TAMANHO_MAXIMO_SENHA = 100


class LoginEntrada(BaseModel):
    email: str = Field(min_length=5, max_length=150)
    senha: str = Field(min_length=6, max_length=TAMANHO_MAXIMO_SENHA)


class TokenResposta(RespostaDTO):
    token: str
    # Opcional para compatibilidade: clientes antigos só leem "token".
    refresh_token: str | None = None


class RenovarSessaoEntrada(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=200)


class CadastroEntrada(BaseModel):
    """Autocadastro pela tela pública. O perfil não é escolhido: toda conta nova nasce como "usuario"."""

    # Campos desconhecidos (ex.: "perfil": "admin") são recusados em vez de ignorados em silêncio.
    model_config = ConfigDict(extra="forbid")

    nome: str = Field(min_length=3, max_length=150)
    email: str = Field(min_length=5, max_length=150)
    senha: str = Field(min_length=TAMANHO_MINIMO_SENHA, max_length=TAMANHO_MAXIMO_SENHA)
    # Versão da Política de Privacidade que a pessoa leu e marcou como ciente na tela de cadastro.
    versao_termos: str = Field(min_length=1, max_length=20)

    @field_validator("nome")
    @classmethod
    def normalizar_nome(cls, nome: str) -> str:
        nome_limpo = re.sub(r"\s+", " ", nome).strip()
        if len(nome_limpo) < 3 or not any(caractere.isalpha() for caractere in nome_limpo):
            raise ValueError("Informe o seu nome.")
        return nome_limpo

    @field_validator("email")
    @classmethod
    def exigir_email_institucional(cls, email: str) -> str:
        return validar_email_institucional(email)

    @field_validator("senha")
    @classmethod
    def recusar_senha_em_branco(cls, senha: str) -> str:
        if not senha.strip():
            raise ValueError("A senha não pode ser só espaços.")
        return senha

    @model_validator(mode="after")
    def senha_diferente_do_email(self) -> "CadastroEntrada":
        senha = self.senha.lower()
        if senha == self.email or senha == self.email.split("@")[0]:
            raise ValueError("A senha não pode ser igual ao seu e-mail.")
        return self


class EsqueciSenhaEntrada(BaseModel):
    email: str = Field(min_length=3, max_length=150)


class RedefinirSenhaEntrada(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    nova_senha: str = Field(min_length=6, max_length=TAMANHO_MAXIMO_SENHA)


class VerificarEmailEntrada(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    # A confirmação exige a senha da conta: quem tem só o link (o dono do e-mail) não ativa uma conta
    # cuja senha foi escolhida por outra pessoa (ataque de "pré-sequestro" de conta).
    senha: str = Field(min_length=1, max_length=TAMANHO_MAXIMO_SENHA)


class ReenviarVerificacaoEntrada(BaseModel):
    email: str = Field(min_length=3, max_length=150)


class MensagemResposta(BaseModel):
    mensagem: str
