import re

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


# Único domínio aceito no autocadastro: o e-mail oficial dos alunos. A comparação é exata:
# outros subdomínios (ex.: aluno.unifor.br), o domínio dos funcionários (unifor.br) e domínios
# parecidos (ex.: edu.unifor.br.com, edu.unifor.com.br) são recusados. As contas da equipe
# (admin, segurança, técnicos) não passam pelo autocadastro.
DOMINIO_EMAIL_INSTITUCIONAL = "edu.unifor.br"
MENSAGEM_EMAIL_INSTITUCIONAL = f"Use o seu e-mail institucional (@{DOMINIO_EMAIL_INSTITUCIONAL})."

# Parte antes do @: letras minúsculas, números e . _ % + -, começando e terminando com letra ou número.
_PARTE_LOCAL = re.compile(r"^[a-z0-9](?:[a-z0-9._%+-]{0,62}[a-z0-9])?$")


class RespostaDTO(BaseModel):
    """Base das respostas: atributos em snake_case no Python, camelCase no JSON."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


def validar_email(email: str) -> str:
    email_normalizado = email.lower().strip()
    if email_normalizado.count("@") != 1 or email_normalizado.startswith("@") or email_normalizado.endswith("@"):
        raise ValueError("Informe um e-mail válido.")
    return email_normalizado


def validar_email_institucional(email: str) -> str:
    """Normaliza e só aceita endereços exatamente do domínio da UNIFOR."""
    email_normalizado = validar_email(email)
    parte_local, dominio = email_normalizado.split("@")
    if dominio != DOMINIO_EMAIL_INSTITUCIONAL:
        raise ValueError(MENSAGEM_EMAIL_INSTITUCIONAL)
    if not _PARTE_LOCAL.fullmatch(parte_local) or ".." in parte_local:
        raise ValueError("Informe um e-mail válido.")
    return email_normalizado
