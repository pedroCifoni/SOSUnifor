"""Devolve à trilha de auditoria os eventos parados na fila "unisos.eventos.mortos".

A API já faz isso sozinha (30 s depois de subir e a cada 10 min); este script serve para
rodar na hora, por exemplo logo depois de o banco voltar de uma queda.

Uso, a partir de backend/ (com RABBITMQ_URL e DATABASE_URL do ambiente desejado):
    python -m scripts.reprocessar_eventos_mortos
"""

import asyncio

import aio_pika

from app.core import eventos
from app.core.config import configuracoes


async def reprocessar() -> None:
    conexao = await aio_pika.connect_robust(configuracoes.rabbitmq_url, timeout=10)
    try:
        canal = await conexao.channel()
        print("Resultado:", await eventos.reprocessar_mortos(canal, limite=10_000))
    finally:
        await conexao.close()


if __name__ == "__main__":
    asyncio.run(reprocessar())
