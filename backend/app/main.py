import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.controllers import routers
from app.core import mensageria
from app.core.config import obter_origens_cors, validar_configuracao_de_producao
from app.core.excecoes import ErroAplicacao
from app.core.inicializacao_banco import inicializar_banco


logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    validar_configuracao_de_producao()
    inicializar_banco()
    await mensageria.iniciar()
    yield
    await mensageria.encerrar()


app = FastAPI(title="UniSOS API", version="1.0.0", lifespan=ciclo_de_vida)
app.add_middleware(
    CORSMiddleware,
    allow_origins=obter_origens_cors(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ErroAplicacao)
async def tratar_erro_da_aplicacao(_: Request, erro: ErroAplicacao) -> JSONResponse:
    return JSONResponse(status_code=erro.status_code, content={"detail": erro.mensagem})


for router in routers:
    app.include_router(router)
