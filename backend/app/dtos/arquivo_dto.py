from app.dtos.base import RespostaDTO


class ArquivoResposta(RespostaDTO):
    nome: str
    url: str
    tipo: str | None
