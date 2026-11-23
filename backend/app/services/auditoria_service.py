from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.database import FabricaSessao
from app.core.eventos import Evento
from app.core.excecoes import RegraDeNegocioErro
from app.dtos.auditoria_dto import RegistroAuditoriaResposta
from app.dtos.ocorrencia_dto import CursorPagina
from app.repositories.auditoria_repository import AuditoriaRepository


class AuditoriaService:
    def __init__(self, sessao: Session) -> None:
        self.sessao = sessao
        self.registros = AuditoriaRepository(sessao)

    def listar(
        self,
        cursor: CursorPagina | None = None,
        limite: int = 50,
        tipo: str | None = None,
        desde: datetime | None = None,
        ate: datetime | None = None,
    ) -> list[RegistroAuditoriaResposta]:
        if desde is not None and ate is not None and desde > ate:
            raise RegraDeNegocioErro("O início do período deve ser anterior ao fim.")
        cursor = cursor or CursorPagina()
        linhas = self.registros.listar_com_nome_do_ator(
            tipo=tipo.strip() if tipo else None,
            desde=_com_fuso(desde),
            ate=_com_fuso(ate),
            antes_de=cursor.antes_de,
            antes_id=cursor.antes_id,
            limite=limite,
        )
        return [RegistroAuditoriaResposta.de_entidade(registro, nome) for registro, nome in linhas]

    def registrar_evento(self, evento: Evento, origem: str) -> bool:
        """Grava o evento na trilha. Idempotente pelo id: devolve False se ele já estava lá."""
        dados = evento.dados
        novo = self.registros.registrar_se_novo(
            {
                "id": evento.id,
                "tipo": evento.tipo,
                "versao": evento.versao,
                "ocorrido_em": _com_fuso(evento.ocorrido_em),
                "ator_id": evento.ator_id,
                "entidade": _texto(dados.get("entidade"), 40),
                "entidade_id": _texto(dados.get("entidade_id"), 64),
                "resultado": "erro" if dados.get("resultado") == "erro" else "sucesso",
                "request_id": _texto(dados.get("request_id"), 64),
                "origem": origem,
                "dados": dados,
            }
        )
        self.sessao.commit()
        return novo


def gravar_evento(evento: Evento, origem: str) -> bool:
    """Grava numa sessão própria: usado pelo consumidor da fila e pelo fallback sem broker.

    Sessão separada da requisição de propósito: a trilha é gravada mesmo quando a operação
    auditada falhou e a sessão dela foi desfeita (rollback).
    """
    with FabricaSessao() as sessao:
        return AuditoriaService(sessao).registrar_evento(evento, origem)


def _com_fuso(data: datetime | None) -> datetime | None:
    if data is not None and data.tzinfo is None:
        return data.replace(tzinfo=timezone.utc)
    return data


def _texto(valor: object, tamanho: int) -> str | None:
    return None if valor is None else str(valor)[:tamanho]
