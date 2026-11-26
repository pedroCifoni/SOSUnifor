"""Padrão Observer dos eventos de domínio (sem broker e sem banco)."""

import pytest

from app.core import eventos
from app.core.eventos import Evento


@pytest.mark.parametrize(
    ("padrao", "tipo", "casa"),
    [
        ("usuario.ativado", "usuario.ativado", True),
        ("usuario.*", "usuario.criado", True),
        ("usuario.*", "usuario.criado.extra", False),
        ("#", "ocorrencia.status_alterado", True),
        ("ocorrencia.#", "ocorrencia", True),
        ("ocorrencia.*", "usuario.criado", False),
    ],
)
def test_padrao_casa_como_exchange_topic(padrao: str, tipo: str, casa: bool) -> None:
    assert eventos.padrao_casa(padrao, tipo) is casa


def test_notificar_localmente_entrega_aos_assinantes_e_isola_falhas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(eventos, "_assinantes", [])
    recebidos: list[str] = []

    @eventos.assinar("teste.*")
    def com_erro(evento: Evento) -> None:
        raise RuntimeError("falha de um observador")

    @eventos.assinar("teste.feito")
    def observador(evento: Evento) -> None:
        recebidos.append(evento.tipo)

    eventos.notificar_localmente(Evento(tipo="teste.feito"))
    eventos.notificar_localmente(Evento(tipo="outro.evento"))

    assert recebidos == ["teste.feito"]
