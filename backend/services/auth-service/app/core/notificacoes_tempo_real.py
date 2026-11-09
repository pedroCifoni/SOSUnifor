"""Canal WebSocket para avisar o front-end que há novas notificações."""

from collections import defaultdict
from uuid import UUID

from fastapi import WebSocket


class GerenciadorNotificacoesTempoReal:
    def __init__(self) -> None:
        self.conexoes: dict[UUID, set[WebSocket]] = defaultdict(set)

    async def conectar(self, usuario_id: UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        self.conexoes[usuario_id].add(websocket)

    def desconectar(self, usuario_id: UUID, websocket: WebSocket) -> None:
        conexoes = self.conexoes.get(usuario_id)
        if conexoes is None:
            return
        conexoes.discard(websocket)
        if not conexoes:
            self.conexoes.pop(usuario_id, None)

    async def avisar(self, destinatarios: list[UUID]) -> None:
        for destinatario in set(destinatarios):
            for websocket in list(self.conexoes.get(destinatario, set())):
                try:
                    await websocket.send_json({"tipo": "notificacoes_atualizadas"})
                except Exception:
                    self.desconectar(destinatario, websocket)


gerenciador_notificacoes = GerenciadorNotificacoesTempoReal()
