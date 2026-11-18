from typing import Any, Literal

from pydantic import BaseModel, Field

from app.dtos.base import RespostaDTO
from app.entities.evento_ocorrencia import EventoOcorrencia
from app.entities.ocorrencia import Ocorrencia


TipoOcorrencia = Literal["sos", "manutencao", "denuncia"]
StatusOcorrencia = Literal["pendente", "aguardando_aceite", "em_atendimento", "concluido", "cancelado"]


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
