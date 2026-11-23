"""Aspecto da camada HTTP: request id, tempo e status de cada requisição e mascaramento de dados sensíveis nos logs.

É um middleware ASGI puro: o "advice around" envolve TODAS as requisições (o ponto de
corte é "toda requisição HTTP"), sem que nenhum controller precise saber dele.
"""

import logging
import re
import time
from collections.abc import Iterable
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core import contexto_requisicao

logger = logging.getLogger("app.http")

CABECALHO_REQUEST_ID = "X-Request-ID"
# Aceita o id vindo do cliente/proxy só se for curto e "inofensivo"; senão gera um novo.
PADRAO_REQUEST_ID_VALIDO = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

# ---------- mascaramento ----------
MASCARA = "***"
PADROES_SENSIVEIS = [
    # ?token=... / &access_token=... (o WebSocket /ws/notificacoes recebe o JWT na query string)
    (re.compile(r"((?:access_)?token=)[^&\s\"']+", re.IGNORECASE), rf"\1{MASCARA}"),
    # Authorization: Bearer <jwt>
    (re.compile(r"(Bearer\s+)[A-Za-z0-9._~+/=-]+", re.IGNORECASE), rf"\1{MASCARA}"),
    # "senha": "..." / senha=...
    (re.compile(r"((?:senha|password)[\"']?\s*[:=]\s*[\"']?)[^\"'&\s,}]+", re.IGNORECASE), rf"\1{MASCARA}"),
]


def mascarar(texto: str) -> str:
    for padrao, substituto in PADROES_SENSIVEIS:
        texto = padrao.sub(substituto, texto)
    return texto


class FiltroDadosSensiveis(logging.Filter):
    """Filtro de logging que mascara token, Bearer e senha na mensagem e nos argumentos do registro."""

    def filter(self, registro: logging.LogRecord) -> bool:
        if isinstance(registro.msg, str):
            registro.msg = mascarar(registro.msg)
        if isinstance(registro.args, tuple):
            registro.args = tuple(mascarar(a) if isinstance(a, str) else a for a in registro.args)
        elif isinstance(registro.args, dict):
            registro.args = {k: mascarar(v) if isinstance(v, str) else v for k, v in registro.args.items()}
        # Padrão que atravessa mensagem e argumento ("Bearer %s"): mascara o texto já montado.
        # Só nesse caso os args são descartados (o formatter do uvicorn.access precisa da tupla original).
        try:
            montada = registro.getMessage()
        except Exception:
            return True
        mascarada = mascarar(montada)
        if mascarada != montada:
            registro.msg, registro.args = mascarada, None
        return True


_filtro = FiltroDadosSensiveis()
LOGGERS_MASCARADOS = ("", "uvicorn", "uvicorn.access", "uvicorn.error", "app", "httpx")


def instalar_mascaramento_de_logs(nomes: Iterable[str] = LOGGERS_MASCARADOS) -> None:
    """Aplica o filtro aos loggers e aos seus handlers. Idempotente; pode rodar várias vezes.

    Filtro em logger só vale para registros emitidos nele; filtro em handler vale para tudo que
    passa por ele (inclusive o que vem propagado de loggers filhos). Por isso, os dois.
    O uvicorn configura os próprios handlers antes de carregar a aplicação, então chamar isto
    na importação de app.main já pega o "uvicorn.access" (que grava a URL com ?token=...).
    """
    for nome in nomes:
        registrador = logging.getLogger(nome)
        if _filtro not in registrador.filters:
            registrador.addFilter(_filtro)
        for handler in registrador.handlers:
            if _filtro not in handler.filters:
                handler.addFilter(_filtro)


# ---------- middleware ----------
def _request_id_de(scope: Scope) -> str:
    for nome, valor in scope.get("headers") or []:
        if nome.decode("latin-1").lower() == CABECALHO_REQUEST_ID.lower():
            candidato = valor.decode("latin-1").strip()
            if PADRAO_REQUEST_ID_VALIDO.match(candidato):
                return candidato
    return uuid4().hex


class AspectoHttp:
    """Middleware ASGI: abre o contexto da requisição, devolve X-Request-ID e registra método, rota, status e tempo."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return

        request_id = _request_id_de(scope)
        token = contexto_requisicao.iniciar(request_id)
        inicio = time.perf_counter()
        status = 500

        async def enviar(mensagem: Message) -> None:
            nonlocal status
            if mensagem["type"] == "http.response.start":
                status = mensagem["status"]
                cabecalhos = list(mensagem.get("headers", []))
                cabecalhos.append((CABECALHO_REQUEST_ID.lower().encode(), request_id.encode()))
                mensagem = {**mensagem, "headers": cabecalhos}
            await send(mensagem)

        try:
            await self.app(scope, receive, enviar)
        finally:
            if scope["type"] == "http":
                # Só o caminho, nunca a query string: ela pode carregar token.
                logger.info(
                    "%s %s -> %s em %.1f ms [request_id=%s]",
                    scope.get("method", "-"),
                    scope.get("path", "-"),
                    status,
                    (time.perf_counter() - inicio) * 1000,
                    request_id,
                )
            contexto_requisicao.encerrar(token)
