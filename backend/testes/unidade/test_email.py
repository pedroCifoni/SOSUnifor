"""Escolha do canal de envio e formato da chamada à API da Brevo (sem rede real)."""

import json

import pytest

from app.core import email as modulo_email
from app.core.config import configuracoes


class _RespostaFalsa:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self) -> bytes:
        return b'{"messageId": "<teste>"}'


def test_com_chave_da_brevo_envia_pela_api_https(monkeypatch: pytest.MonkeyPatch) -> None:
    chamadas = []

    def urlopen_falso(requisicao, timeout):
        chamadas.append(requisicao)
        return _RespostaFalsa()

    monkeypatch.setattr(configuracoes, "brevo_api_key", "chave-de-teste")
    monkeypatch.setattr(configuracoes, "smtp_host", "smtp.que.nao.deve.ser.usado")
    monkeypatch.setattr(configuracoes, "smtp_remetente", "Uni SOS <unisos@exemplo.com>")
    monkeypatch.setattr(modulo_email.urllib.request, "urlopen", urlopen_falso)
    monkeypatch.setattr(modulo_email, "_enviar_por_smtp", lambda *a: pytest.fail("não deveria usar SMTP"))

    modulo_email.enviar_email("pessoa@exemplo.com", "Assunto", "texto", "<p>html</p>")

    assert len(chamadas) == 1
    requisicao = chamadas[0]
    assert requisicao.full_url == "https://api.brevo.com/v3/smtp/email"
    assert requisicao.get_header("Api-key") == "chave-de-teste"
    corpo = json.loads(requisicao.data)
    assert corpo["sender"] == {"name": "Uni SOS", "email": "unisos@exemplo.com"}
    assert corpo["to"] == [{"email": "pessoa@exemplo.com"}]
    assert corpo["subject"] == "Assunto"
    assert corpo["htmlContent"] == "<p>html</p>"


def test_falha_da_brevo_nao_derruba_quem_chamou(monkeypatch: pytest.MonkeyPatch) -> None:
    def urlopen_com_erro(requisicao, timeout):
        raise modulo_email.urllib.error.HTTPError(requisicao.full_url, 401, "Unauthorized", None, None)

    monkeypatch.setattr(configuracoes, "brevo_api_key", "chave-invalida")
    monkeypatch.setattr(modulo_email.urllib.request, "urlopen", urlopen_com_erro)

    modulo_email.enviar_email("pessoa@exemplo.com", "Assunto", "texto")  # não pode lançar exceção
