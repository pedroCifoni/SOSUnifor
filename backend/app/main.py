from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.controllers import routers
from app.core.config import configuracoes, obter_origens_cors, validar_configuracao_de_producao
from app.core.excecoes import ErroAplicacao
from app.core.inicializacao_banco import inicializar_banco
from app.core.tempo_real import gerenciador_notificacoes
from app.core.tempo_real_distribuido import OuvinteNotificacoes


def regex_origem_de_rede_em_desenvolvimento() -> str | None:
    """Permite a demonstração por dispositivos da mesma rede, nunca em produção."""
    if configuracoes.ambiente.lower() in {"producao", "production"}:
        return None
    return r"^http://(?:localhost|127\.0\.0\.1|10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}):\d+$"


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    validar_configuracao_de_producao()
    inicializar_banco()
    ouvinte = OuvinteNotificacoes(gerenciador_notificacoes) if configuracoes.tempo_real_distribuido else None
    if ouvinte is not None:
        await ouvinte.iniciar()
    try:
        yield
    finally:
        if ouvinte is not None:
            await ouvinte.parar()


app = FastAPI(title="UniSOS API", version="1.0.0", lifespan=ciclo_de_vida)
app.add_middleware(
    CORSMiddleware,
    allow_origins=obter_origens_cors(),
    allow_origin_regex=regex_origem_de_rede_em_desenvolvimento(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ErroAplicacao)
async def tratar_erro_da_aplicacao(_: Request, erro: ErroAplicacao) -> JSONResponse:
    return JSONResponse(status_code=erro.status_code, content={"detail": erro.mensagem})


for router in routers:
    app.include_router(router)
