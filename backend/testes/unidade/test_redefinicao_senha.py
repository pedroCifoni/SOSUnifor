import re
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import FabricaSessao
from app.entities.token_redefinicao_senha import TokenRedefinicaoSenha


def _token_do_email(texto: str) -> str:
    achado = re.search(r"token=([A-Za-z0-9_-]+)", texto)
    assert achado, texto
    return achado.group(1)


def test_redefinicao_nao_revela_email_e_invalida_token_apos_uso(client: TestClient, emails) -> None:
    existente = client.post("/auth/esqueci-senha", json={"email": "admin@unifor.br"})
    inexistente = client.post("/auth/esqueci-senha", json={"email": "nao-existe@edu.unifor.br"})
    assert existente.status_code == inexistente.status_code == 200
    assert existente.json() == inexistente.json()
    assert len(emails) == 1

    token = _token_do_email(emails[0]["texto"] or "")
    assert client.post("/auth/redefinir-senha", json={"token": token, "nova_senha": "nova-senha1"}).status_code == 200
    assert "foi alterada" in (emails[-1]["assunto"] or "").lower()
    assert client.post("/auth/redefinir-senha", json={"token": token, "nova_senha": "outra-senha"}).status_code == 400
    assert client.post("/auth/login", json={"email": "admin@unifor.br", "senha": "123456"}).status_code == 401
    assert client.post("/auth/login", json={"email": "admin@unifor.br", "senha": "nova-senha1"}).status_code == 200


def test_token_expirado_e_limite_de_tres_pedidos(client: TestClient, emails) -> None:
    client.post("/auth/esqueci-senha", json={"email": "admin@unifor.br"})
    token = _token_do_email(emails[0]["texto"] or "")
    with FabricaSessao() as sessao:
        registro = sessao.scalar(select(TokenRedefinicaoSenha))
        assert registro is not None
        registro.expira_em = datetime.now(timezone.utc) - timedelta(seconds=1)
        sessao.commit()
    assert client.post("/auth/redefinir-senha", json={"token": token, "nova_senha": "nova-senha1"}).status_code == 400

    # O pedido já expirado conta para a janela; mais dois ainda são permitidos e o quarto é silenciado.
    for _ in range(3):
        assert client.post("/auth/esqueci-senha", json={"email": "admin@unifor.br"}).status_code == 200
    assert len(emails) == 3
