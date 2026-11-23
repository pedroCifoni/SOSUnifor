from fastapi.testclient import TestClient

from app.services.privacidade_service import VERSAO_POLITICA_PRIVACIDADE
from testes.conftest import token_de


def test_ciencia_da_politica_de_privacidade(client: TestClient, criar_usuario) -> None:
    assert client.get("/privacidade/situacao").status_code == 401

    criar_usuario("aluno@unifor.br")
    cabecalho = {"Authorization": f"Bearer {token_de(client, 'aluno@unifor.br', 'senha123')}"}

    situacao = client.get("/privacidade/situacao", headers=cabecalho).json()
    assert situacao == {
        "versaoVigente": VERSAO_POLITICA_PRIVACIDADE,
        "versaoCiente": None,
        "cienteEm": None,
        "pendente": True,
    }

    desatualizada = client.post("/privacidade/ciencia", json={"versao": "2000-01-01"}, headers=cabecalho)
    assert desatualizada.status_code == 409
    assert client.get("/privacidade/situacao", headers=cabecalho).json()["pendente"] is True

    registrada = client.post("/privacidade/ciencia", json={"versao": VERSAO_POLITICA_PRIVACIDADE}, headers=cabecalho)
    assert registrada.status_code == 200
    assert registrada.json()["pendente"] is False
    assert registrada.json()["versaoCiente"] == VERSAO_POLITICA_PRIVACIDADE
    assert registrada.json()["cienteEm"]

    # Repetir não altera a data da primeira ciência.
    de_novo = client.post("/privacidade/ciencia", json={"versao": VERSAO_POLITICA_PRIVACIDADE}, headers=cabecalho)
    assert de_novo.json()["cienteEm"] == registrada.json()["cienteEm"]


def test_nova_versao_da_politica_exige_nova_ciencia(client: TestClient, criar_usuario, monkeypatch) -> None:
    criar_usuario("aluna@unifor.br")
    cabecalho = {"Authorization": f"Bearer {token_de(client, 'aluna@unifor.br', 'senha123')}"}
    client.post("/privacidade/ciencia", json={"versao": VERSAO_POLITICA_PRIVACIDADE}, headers=cabecalho)

    monkeypatch.setattr("app.services.privacidade_service.VERSAO_POLITICA_PRIVACIDADE", "2099-01-01")
    situacao = client.get("/privacidade/situacao", headers=cabecalho).json()
    assert situacao["pendente"] is True
    assert situacao["versaoVigente"] == "2099-01-01"
    assert situacao["versaoCiente"] == VERSAO_POLITICA_PRIVACIDADE
