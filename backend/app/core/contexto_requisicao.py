"""Contexto da requisição HTTP em andamento (request id e usuário autenticado).

O middleware do aspecto HTTP cria o contexto no começo da requisição. A dependência de
autenticação anota quem é o usuário. Os aspectos dos services leem daqui o "quem" e o
"request id" sem que o código de negócio precise repassá-los.

Por que um objeto mutável dentro de uma ContextVar: as rotas e dependências síncronas
rodam em threads do threadpool, que recebem uma CÓPIA do contexto. Uma nova atribuição
na ContextVar feita numa thread não volta para as outras; já a alteração de um atributo
do mesmo objeto é vista por todas.
"""

from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID


@dataclass
class ContextoRequisicao:
    request_id: str | None = None
    ator_id: UUID | None = None


_contexto: ContextVar[ContextoRequisicao | None] = ContextVar("contexto_requisicao", default=None)


def iniciar(request_id: str) -> object:
    """Abre o contexto de uma requisição. Devolve o token para ``encerrar``."""
    return _contexto.set(ContextoRequisicao(request_id=request_id))


def encerrar(token: object) -> None:
    _contexto.reset(token)  # type: ignore[arg-type]


def atual() -> ContextoRequisicao:
    """O contexto da requisição corrente (vazio fora de uma requisição, ex.: testes de service)."""
    return _contexto.get() or ContextoRequisicao()


def definir_ator(usuario_id: UUID) -> None:
    contexto = _contexto.get()
    if contexto is not None:
        contexto.ator_id = usuario_id
