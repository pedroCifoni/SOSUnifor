"""Avisos em tempo real entre várias instâncias/workers da API via Postgres LISTEN/NOTIFY.

Cada processo guarda só as suas conexões WebSocket (ver ``tempo_real.py``). Com
TEMPO_REAL_DISTRIBUIDO=true, o aviso é publicado no canal do banco e cada processo,
pelo seu ouvinte, entrega às conexões que tem localmente.
"""

import asyncio
import json
import logging
import threading
from collections.abc import Awaitable, Callable
from uuid import UUID

import psycopg
from sqlalchemy import text

from app.core.config import configuracoes


logger = logging.getLogger("uvicorn.error")

CANAL = "unisos_notificacoes"
# O payload do NOTIFY aceita menos de 8000 bytes. Cada id ocupa ~39 bytes no JSON,
# então 150 ids por aviso (~6 KB) deixam folga.
IDS_POR_AVISO = 150
# Sem avisos por este tempo, o ouvinte testa a conexão (detecta queda silenciosa).
INTERVALO_VERIFICACAO_SEGUNDOS = 60
ESPERA_MAXIMA_RECONEXAO_SEGUNDOS = 60

Entregar = Callable[[list[UUID]], Awaitable[None]]


# ---------- publicação ----------
def montar_payloads(destinatarios: list[UUID]) -> list[str]:
    ids = list(dict.fromkeys(str(destinatario) for destinatario in destinatarios))
    return [
        json.dumps({"ids": ids[inicio : inicio + IDS_POR_AVISO]}, separators=(",", ":"))
        for inicio in range(0, len(ids), IDS_POR_AVISO)
    ]


def publicar_aviso(destinatarios: list[UUID]) -> None:
    """Publica o aviso no canal do banco (roda em thread, via BackgroundTasks).

    Usa a engine normal da aplicação: pg_notify funciona também pelo pooler.
    """
    payloads = montar_payloads(destinatarios)
    if not payloads:
        return
    from app.core.database import engine

    try:
        with engine.begin() as conexao:
            for payload in payloads:
                conexao.execute(text("SELECT pg_notify(:canal, :payload)"), {"canal": CANAL, "payload": payload})
    except Exception:
        logger.exception("Tempo real: falha ao publicar aviso no canal '%s'.", CANAL)


# ---------- ouvinte ----------
def url_do_ouvinte() -> str:
    url = configuracoes.database_url_direta or configuracoes.database_url
    for prefixo in ("postgresql+psycopg://", "postgresql+psycopg2://", "postgres://"):
        if url.startswith(prefixo):
            return "postgresql://" + url[len(prefixo) :]
    return url


def _ler_ids(payload: str) -> list[UUID]:
    try:
        return [UUID(valor) for valor in json.loads(payload).get("ids", [])]
    except (ValueError, TypeError, AttributeError):
        logger.warning("Tempo real: aviso ignorado, payload inválido: %.200s", payload)
        return []


async def _escutar(url: str, entregar: Entregar, avisar_todos: Callable[[], Awaitable[None]]) -> None:
    """Mantém um LISTEN aberto e reconecta com backoff quando a conexão cai."""
    espera = 1
    ja_conectou = False
    while True:
        try:
            async with await psycopg.AsyncConnection.connect(url, autocommit=True) as conexao:
                await conexao.execute(f"LISTEN {CANAL}")
                logger.info("Tempo real: escutando o canal '%s' no banco.", CANAL)
                espera = 1
                if ja_conectou:
                    # Avisos publicados enquanto estava desconectado se perderam:
                    # pede a todos os conectados aqui que recarreguem as notificações.
                    await avisar_todos()
                ja_conectou = True
                while True:
                    async for aviso in conexao.notifies(timeout=INTERVALO_VERIFICACAO_SEGUNDOS):
                        ids = _ler_ids(aviso.payload)
                        if ids:
                            await entregar(ids)
                    await conexao.execute("SELECT 1")
        except asyncio.CancelledError:
            raise
        except Exception as erro:
            logger.warning(
                "Tempo real: ouvinte sem conexão com o banco (%s). Nova tentativa em %ss.",
                erro.__class__.__name__,
                espera,
            )
            await asyncio.sleep(espera)
            espera = min(espera * 2, ESPERA_MAXIMA_RECONEXAO_SEGUNDOS)


class OuvinteNotificacoes:
    """Tarefa de fundo do processo da API que entrega os avisos do canal às conexões locais.

    O psycopg assíncrono não funciona com o ProactorEventLoop (padrão do uvicorn no
    Windows com um só processo). Nesse caso o ouvinte roda num thread com loop próprio
    e entrega os avisos no loop principal.
    """

    def __init__(self, gerenciador) -> None:
        self.gerenciador = gerenciador
        self._tarefa: asyncio.Task | None = None
        self._thread: threading.Thread | None = None
        self._loop_thread: asyncio.AbstractEventLoop | None = None
        self._tarefa_thread: asyncio.Task | None = None

    async def _avisar_todos(self) -> None:
        await self.gerenciador.avisar(list(self.gerenciador.conexoes))

    async def iniciar(self) -> None:
        url = url_do_ouvinte()
        if "-pooler" in url:
            logger.warning(
                "Tempo real: o ouvinte está usando um endpoint com '-pooler'. LISTEN NÃO funciona "
                "através do pooler em modo transação (Neon/PgBouncer) e os avisos entre instâncias "
                "não vão chegar. Defina DATABASE_URL_DIRETA com o endpoint sem '-pooler'."
            )
        loop_principal = asyncio.get_running_loop()
        if not isinstance(loop_principal, getattr(asyncio, "ProactorEventLoop", ())):
            self._tarefa = asyncio.create_task(
                _escutar(url, self.gerenciador.avisar, self._avisar_todos), name="ouvinte-tempo-real"
            )
            return

        async def entregar_no_loop_principal(ids: list[UUID]) -> None:
            futuro = asyncio.run_coroutine_threadsafe(self.gerenciador.avisar(ids), loop_principal)
            await asyncio.wrap_future(futuro)

        async def avisar_todos_no_loop_principal() -> None:
            futuro = asyncio.run_coroutine_threadsafe(self._avisar_todos(), loop_principal)
            await asyncio.wrap_future(futuro)

        # Loop e tarefa são criados ANTES de iniciar o thread: assim parar(), mesmo chamado logo
        # após iniciar(), sempre encontra a tarefa para cancelar (call_soon_threadsafe enfileira o
        # cancelamento e ele roda assim que o loop do thread começar).
        loop = asyncio.SelectorEventLoop()
        tarefa = loop.create_task(_escutar(url, entregar_no_loop_principal, avisar_todos_no_loop_principal))
        self._loop_thread = loop
        self._tarefa_thread = tarefa

        def executar() -> None:
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(tarefa)
            except asyncio.CancelledError:
                pass
            finally:
                loop.close()

        self._thread = threading.Thread(target=executar, name="ouvinte-tempo-real", daemon=True)
        self._thread.start()

    async def parar(self) -> None:
        if self._tarefa is not None:
            self._tarefa.cancel()
            try:
                await self._tarefa
            except asyncio.CancelledError:
                pass
            self._tarefa = None
        if self._thread is not None:
            if self._loop_thread is not None and self._tarefa_thread is not None:
                try:
                    self._loop_thread.call_soon_threadsafe(self._tarefa_thread.cancel)
                except RuntimeError:
                    pass  # o loop do thread já terminou e foi fechado

            await asyncio.to_thread(self._thread.join, 5)
            if self._thread.is_alive():
                logger.warning("Tempo real: o ouvinte não terminou em 5 s; ele será encerrado junto com o processo.")
            self._thread = None
            self._loop_thread = None
            self._tarefa_thread = None
