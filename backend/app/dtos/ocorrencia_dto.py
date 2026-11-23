import re
from datetime import datetime, timezone
from typing import Any, Literal, get_args
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.excecoes import RegraDeNegocioErro
from app.dtos.base import RespostaDTO
from app.entities.evento_ocorrencia import EventoOcorrencia
from app.entities.ocorrencia import Ocorrencia


TipoOcorrencia = Literal["sos", "manutencao", "denuncia"]
StatusOcorrencia = Literal["pendente", "aguardando_aceite", "em_atendimento", "concluido", "cancelado"]

LIMITE_PADRAO_PAGINA = 50
LIMITE_MAXIMO_PAGINA = 200


# ---------- paginação ----------
def ajustar_limite(limite: int) -> int:
    return max(1, min(limite, LIMITE_MAXIMO_PAGINA))


class CursorPagina(BaseModel):
    """Cursor da paginação keyset: data e id do ÚLTIMO item da página anterior."""

    antes_de: datetime | None = None
    antes_id: UUID | None = None

    @classmethod
    def interpretar(cls, antes_de: str | None, antes_id: UUID | None) -> "CursorPagina":
        if (antes_de is None) != (antes_id is None):
            raise RegraDeNegocioErro("Envie antes_de e antes_id juntos.")
        if antes_de is None:
            return cls()
        # Um "+" sem codificação na URL chega como espaço: "...T12:00:00.123 00:00".
        texto = antes_de.strip()
        if "T" in texto:
            texto = re.sub(r" (\d{2}:?\d{2})$", r"+\1", texto)
        try:
            data = datetime.fromisoformat(texto.replace("Z", "+00:00"))
        except ValueError as erro:
            raise RegraDeNegocioErro("antes_de deve ser uma data ISO 8601.") from erro
        if data.tzinfo is None:
            data = data.replace(tzinfo=timezone.utc)
        return cls(antes_de=data, antes_id=antes_id)


# ---------- entrada ----------
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


# ---------- saída ----------
class ResumoOcorrenciasResposta(RespostaDTO):
    total: int
    por_status: dict[str, int]
    por_tipo: dict[str, int]

    @classmethod
    def de_contagens(cls, contagens: list[tuple[str, str, int]]) -> "ResumoOcorrenciasResposta":
        """Recebe (status, tipo, quantidade) e garante todas as chaves, com 0 quando não houver."""
        por_status = dict.fromkeys(get_args(StatusOcorrencia), 0)
        por_tipo = dict.fromkeys(get_args(TipoOcorrencia), 0)
        total = 0
        for status, tipo, quantidade in contagens:
            total += quantidade
            if status in por_status:
                por_status[status] += quantidade
            if tipo in por_tipo:
                por_tipo[tipo] += quantidade
        return cls(total=total, por_status=por_status, por_tipo=por_tipo)


class EventoOcorrenciaResposta(RespostaDTO):
    tipo: str
    descricao: str
    criado_em: str

    @classmethod
    def de_entidade(cls, evento: EventoOcorrencia) -> "EventoOcorrenciaResposta":
        return cls(tipo=evento.tipo, descricao=evento.descricao, criado_em=evento.criado_em.isoformat())


class OcorrenciaResposta(RespostaDTO):
    id: str
    protocolo: str
    titulo: str
    descricao: str | None
    local: str
    tipo: str
    status: str
    solicitante: str
    autor_id: str | None
    anonima: bool
    anexos: list[dict[str, Any]]
    responsavel_id: str | None
    latitude: float | None
    longitude: float | None
    precisao_metros: float | None
    criado_em: str

    @classmethod
    def de_entidade(cls, ocorrencia: Ocorrencia, solicitante: str) -> "OcorrenciaResposta":
        return cls(**_campos_da_ocorrencia(ocorrencia, solicitante))


class OcorrenciaDetalheResposta(OcorrenciaResposta):
    eventos: list[EventoOcorrenciaResposta]

    @classmethod
    def de_entidade_com_eventos(
        cls, ocorrencia: Ocorrencia, solicitante: str, eventos: list[EventoOcorrencia]
    ) -> "OcorrenciaDetalheResposta":
        return cls(
            **_campos_da_ocorrencia(ocorrencia, solicitante),
            eventos=[EventoOcorrenciaResposta.de_entidade(evento) for evento in eventos],
        )


def _campos_da_ocorrencia(ocorrencia: Ocorrencia, solicitante: str) -> dict[str, Any]:
    return {
        "id": str(ocorrencia.id),
        "protocolo": ocorrencia.protocolo,
        "titulo": ocorrencia.titulo,
        "descricao": ocorrencia.descricao,
        "local": ocorrencia.local,
        "tipo": ocorrencia.tipo,
        "status": ocorrencia.status,
        "solicitante": solicitante,
        # Em denúncias anônimas o autor nunca é exposto.
        "autor_id": None if ocorrencia.anonima else str(ocorrencia.autor_id),
        "anonima": ocorrencia.anonima,
        "anexos": ocorrencia.anexos,
        "responsavel_id": str(ocorrencia.responsavel_id) if ocorrencia.responsavel_id else None,
        "latitude": ocorrencia.latitude,
        "longitude": ocorrencia.longitude,
        "precisao_metros": ocorrencia.precisao_metros,
        "criado_em": ocorrencia.criado_em.isoformat(),
    }
