from fastapi.testclient import TestClient
import pytest


def _cabecalho(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_admin_cria_usuario_e_email_contem_senha(client: TestClient, token_admin: str, emails) -> None:
    resposta = client.post(
        "/usuarios",
        headers=_cabecalho(token_admin),
        json={"nome": "Nova Pessoa", "email": "nova@unifor.br", "perfil": "usuario", "senha": "minha-senha"},
    )
    assert resposta.status_code == 201, resposta.text
    assert len(emails) == 1
    assert "minha-senha" in (emails[0]["texto"] or "")


def test_lote_com_erro_eh_atomico_e_nao_envia_email(client: TestClient, token_admin: str, emails) -> None:
    dados = {
        "criacoes": [
            {"nome": "Uma Pessoa", "email": "repetido@unifor.br", "perfil": "usuario", "senha": "senha123"},
            {"nome": "Outra Pessoa", "email": "repetido@unifor.br", "perfil": "usuario", "senha": "senha456"},
        ]
    }
    resposta = client.post("/usuarios/lote", headers=_cabecalho(token_admin), json=dados)
    assert resposta.status_code == 409, resposta.text
    assert emails == []
    lista = client.get("/usuarios", headers=_cabecalho(token_admin)).json()
    assert not any(usuario["email"] == "repetido@unifor.br" for usuario in lista)
