import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.controllers import routers
from app.core import eventos, mensageria
from app.core.aspecto_http import AspectoHttp, instalar_mascaramento_de_logs
from app.core.aspectos import tecer_aspectos_transversais
from app.core.config import configuracoes, obter_origens_cors, validar_configuracao_de_producao
from app.core.excecoes import ErroAplicacao
from app.core.inicializacao_banco import inicializar_banco


def regex_origem_de_rede_em_desenvolvimento() -> str | None:
    """Permite a demonstração por dispositivos da mesma rede, nunca em produção."""
    if configuracoes.ambiente.lower() in {"producao", "production"}:
        return None
    return r"^http://(?:localhost|127\.0\.0\.1|10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}):\d+$"


logging.basicConfig(level=logging.INFO)
# Mascara token=..., Bearer e senha em todos os logs (inclusive no log de acesso do uvicorn).
instalar_mascaramento_de_logs()
# Tecelagem (weaving) por padrão: medir_desempenho em todos os métodos públicos dos services.
tecer_aspectos_transversais(configuracoes.desempenho_limite_ms)


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    validar_configuracao_de_producao()
    instalar_mascaramento_de_logs()
    inicializar_banco()
    await mensageria.iniciar()
    await eventos.iniciar(mensageria.conexao())
    try:
        yield
    finally:
        await eventos.encerrar()
        await mensageria.encerrar()


app = FastAPI(title="UniSOS API", version="1.0.0", lifespan=ciclo_de_vida)
app.add_middleware(
    CORSMiddleware,
    allow_origins=obter_origens_cors(),
    allow_origin_regex=regex_origem_de_rede_em_desenvolvimento(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)
# Registrado por último = camada mais externa: mede e identifica a requisição inteira.
app.add_middleware(AspectoHttp)


@app.exception_handler(ErroAplicacao)
async def tratar_erro_da_aplicacao(_: Request, erro: ErroAplicacao) -> JSONResponse:
    return JSONResponse(status_code=erro.status_code, content={"detail": erro.mensagem})


for router in routers:
    app.include_router(router)
