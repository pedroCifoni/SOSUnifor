from fastapi.testclient import TestClient

from testes.conftest import token_de


def test_login_e_protecao_de_rotas(client: TestClient, criar_usuario) -> None:
    resposta = client.post("/auth/login", json={"email": "admin@unifor.br", "senha": "123456"})
    assert resposta.status_code == 200
    assert resposta.json()["token"]

    assert client.post("/auth/login", json={"email": "admin@unifor.br", "senha": "errada1"}).status_code == 401
    criar_usuario("desativado@edu.unifor.br", ativo=False)
    assert client.post("/auth/login", json={"email": "desativado@edu.unifor.br", "senha": "senha123"}).status_code == 401

    assert client.get("/usuarios").status_code == 401
    criar_usuario("comum@edu.unifor.br")
    token_comum = token_de(client, "comum@edu.unifor.br", "senha123")
    assert client.get("/usuarios", headers={"Authorization": f"Bearer {token_comum}"}).status_code == 403
