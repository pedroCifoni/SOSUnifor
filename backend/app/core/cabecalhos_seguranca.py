"""Cabeçalhos HTTP de segurança em todas as respostas da API (OWASP Secure Headers)."""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import configuracoes


# A documentação interativa (Swagger/ReDoc) carrega scripts de CDN; as demais rotas só devolvem dados.
ROTAS_DE_DOCUMENTACAO = ("/docs", "/redoc", "/openapi.json")

CABECALHOS_FIXOS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}
CSP_DA_API = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"


class CabecalhosSeguranca(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        resposta = await call_next(request)
        for nome, valor in CABECALHOS_FIXOS.items():
            resposta.headers.setdefault(nome, valor)
        if not request.url.path.startswith(ROTAS_DE_DOCUMENTACAO):
            resposta.headers.setdefault("Content-Security-Policy", CSP_DA_API)
        if configuracoes.ambiente.lower() in {"producao", "production"}:
            resposta.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        # Respostas autenticadas não ficam em cache compartilhado (proxies).
        if "authorization" in request.headers:
            resposta.headers.setdefault("Cache-Control", "no-store")
        return resposta
