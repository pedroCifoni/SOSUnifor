from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.core.database import FabricaSessao
from app.core.excecoes import NaoAutenticadoErro
from app.core.seguranca import ler_id_do_token
from app.core.tempo_real import gerenciador_notificacoes
from app.repositories.usuario_repository import UsuarioRepository


router = APIRouter(tags=["Tempo real"])


@router.websocket("/ws/notificacoes")
async def acompanhar_notificacoes(websocket: WebSocket) -> None:
    """Mantém o canal aberto e avisa o front quando chegam novas notificações."""
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    try:
        usuario_id = ler_id_do_token(token)
    except NaoAutenticadoErro:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    with FabricaSessao() as sessao:
        usuario = UsuarioRepository(sessao).buscar_por_id(usuario_id)
        if usuario is None or not usuario.ativo:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    await gerenciador_notificacoes.conectar(usuario_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        gerenciador_notificacoes.desconectar(usuario_id, websocket)
