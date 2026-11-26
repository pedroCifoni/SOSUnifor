"""Cache em memória com prazo de validade (TTL), por processo.

Usado para dados lidos a todo instante e que quase nunca mudam (ex.: polígonos do campus, lidos em
cada SOS para descobrir o prédio). A instância que altera o dado invalida o próprio cache na hora;
as outras réplicas enxergam a mudança quando o prazo vence. Por isso o TTL é curto.
"""

import threading
import time
from collections.abc import Callable
from typing import Any, TypeVar


T = TypeVar("T")


class CacheTTL:
    def __init__(self, relogio: Callable[[], float] = time.monotonic) -> None:
        self._valores: dict[str, tuple[float, Any]] = {}
        self._trava = threading.Lock()
        self._relogio = relogio
        self.acertos = 0
        self.faltas = 0

    def obter_ou_calcular(self, chave: str, ttl_segundos: float, calcular: Callable[[], T]) -> T:
        agora = self._relogio()
        with self._trava:
            item = self._valores.get(chave)
            if item is not None and item[0] > agora:
                self.acertos += 1
                return item[1]
        # Calcula fora da trava: uma consulta lenta não bloqueia as outras chaves.
        valor = calcular()
        with self._trava:
            self.faltas += 1
            self._valores[chave] = (agora + ttl_segundos, valor)
        return valor

    def invalidar(self, prefixo: str = "") -> None:
        with self._trava:
            for chave in [c for c in self._valores if c.startswith(prefixo)]:
                del self._valores[chave]


cache = CacheTTL()
