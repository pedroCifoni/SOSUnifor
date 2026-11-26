"""Teste de ponta a ponta dos eventos com um RabbitMQ de verdade e a API com 2 workers.

Não roda no pytest (precisa do broker e de uma API no ar). Como usar (PowerShell, pasta backend):

    docker compose up -d rabbitmq
    $env:DATABASE_URL='postgresql+psycopg://unisos:uni12345@localhost:5433/unisos_testes_aspectos'
    $env:RABBITMQ_URL='amqp://unisos:uni12345@localhost:5672/'; $env:SMTP_HOST=''; $env:BREVO_API_KEY=''
    python -m uvicorn app.main:app --port 8030 --workers 2
    # No Windows, "--workers" do uvicorn 0.54 falha ao abrir o socket (WinError 10022). Suba então
    # dois processos, um em --port 8030 e outro em --port 8031: para o broker é o mesmo cenário
    # (dois consumidores na mesma fila durável).
    # em outro terminal (rode uma vez com API_URL de cada processo):
    python testes/testar_eventos_rabbitmq.py

Confere que:
  1. a fila "unisos.auditoria" tem um consumidor por processo da API (2);
  2. um evento publicado pela API chega UMA vez na auditoria, gravado pelo consumidor (origem "broker");
  3. o mesmo evento publicado duas vezes (reentrega) continua com um registro só (idempotência);
  4. o token do WebSocket não aparece no log de acesso (confira no terminal da API: token=***).
"""

import asyncio
import base64
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from uuid import uuid4


API = os.environ.get("API_URL", "http://127.0.0.1:8030")
RABBITMQ_URL = os.environ.get("RABBITMQ_URL", "amqp://unisos:uni12345@localhost:5672/")
PAINEL = os.environ.get("RABBITMQ_PAINEL", "http://localhost:15672")
CREDENCIAIS_PAINEL = os.environ.get("RABBITMQ_PAINEL_USUARIO", "unisos:uni12345")


def requisitar(metodo: str, caminho: str, token: str | None = None, corpo: dict | None = None):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    pedido = urllib.request.Request(f"{API}{caminho}", data=dados, method=metodo)
    pedido.add_header("Content-Type", "application/json")
    if token:
        pedido.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(pedido, timeout=10) as resposta:
        return json.loads(resposta.read() or b"null")


def entrar(email: str, senha: str = "123456") -> str:
    return requisitar("POST", "/auth/login", corpo={"email": email, "senha": senha})["token"]


def auditoria(token: str, **filtros: str) -> list[dict]:
    return requisitar("GET", f"/auditoria?{urllib.parse.urlencode({'limite': 100, **filtros})}", token)


def esperar_registros(token: str, tipo: str, entidade_id: str, segundos: float = 10) -> list[dict]:
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        achados = [r for r in auditoria(token, tipo=tipo) if r["entidadeId"] == entidade_id]
        if achados:
            time.sleep(2)  # dá tempo de uma eventual duplicata chegar
            return [r for r in auditoria(token, tipo=tipo) if r["entidadeId"] == entidade_id]
        time.sleep(0.3)
    return []


def consumidores_da_fila(fila: str) -> int:
    pedido = urllib.request.Request(f"{PAINEL}/api/queues/%2F/{fila}")
    pedido.add_header("Authorization", "Basic " + base64.b64encode(CREDENCIAIS_PAINEL.encode()).decode())
    with urllib.request.urlopen(pedido, timeout=5) as resposta:
        return json.loads(resposta.read())["consumers"]


async def publicar_duas_vezes(evento: dict) -> None:
    import aio_pika

    conexao = await aio_pika.connect_robust(RABBITMQ_URL)
    async with conexao:
        canal = await conexao.channel(publisher_confirms=True)
        exchange = await canal.get_exchange("unisos.eventos")
        for _ in range(2):
            await exchange.publish(
                aio_pika.Message(json.dumps(evento).encode(), message_id=evento["id"], content_type="application/json"),
                routing_key=evento["tipo"],
            )


async def abrir_websocket(token: str) -> None:
    import websockets

    url = API.replace("http", "ws", 1) + f"/ws/notificacoes?token={token}"
    async with websockets.connect(url):
        await asyncio.sleep(0.2)


def verificar(condicao: bool, mensagem: str) -> None:
    print(("OK   " if condicao else "FALHA ") + mensagem)
    if not condicao:
        sys.exit(1)


def main() -> None:
    admin = entrar("admin@unifor.br")
    usuario = entrar("eduardo.costa@unifor.br")

    consumidores = consumidores_da_fila("unisos.auditoria")
    verificar(consumidores >= 2, f"fila unisos.auditoria com {consumidores} consumidores (um por processo da API)")
    verificar(consumidores_da_fila("unisos.metricas") >= 2, "fila unisos.metricas consumida pelos processos da API")

    ocorrencia = requisitar(
        "POST", "/ocorrencias", usuario, {"titulo": "Teste de eventos", "local": "Bloco Z", "tipo": "manutencao"}
    )
    criada = esperar_registros(admin, "ocorrencia.criada", ocorrencia["id"])
    verificar(len(criada) == 1, f"evento ocorrencia.criada chegou {len(criada)} vez(es) na auditoria")
    verificar(criada[0]["origem"] == "broker", "gravado pelo consumidor da fila (origem=broker)")
    acao = esperar_registros(admin, "auditoria.ocorrencia.criar", ocorrencia["id"])
    verificar(len(acao) == 1, f"auditoria.ocorrencia.criar chegou {len(acao)} vez(es)")

    entidade_id = f"teste-{uuid4().hex[:8]}"
    evento = {
        "id": str(uuid4()),
        "tipo": "ocorrencia.teste_reentrega",
        "versao": 1,
        "ocorrido_em": "2026-01-01T12:00:00+00:00",
        "ator_id": None,
        "dados": {"entidade": "ocorrencia", "entidade_id": entidade_id, "resultado": "sucesso"},
    }
    asyncio.run(publicar_duas_vezes(evento))
    duplicado = esperar_registros(admin, "ocorrencia.teste_reentrega", entidade_id)
    verificar(len(duplicado) == 1, f"mesmo evento publicado 2x gerou {len(duplicado)} registro (idempotente)")

    asyncio.run(abrir_websocket(usuario))
    print("Confira no log da API: a linha do WebSocket deve mostrar /ws/notificacoes?token=***")


if __name__ == "__main__":
    main()
