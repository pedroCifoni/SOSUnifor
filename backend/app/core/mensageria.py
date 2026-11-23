"""Publicação e consumo das notificações em tempo real pelo RabbitMQ."""

import json
import logging
from uuid import UUID

import aio_pika
from aio_pika import ExchangeType, Message

from app.core.config import configuracoes
from app.core.tempo_real import gerenciador_notificacoes

logger = logging.getLogger(__name__)

NOME_DA_EXCHANGE = "notificacoes"

_conexao: aio_pika.abc.AbstractRobustConnection | None = None
_exchange: aio_pika.abc.AbstractExchange | None = None


async def iniciar() -> None:
    """Conecta, declara a exchange e passa a consumir. Não derruba a API se o broker faltar."""
    global _conexao, _exchange
    try:
        _conexao = await aio_pika.connect_robust(configuracoes.rabbitmq_url, timeout=5)
        canal = await _conexao.channel()
        _exchange = await canal.declare_exchange(NOME_DA_EXCHANGE, ExchangeType.FANOUT, durable=True)
        fila = await canal.declare_queue(exclusive=True)
        await fila.bind(_exchange)
        await fila.consume(_receber)
        logger.info("RabbitMQ conectado; consumindo a exchange '%s'.", NOME_DA_EXCHANGE)
    except Exception:
        logger.warning("RabbitMQ indisponível; o aviso em tempo real fica só neste processo.", exc_info=True)
        _conexao, _exchange = None, None


def conexao() -> aio_pika.abc.AbstractRobustConnection | None:
    """A conexão com o broker (None sem RabbitMQ). Reaproveitada pelos eventos de domínio (app/core/eventos.py)."""
    return _conexao


async def encerrar() -> None:
    if _conexao is not None:
        await _conexao.close()


async def publicar(destinatarios: list[UUID]) -> None:
    """Publica os destinatários. Cada instância recebe a cópia e avisa seus WebSockets."""
    if _exchange is None:
        await gerenciador_notificacoes.avisar(destinatarios)
        return

    corpo = json.dumps({"destinatarios": [str(d) for d in set(destinatarios)]})
    try:
        await _exchange.publish(Message(body=corpo.encode()), routing_key="", timeout=2)
    except Exception:
        logger.warning("Falha ao publicar no RabbitMQ; avisando só este processo.")
        await gerenciador_notificacoes.avisar(destinatarios)


async def _receber(mensagem: aio_pika.abc.AbstractIncomingMessage) -> None:
    async with mensagem.process(requeue=False):
        dados = json.loads(mensagem.body)
        await gerenciador_notificacoes.avisar([UUID(d) for d in dados["destinatarios"]])
