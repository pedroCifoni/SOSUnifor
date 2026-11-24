"""Eventos de domínio no RabbitMQ: produção (com publisher confirms) e consumo (com ack manual).

Topologia (declarada por qualquer instância que sobe; as declarações são idempotentes):

    exchange TOPIC durável "unisos.eventos"
        ├── fila durável "unisos.auditoria"  (binding "#")           → grava a tabela auditoria
        └── fila durável "unisos.metricas"   (binding "ocorrencia.*") → contadores (por processo) no log
    exchange FANOUT durável "unisos.eventos.dlx"
        └── fila durável "unisos.eventos.mortos"  ← mensagens rejeitadas pelos consumidores;
                                                    reprocessada de tempos em tempos (reprocessar_mortos)

Formato do evento (JSON, versionado):
    {"id": uuid, "tipo": "ocorrencia.criada", "versao": 1, "ocorrido_em": ISO 8601,
     "ator_id": uuid | null, "dados": {...}}

O "tipo" é também a routing key. Os aspectos (app/core/aspectos.py) são os produtores.
Sem broker, ``publicar`` devolve False e o aspecto grava a auditoria direto no banco.
"""

import asyncio
import logging
import os
import time
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
TEMPO_CONFIRMACAO_SEGUNDOS = 1.5
# Depois de uma confirmação que não chegou, o broker é tratado como degradado por este tempo:
# as publicações vão direto ao fallback, sem cada requisição esperar o timeout de novo.
PAUSA_BROKER_DEGRADADO_SEGUNDOS = 30.0
# Esperas entre as tentativas do consumidor de gravar a auditoria (cobrem uma queda curta do banco,
# como um cold start do Neon). Só depois de todas a mensagem vai para a fila de mortos.
ESPERAS_NOVA_TENTATIVA_SEGUNDOS = (1.0, 3.0, 10.0, 30.0)
# Reprocessamento automático da fila de mortos: primeira rodada logo depois da subida, depois periódica.
ATRASO_PRIMEIRO_REPROCESSAMENTO_SEGUNDOS = 30.0
INTERVALO_REPROCESSAMENTO_SEGUNDOS = 600.0
# Cabeçalho que conta quantas vezes uma mensagem já voltou da fila de mortos sem sucesso.
CABECALHO_REPROCESSAMENTOS = "x-unisos-reprocessamentos"
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
_tarefa_reprocessamento: asyncio.Task | None = None
_degradado_ate = 0.0  # time.monotonic() até quando o broker é tratado como degradado


# ---------- ciclo de vida ----------
async def iniciar(conexao: aio_pika.abc.AbstractRobustConnection | None) -> None:
    """Declara a topologia e inicia os consumidores na conexão já aberta pela mensageria.

    Reaproveitar a conexão economiza conexões no CloudAMQP (o plano gratuito tem limite).
    Sem conexão (broker fora do ar), fica no modo fallback e não derruba a API.
    """
    global _conexao, _exchange, _loop, _tarefa_reprocessamento
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
        _tarefa_reprocessamento = asyncio.create_task(_reprocessar_periodicamente(canal_consumo))
        logger.info("Eventos: exchange '%s' pronta; consumindo '%s' e '%s'.", EXCHANGE_EVENTOS, FILA_AUDITORIA, FILA_METRICAS)
    except Exception:
        logger.warning("RabbitMQ indisponível para eventos; a auditoria será gravada direto no banco.", exc_info=True)
        await encerrar()


async def encerrar() -> None:
    """Esquece a conexão; quem a fecha é a mensageria, que a abriu."""
    global _conexao, _exchange, _loop, _tarefa_reprocessamento
    if _tarefa_reprocessamento is not None:
        _tarefa_reprocessamento.cancel()
    _conexao, _exchange, _loop, _tarefa_reprocessamento = None, None, None, None


def conectado() -> bool:
    return _exchange is not None and _loop is not None and not _loop.is_closed()


def degradado() -> bool:
    """True logo depois de uma confirmação que não chegou (ver PAUSA_BROKER_DEGRADADO_SEGUNDOS)."""
    return time.monotonic() < _degradado_ate


def _marcar_degradado() -> None:
    global _degradado_ate
    _degradado_ate = time.monotonic() + PAUSA_BROKER_DEGRADADO_SEGUNDOS


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
    Com o broker degradado (confirmação recente que não chegou), nem tenta: devolve False na hora.
    """
    loop = _loop
    if not conectado() or loop is None or degradado():
        return False
    try:
        asyncio.get_running_loop()
        return False  # já estamos dentro de um event loop: não dá para bloquear esperando o broker
    except RuntimeError:
        pass
    futuro = asyncio.run_coroutine_threadsafe(publicar_async(evento), loop)
    try:
        futuro.result(timeout=TEMPO_CONFIRMACAO_SEGUNDOS + 0.5)
        return True
    except Exception:
        futuro.cancel()
        _marcar_degradado()
        logger.warning(
            "Evento %s (%s) não confirmado pelo RabbitMQ; publicações vão direto ao banco pelos próximos %.0f s.",
            evento.id,
            evento.tipo,
            PAUSA_BROKER_DEGRADADO_SEGUNDOS,
            exc_info=True,
        )
        return False


# ---------- consumo ----------
async def _esperar(segundos: float) -> None:
    await asyncio.sleep(segundos)


async def _gravar_com_novas_tentativas(evento: Evento) -> None:
    """Grava a auditoria (idempotente); falha transitória ganha novas tentativas com espera crescente."""
    from app.services.auditoria_service import gravar_evento  # import tardio: core não depende de services ao carregar

    for espera in (*ESPERAS_NOVA_TENTATIVA_SEGUNDOS, None):
        try:
            await asyncio.to_thread(gravar_evento, evento, "broker")
            return
        except Exception as erro:
            if espera is None:
                raise
            logger.warning(
                "Evento %s: falha ao gravar a auditoria (%s); nova tentativa em %.0f s.", evento.id, type(erro).__name__, espera
            )
            await _esperar(espera)


async def consumir_auditoria(mensagem: aio_pika.abc.AbstractIncomingMessage) -> None:
    """Grava o evento na tabela de auditoria. Idempotente: reentregas não duplicam o registro.

    Mensagem inválida, ou falha que persiste depois de todas as tentativas, vai para a fila de
    mortos (nunca trava a fila); de lá, ``reprocessar_mortos`` devolve o evento à trilha.
    """
    try:
        evento = Evento.model_validate_json(mensagem.body)
    except Exception:
        logger.error("Evento %s inválido; enviado para '%s'.", mensagem.message_id, FILA_MORTOS)
        await mensagem.reject(requeue=False)
        return
    try:
        await _gravar_com_novas_tentativas(evento)
    except Exception as erro:
        logger.error(
            "Evento %s: falha ao gravar a auditoria (%s) depois de %d tentativas; enviado para '%s'.",
            mensagem.message_id,
            type(erro).__name__,
            len(ESPERAS_NOVA_TENTATIVA_SEGUNDOS) + 1,
            FILA_MORTOS,
        )
        await mensagem.reject(requeue=False)
        return
    await mensagem.ack()


# ---------- reprocessamento da fila de mortos ----------
async def reprocessar_mortos(canal: aio_pika.abc.AbstractChannel, limite: int = 500) -> dict[str, int]:
    """Devolve à trilha de auditoria os eventos que caíram em "unisos.eventos.mortos".

    Todo evento da fila de mortos também foi roteado para a fila de auditoria (o binding dela é
    "#"), então regravá-lo é seguro: a gravação é idempotente pelo id. Processa no máximo as
    mensagens que já estavam lá (nunca entra em laço). Uma mensagem que falha de novo volta para
    o FIM da fila, com um contador no cabeçalho, e a rodada para (as próximas falhariam igual).
    JSON inválido não tem como virar registro: é descartado com log.
    """
    from app.services.auditoria_service import gravar_evento  # import tardio: core não depende de services ao carregar

    fila = await canal.declare_queue(FILA_MORTOS, durable=True)
    total = min(fila.declaration_result.message_count or 0, limite)
    resumo = {"regravados": 0, "descartados": 0, "devolvidos": 0}
    for _ in range(total):
        mensagem = await fila.get(no_ack=False, fail=False)
        if mensagem is None:
            break
        try:
            evento = Evento.model_validate_json(mensagem.body)
        except Exception:
            logger.error("Fila de mortos: evento %s inválido descartado.", mensagem.message_id)
            await mensagem.ack()
            resumo["descartados"] += 1
            continue
        try:
            await asyncio.to_thread(gravar_evento, evento, "broker")
        except Exception as erro:
            cabecalhos = dict(mensagem.headers or {})
            cabecalhos[CABECALHO_REPROCESSAMENTOS] = int(cabecalhos.get(CABECALHO_REPROCESSAMENTOS) or 0) + 1
            await canal.default_exchange.publish(
                Message(
                    body=mensagem.body,
                    headers=cabecalhos,
                    content_type="application/json",
                    delivery_mode=DeliveryMode.PERSISTENT,
                    message_id=mensagem.message_id,
                    type=mensagem.type,
                ),
                routing_key=FILA_MORTOS,
            )
            await mensagem.ack()
            resumo["devolvidos"] += 1
            logger.warning("Fila de mortos: evento %s ainda não gravado (%s); rodada interrompida.", evento.id, type(erro).__name__)
            break
        await mensagem.ack()
        resumo["regravados"] += 1
    if any(resumo.values()):
        logger.info("Fila de mortos reprocessada: %s", resumo)
    return resumo


async def _reprocessar_periodicamente(canal: aio_pika.abc.AbstractChannel) -> None:
    await asyncio.sleep(ATRASO_PRIMEIRO_REPROCESSAMENTO_SEGUNDOS)
    while True:
        try:
            await reprocessar_mortos(canal)
        except Exception:
            logger.warning("Não foi possível reprocessar '%s' agora.", FILA_MORTOS, exc_info=True)
        await asyncio.sleep(INTERVALO_REPROCESSAMENTO_SEGUNDOS)


class Indicadores:
    """Contadores DESTE PROCESSO alimentados pela fila "unisos.metricas".

    A fila é compartilhada (consumidores concorrentes): com N workers/instâncias, cada processo
    recebe só uma parte dos eventos, e os contadores zeram a cada deploy. Não são o total do
    sistema; o total confiável está na tabela ``auditoria`` (GET /auditoria?tipo=ocorrencia.criada).
    """

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
        "Indicadores do processo %d (parciais: só o que este worker recebeu desde a subida): "
        "%s (%d) | ocorrências criadas por tipo: %s",
        os.getpid(),
        evento.tipo,
        indicadores.por_evento[evento.tipo],
        dict(indicadores.por_tipo_de_ocorrencia),
    )
    await mensagem.ack()
