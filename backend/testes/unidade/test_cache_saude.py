"""Cache TTL e readiness."""

from app.core.cache import CacheTTL


def test_cache_reaproveita_ate_vencer_e_invalida_por_prefixo() -> None:
    agora = [0.0]
    cache = CacheTTL(relogio=lambda: agora[0])
    chamadas: list[int] = []

    def calcular() -> int:
        chamadas.append(1)
        return len(chamadas)

    assert cache.obter_ou_calcular("areas:x", 60, calcular) == 1
    assert cache.obter_ou_calcular("areas:x", 60, calcular) == 1  # acerto
    agora[0] = 61
    assert cache.obter_ou_calcular("areas:x", 60, calcular) == 2  # venceu
    cache.invalidar("areas:")
    assert cache.obter_ou_calcular("areas:x", 60, calcular) == 3
    assert (cache.acertos, cache.faltas) == (1, 3)


def test_readiness_confere_o_banco_e_informa_o_broker(client) -> None:
    resposta = client.get("/health/ready")
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["status"] == "ready"
    assert corpo["dependencias"]["postgres"]["status"] == "ok"
    # Nos testes o RabbitMQ está fora de propósito: a API segue no modo fallback.
    assert corpo["dependencias"]["rabbitmq"]["status"] == "fallback_local"
    assert client.get("/health").json() == {"service": "uni-sos-api", "status": "healthy"}
