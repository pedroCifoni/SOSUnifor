from app.dtos.base import RespostaDTO
from app.entities.notificacao import Notificacao


class NotificacaoResposta(RespostaDTO):
    id: str
    destinatario_id: str
    tipo: str
    titulo: str
    mensagem: str
    ocorrencia_id: str
    criada_em: str
    lida: bool

    @classmethod
    def de_entidade(cls, notificacao: Notificacao) -> "NotificacaoResposta":
        return cls(
            id=str(notificacao.id),
            destinatario_id=str(notificacao.destinatario_id),
            tipo=notificacao.tipo,
            titulo=notificacao.titulo,
            mensagem=notificacao.mensagem,
            ocorrencia_id=str(notificacao.ocorrencia_id),
            criada_em=notificacao.criada_em.isoformat(),
            lida=notificacao.lida,
        )


class ResumoNotificacoesResposta(RespostaDTO):
    nao_lidas: int
