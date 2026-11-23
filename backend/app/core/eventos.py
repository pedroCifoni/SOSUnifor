"""Eventos de domínio no RabbitMQ: produção (com publisher confirms) e consumo (com ack manual).

Topologia (declarada por qualquer instância que sobe; as declarações são idempotentes):

    exchange TOPIC durável "unisos.eventos"
        ├── fila durável "unisos.auditoria"  (binding "#")           → grava a tabela auditoria
        └── fila durável "unisos.metricas"   (binding "ocorrencia.*") → contadores e indicadores no log
    exchange FANOUT durável "unisos.eventos.dlx"
        └── fila durável "unisos.eventos.mortos"  ← mensagens rejeitadas pelos consumidores

Formato do evento (JSON, versionado):
    {"id": uuid, "tipo": "ocorrencia.criada", "versao": 1, "ocorrido_em": ISO 8601,
     "ator_id": uuid | null, "dados": {...}}

O "tipo" é também a routing key. Os aspectos (app/core/aspectos.py) são os produtores.
Sem broker, ``publicar`` devolve False e o aspecto grava a auditoria direto no banco.
"""

import asyncio
import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import aio_pika
from aio_pika import DeliveryMode, ExchangeType, Message
from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)

EXCHANGE_EVENTOS = "unisos.eventos"
EXCHANGE_MORTOS = "unisos.eventos.dlx"
FILA_MORTOS = "unisos.eventos.mortos"
FILA_AUDITORIA = "unisos.auditoria"
BINDING_AUDITORIA = "#"
FILA_METRICAS = "unisos.metricas"
BINDING_METRICAS = "ocorrencia.*"
# Quantas mensagens cada consumidor pode ter em mãos sem ack: limita a memória e reparte entre workers.
PREFETCH = 10
# Tempo máximo esperando a confirmação do broker antes de cair no fallback.
TEMPO_CONFIRMACAO_SEGUNDOS = 3.0
VERSAO_ATUAL = 1


class Evento(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    tipo: str = Field(min_length=1, max_length=80)
    versao: int = VERSAO_ATUAL
    ocorrido_em: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ator_id: UUID | None = None
    dados: dict[str, Any] = Field(default_factory=dict)


_conexao: aio_pika.abc.AbstractRobustConnection | None = None
_exchange: aio_pika.abc.AbstractExchange | None = None
_loop: asyncio.AbstractEventLoop | None = None


# ---------- ciclo de vida ----------
async def iniciar(conexao: aio_pika.abc.AbstractRobustConnection | None) -> None:
    """Declara a topologia e inicia os consumidores na conexão já aberta pela mensageria.

    Reaproveitar a conexão economiza conexões no CloudAMQP (o plano gratuito tem limite).
    Sem conexão (broker fora do ar), fica no modo fallback e não derruba a API.
    """
    global _conexao, _exchange, _loop
    if conexao is None:
        logger.warning("RabbitMQ indisponível para eventos; a auditoria será gravada direto no banco.")
        return
    try:
        _conexao = conexao
        canal_publicacao = await _conexao.channel(publisher_confirms=True)
        _exchange = await canal_publicacao.declare_exchange(EXCHANGE_EVENTOS, ExchangeType.TOPIC, durable=True)

        canal_consumo = await _conexao.channel()
        await canal_consumo.set_qos(prefetch_count=PREFETCH)
        exchange = await canal_consumo.declare_exchange(EXCHANGE_EVENTOS, ExchangeType.TOPIC, durable=True)
        mortos = await canal_consumo.declare_exchange(EXCHANGE_MORTOS, ExchangeType.FANOUT, durable=True)
        fila_mortos = await canal_consumo.declare_queue(FILA_MORTOS, durable=True)
        await fila_mortos.bind(mortos)

        argumentos = {"x-dead-letter-exchange": EXCHANGE_MORTOS}
        fila_auditoria = await canal_consumo.declare_queue(FILA_AUDITORIA, durable=True, arguments=argumentos)
        await fila_auditoria.bind(exchange, routing_key=BINDING_AUDITORIA)
        await fila_auditoria.consume(consumir_auditoria)

        fila_metricas = await canal_consumo.declare_queue(FILA_METRICAS, durable=True, arguments=argumentos)
        await fila_metricas.bind(exchange, routing_key=BINDING_METRICAS)
        await fila_metricas.consume(consumir_metricas)

        _loop = asyncio.get_running_loop()
        logger.info("Eventos: exchange '%s' pronta; consumindo '%s' e '%s'.", EXCHANGE_EVENTOS, FILA_AUDITORIA, FILA_METRICAS)
    except Exception:
        logger.warning("RabbitMQ indisponível para eventos; a auditoria será gravada direto no banco.", exc_info=True)
        await encerrar()


async def encerrar() -> None:
    """Esquece a conexão; quem a fecha é a mensageria, que a abriu."""
    global _conexao, _exchange, _loop
    _conexao, _exchange, _loop = None, None, None


def conectado() -> bool:
    return _exchange is not None and _loop is not None and not _loop.is_closed()


# ---------- produção ----------
async def publicar_async(evento: Evento) -> None:
    """Publica e aguarda o "ack" do broker (publisher confirm). Lança exceção se não confirmar."""
    if _exchange is None:
        raise RuntimeError("Broker de eventos não conectado.")
    mensagem = Message(
        body=evento.model_dump_json().encode(),
        content_type="application/json",
        delivery_mode=DeliveryMode.PERSISTENT,
        message_id=str(evento.id),
        type=evento.tipo,
        timestamp=evento.ocorrido_em,
    )
    await _exchange.publish(mensagem, routing_key=evento.tipo, timeout=TEMPO_CONFIRMACAO_SEGUNDOS)


def publicar(evento: Evento) -> bool:
    """Publica a partir de código síncrono (services rodam no threadpool).

    Agenda a publicação no event loop da aplicação e espera a confirmação do broker.
    Devolve False quando não foi possível publicar: quem chamou decide o fallback.
    """
    loop = _loop
    if not conectado() or loop is None:
        return False
    try:
        asyncio.get_running_loop()
        return False  # já estamos dentro de um event loop: não dá para bloquear esperando o broker
    except RuntimeError:
        pass
    futuro = asyncio.run_coroutine_threadsafe(publicar_async(evento), loop)
    try:
        futuro.result(timeout=TEMPO_CONFIRMACAO_SEGUNDOS + 1)
        return True
    except Exception:
        futuro.cancel()
        logger.warning("Evento %s (%s) não confirmado pelo RabbitMQ.", evento.id, evento.tipo, exc_info=True)
        return False


# ---------- consumo ----------
async def _rejeitar(mensagem: aio_pika.abc.AbstractIncomingMessage, motivo: str) -> None:
    """Falha transitória ganha uma nova tentativa; na segunda vai para a fila de mortos (nunca trava a fila)."""
    if not mensagem.redelivered:
        logger.warning("Evento %s: %s; devolvido à fila para nova tentativa.", mensagem.message_id, motivo)
        await mensagem.nack(requeue=True)
    else:
        logger.error("Evento %s: %s; enviado para '%s'.", mensagem.message_id, motivo, FILA_MORTOS)
        await mensagem.reject(requeue=False)


async def consumir_auditoria(mensagem: aio_pika.abc.AbstractIncomingMessage) -> None:
    """Grava o evento na tabela de auditoria. Idempotente: reentregas não duplicam o registro."""
    from app.services.auditoria_service import gravar_evento  # import tardio: core não depende de services ao carregar

    try:
        evento = Evento.model_validate_json(mensagem.body)
    except Exception:
        logger.error("Evento %s inválido; enviado para '%s'.", mensagem.message_id, FILA_MORTOS)
        await mensagem.reject(requeue=False)
        return
    try:
        await asyncio.to_thread(gravar_evento, evento, "broker")
    except Exception as erro:
        await _rejeitar(mensagem, f"falha ao gravar a auditoria ({type(erro).__name__})")
        return
    await mensagem.ack()


class Indicadores:
    """Contadores por processo alimentados pela fila "unisos.metricas"."""

    def __init__(self) -> None:
        self.por_evento: Counter[str] = Counter()
        self.por_tipo_de_ocorrencia: Counter[str] = Counter()

    def registrar(self, evento: Evento) -> None:
        self.por_evento[evento.tipo] += 1
        if evento.tipo == "ocorrencia.criada" and evento.dados.get("tipo_ocorrencia"):
            self.por_tipo_de_ocorrencia[str(evento.dados["tipo_ocorrencia"])] += 1


indicadores = Indicadores()


async def consumir_metricas(mensagem: aio_pika.abc.AbstractIncomingMessage) -> None:
    try:
        evento = Evento.model_validate_json(mensagem.body)
        indicadores.registrar(evento)
    except Exception:
        logger.error("Evento %s inválido para métricas; enviado para '%s'.", mensagem.message_id, FILA_MORTOS)
        await mensagem.reject(requeue=False)
        return
    logger.info(
        "Indicadores: %s (total %d) | ocorrências criadas por tipo: %s",
        evento.tipo,
        indicadores.por_evento[evento.tipo],
        dict(indicadores.por_tipo_de_ocorrencia),
    )
    await mensagem.ack()
