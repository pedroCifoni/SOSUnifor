from datetime import datetime

from pydantic import BaseModel, Field

from app.dtos.base import RespostaDTO


class CienciaPrivacidadeEntrada(BaseModel):
    """Versão da política que o usuário leu. Evita registrar ciência de um texto que ele não viu."""

    versao: str = Field(min_length=1, max_length=20)


class SituacaoPrivacidadeResposta(RespostaDTO):
    versao_vigente: str
    versao_ciente: str | None
    ciente_em: datetime | None
    pendente: bool
