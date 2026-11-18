from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class RespostaDTO(BaseModel):
    """Base das respostas: atributos em snake_case no Python, camelCase no JSON."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


def validar_email(email: str) -> str:
    email_normalizado = email.lower().strip()
    if email_normalizado.count("@") != 1 or email_normalizado.startswith("@") or email_normalizado.endswith("@"):
        raise ValueError("Informe um e-mail válido.")
    return email_normalizado
