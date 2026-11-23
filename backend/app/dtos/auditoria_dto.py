from typing import Any

from app.dtos.base import RespostaDTO
from app.entities.registro_auditoria import RegistroAuditoria


PREFIXO_AUDITORIA = "auditoria."


class RegistroAuditoriaResposta(RespostaDTO):
    id: str
    tipo: str
    acao: str
    versao: int
    ocorrido_em: str
    ator_id: str | None
    ator_nome: str | None
    entidade: str | None
    entidade_id: str | None
    resultado: str
    request_id: str | None
    origem: str
    detalhes: dict[str, Any]
    erro: str | None

    @classmethod
    def de_entidade(cls, registro: RegistroAuditoria, nome_do_ator: str | None) -> "RegistroAuditoriaResposta":
        dados = registro.dados or {}
        return cls(
            id=str(registro.id),
            tipo=registro.tipo,
            acao=registro.tipo.removeprefix(PREFIXO_AUDITORIA),
            versao=registro.versao,
            ocorrido_em=registro.ocorrido_em.isoformat(),
            ator_id=str(registro.ator_id) if registro.ator_id else None,
            ator_nome=nome_do_ator,
            entidade=registro.entidade,
            entidade_id=registro.entidade_id,
            resultado=registro.resultado,
            request_id=registro.request_id,
            origem=registro.origem,
            # Eventos de auditoria guardam os detalhes em "detalhes"; eventos de domínio, no próprio "dados".
            detalhes=dados.get("detalhes") if isinstance(dados.get("detalhes"), dict) else {
                chave: valor
                for chave, valor in dados.items()
                if chave not in {"entidade", "entidade_id", "resultado", "request_id"}
            },
            erro=dados.get("erro"),
        )
