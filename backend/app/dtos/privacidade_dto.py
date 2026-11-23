"""DTOs da adequação à LGPD: ciência dos termos, exportação e eliminação de dados do titular."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.dtos.base import RespostaDTO
from app.entities.evento_ocorrencia import EventoOcorrencia
from app.entities.notificacao import Notificacao
from app.entities.ocorrencia import Ocorrencia
from app.entities.usuario import Usuario


def _iso(data: datetime | None) -> str | None:
    return data.isoformat() if data else None


# ---------- entrada ----------
class AceiteTermosEntrada(BaseModel):
    versao: str = Field(min_length=1, max_length=20)


class SolicitacaoExclusaoEntrada(BaseModel):
    """O titular precisa confirmar explicitamente o pedido."""

    confirmar: bool


# ---------- saída ----------
class TermosResposta(RespostaDTO):
    versao_atual: str
    versao_aceita: str | None
    aceitos_em: str | None
    pendente: bool


class SolicitacaoExclusaoResposta(RespostaDTO):
    mensagem: str
    solicitada_em: str


class PedidoExclusaoResposta(RespostaDTO):
    id: str
    nome: str
    email: str
    perfil: str
    ativo: bool
    solicitada_em: str

    @classmethod
    def de_entidade(cls, usuario: Usuario) -> "PedidoExclusaoResposta":
        return cls(
            id=str(usuario.id),
            nome=usuario.nome,
            email=usuario.email,
            perfil=usuario.tipo_usuario,
            ativo=usuario.ativo,
            solicitada_em=_iso(usuario.exclusao_solicitada_em) or "",
        )


class AnonimizacaoResposta(RespostaDTO):
    id: str
    nome: str
    anonimizado_em: str


# ---------- exportação (direito de acesso e portabilidade, art. 18, II e V) ----------
class TitularExportado(RespostaDTO):
    id: str
    nome: str
    email: str
    perfil: str
    conta_ativa: bool
    ultimo_acesso: str | None
    termos_versao: str | None
    termos_aceitos_em: str | None
    exclusao_solicitada_em: str | None

    @classmethod
    def de_entidade(cls, usuario: Usuario) -> "TitularExportado":
        return cls(
            id=str(usuario.id),
            nome=usuario.nome,
            email=usuario.email,
            perfil=usuario.tipo_usuario,
            conta_ativa=usuario.ativo,
            ultimo_acesso=_iso(usuario.ultimo_acesso),
            termos_versao=usuario.termos_versao,
            termos_aceitos_em=_iso(usuario.termos_aceitos_em),
            exclusao_solicitada_em=_iso(usuario.exclusao_solicitada_em),
        )


class EventoExportado(RespostaDTO):
    tipo: str
    descricao: str
    criado_em: str


class OcorrenciaExportada(RespostaDTO):
    id: str
    protocolo: str
    tipo: str
    titulo: str
    descricao: str | None
    local: str
    status: str
    anonima: bool
    anexos: list[dict[str, Any]]
    latitude: float | None
    longitude: float | None
    precisao_metros: float | None
    criado_em: str
    eventos: list[EventoExportado]

    @classmethod
    def de_entidade(cls, ocorrencia: Ocorrencia, eventos: list[EventoOcorrencia]) -> "OcorrenciaExportada":
        return cls(
            id=str(ocorrencia.id),
            protocolo=ocorrencia.protocolo,
            tipo=ocorrencia.tipo,
            titulo=ocorrencia.titulo,
            descricao=ocorrencia.descricao,
            local=ocorrencia.local,
            status=ocorrencia.status,
            anonima=ocorrencia.anonima,
            anexos=ocorrencia.anexos or [],
            latitude=ocorrencia.latitude,
            longitude=ocorrencia.longitude,
            precisao_metros=ocorrencia.precisao_metros,
            criado_em=ocorrencia.criado_em.isoformat(),
            eventos=[
                EventoExportado(tipo=evento.tipo, descricao=evento.descricao, criado_em=evento.criado_em.isoformat())
                for evento in eventos
            ],
        )


class NotificacaoExportada(RespostaDTO):
    tipo: str
    titulo: str
    mensagem: str
    ocorrencia_id: str | None
    criada_em: str
    lida: bool

    @classmethod
    def de_entidade(cls, notificacao: Notificacao) -> "NotificacaoExportada":
        return cls(
            tipo=notificacao.tipo,
            titulo=notificacao.titulo,
            mensagem=notificacao.mensagem,
            ocorrencia_id=str(notificacao.ocorrencia_id) if notificacao.ocorrencia_id else None,
            criada_em=notificacao.criada_em.isoformat(),
            lida=notificacao.lida,
        )


class DadosTitularResposta(RespostaDTO):
    gerado_em: str
    controlador: str
    versao_termos_atual: str
    titular: TitularExportado
    ocorrencias: list[OcorrenciaExportada]
    notificacoes: list[NotificacaoExportada]
