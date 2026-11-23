from collections.abc import Callable, Iterable
from uuid import UUID

from sqlalchemy.orm import Session

from app.dtos.notificacao_dto import NotificacaoResposta, ResumoNotificacoesResposta
from app.dtos.ocorrencia_dto import CursorPagina
from app.entities.notificacao import Notificacao
from app.entities.usuario import Usuario
from app.repositories.notificacao_repository import NotificacaoRepository


# Recebe os ids que devem ser avisados em tempo real (WebSocket) depois do commit.
AvisarEmTempoReal = Callable[[list[UUID]], None]


def nao_avisar(_: list[UUID]) -> None:
    return None


class NotificacaoService:
    def __init__(self, sessao: Session, avisar: AvisarEmTempoReal = nao_avisar) -> None:
        self.sessao = sessao
        self.notificacoes = NotificacaoRepository(sessao)
        self.avisar = avisar

    def listar(self, usuario: Usuario, cursor: CursorPagina | None = None, limite: int = 50) -> list[NotificacaoResposta]:
        cursor = cursor or CursorPagina()
        notificacoes = self.notificacoes.listar_do_destinatario(
            usuario.id, antes_de=cursor.antes_de, antes_id=cursor.antes_id, limite=limite
        )
        return [NotificacaoResposta.de_entidade(n) for n in notificacoes]

    def resumir(self, usuario: Usuario) -> ResumoNotificacoesResposta:
        return ResumoNotificacoesResposta(nao_lidas=self.notificacoes.contar_nao_lidas(usuario.id))

    def marcar_todas_como_lidas(self, usuario: Usuario) -> None:
        self.notificacoes.marcar_todas_como_lidas(usuario.id)
        self.sessao.commit()

    def criar(
        self,
        destinatarios: Iterable[UUID],
        tipo: str,
        titulo: str,
        mensagem: str,
        ocorrencia_id: UUID | None,
        ignorar_usuario_id: UUID | None = None,
    ) -> None:
        """Cria uma notificação por destinatário (sem repetir), sem notificar quem fez a ação."""
        for destinatario in set(destinatarios):
            if destinatario == ignorar_usuario_id:
                continue
            self.notificacoes.adicionar(
                Notificacao(
                    destinatario_id=destinatario,
                    tipo=tipo,
                    titulo=titulo,
                    mensagem=mensagem,
                    ocorrencia_id=ocorrencia_id,
                )
            )
