from collections.abc import Callable, Iterable
from uuid import UUID

from sqlalchemy.orm import Session

from app.dtos.notificacao_dto import NotificacaoResposta
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

    def listar(self, usuario: Usuario) -> list[NotificacaoResposta]:
        return [NotificacaoResposta.de_entidade(n) for n in self.notificacoes.listar_do_destinatario(usuario.id)]

    def marcar_todas_como_lidas(self, usuario: Usuario) -> None:
        for notificacao in self.notificacoes.listar_nao_lidas(usuario.id):
            notificacao.lida = True
        self.sessao.commit()

    def criar(
        self,
        destinatarios: Iterable[UUID],
        tipo: str,
        titulo: str,
        mensagem: str,
        ocorrencia_id: UUID,
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
