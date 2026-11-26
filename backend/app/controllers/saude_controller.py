"""Saúde da API: liveness (o processo responde) e readiness (dependências prontas)."""

import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core import eventos, mensageria
from app.core.cache import cache
from app.core.config import configuracoes
from app.core.database import engine


router = APIRouter(tags=["Saúde"])
INICIO = time.monotonic()


@router.get("/health")
def verificar_saude() -> dict[str, str]:
    """Liveness: usado pelo Render para saber se o processo está no ar. Não consulta nada."""
    return {"service": "uni-sos-api", "status": "healthy"}


@router.get("/health/ready")
def verificar_prontidao() -> JSONResponse:
    """Readiness: banco obrigatório (503 se fora); RabbitMQ opcional (a API funciona em modo fallback)."""
    inicio = time.perf_counter()
    try:
        with engine.connect() as conexao:
            conexao.execute(text("SELECT 1"))
        banco = {"status": "ok", "latencia_ms": round((time.perf_counter() - inicio) * 1000, 1)}
    except Exception as erro:
        banco = {"status": "indisponivel", "erro": type(erro).__name__}

    broker_ok = mensageria.conexao() is not None and eventos.conectado()
    pronto = banco["status"] == "ok"
    corpo = {
        "service": "uni-sos-api",
        "status": "ready" if pronto else "not_ready",
        "ambiente": configuracoes.ambiente,
        "uptime_s": int(time.monotonic() - INICIO),
        "dependencias": {
            "postgres": banco,
            "rabbitmq": {"status": "ok" if broker_ok else "fallback_local"},
        },
        "cache": {"acertos": cache.acertos, "faltas": cache.faltas},
        "pool_conexoes": engine.pool.status(),
    }
    return JSONResponse(status_code=200 if pronto else 503, content=corpo)
