"""Refresh token com rotação, logout, limite de tentativas de login e cabeçalhos de segurança."""

from app.core.config import configuracoes


def _login(client, email: str = "sessao@unifor.br", senha: str = "senha123"):
    return client.post("/auth/login", json={"email": email, "senha": senha})


def test_login_devolve_refresh_token_e_renovacao_faz_rotacao(client, criar_usuario) -> None:
    criar_usuario("sessao@unifor.br")
    login = _login(client)
    assert login.status_code == 200, login.text
    corpo = login.json()
    assert corpo["token"] and corpo["refreshToken"]

    renovado = client.post("/auth/renovar", json={"refresh_token": corpo["refreshToken"]})
    assert renovado.status_code == 200, renovado.text
    novo = renovado.json()
    assert novo["refreshToken"] != corpo["refreshToken"]
    assert client.get("/me", headers={"Authorization": f"Bearer {novo['token']}"}).status_code == 200

    # Reusar o token antigo (roubado) encerra todas as sessões, inclusive a renovada.
    assert client.post("/auth/renovar", json={"refresh_token": corpo["refreshToken"]}).status_code == 401
    assert client.post("/auth/renovar", json={"refresh_token": novo["refreshToken"]}).status_code == 401


def test_logout_revoga_o_refresh_token(client, criar_usuario) -> None:
    criar_usuario("sessao@unifor.br")
    refresh = _login(client).json()["refreshToken"]

    assert client.post("/auth/logout", json={"refresh_token": refresh}).status_code == 204
    assert client.post("/auth/logout", json={"refresh_token": refresh}).status_code == 204  # idempotente
    assert client.post("/auth/renovar", json={"refresh_token": refresh}).status_code == 401
    assert client.post("/auth/renovar", json={"refresh_token": "x" * 43}).status_code == 401


def test_trocar_a_senha_encerra_as_outras_sessoes(client, criar_usuario) -> None:
    criar_usuario("sessao@unifor.br")
    outra_sessao = _login(client).json()["refreshToken"]
    token = _login(client).json()["token"]

    resposta = client.put(
        "/me/senha",
        headers={"Authorization": f"Bearer {token}"},
        json={"senha_atual": "senha123", "nova_senha": "outra-senha-1"},
    )
    assert resposta.status_code == 200, resposta.text
    assert client.post("/auth/renovar", json={"refresh_token": outra_sessao}).status_code == 401


def test_muitas_falhas_bloqueiam_o_login_por_um_tempo(client, criar_usuario) -> None:
    criar_usuario("sessao@unifor.br")
    for _ in range(configuracoes.login_max_falhas_por_email):
        assert _login(client, senha="errada-123").status_code == 401

    # Até a senha certa é recusada enquanto durar a janela: o atacante não descobre quando acertou.
    bloqueado = _login(client)
    assert bloqueado.status_code == 429
    assert "Muitas tentativas" in bloqueado.json()["detail"]
    # Outra conta não é afetada (o limite por IP é maior).
    criar_usuario("outra.sessao@unifor.br")
    assert _login(client, "outra.sessao@unifor.br").status_code == 200


def test_sucesso_zera_as_falhas_do_email(client, criar_usuario) -> None:
    criar_usuario("sessao@unifor.br")
    for _ in range(configuracoes.login_max_falhas_por_email - 1):
        _login(client, senha="errada-123")
    assert _login(client).status_code == 200
    for _ in range(configuracoes.login_max_falhas_por_email - 1):
        _login(client, senha="errada-123")
    assert _login(client).status_code == 200


def test_cabecalhos_de_seguranca(client) -> None:
    resposta = client.get("/health")
    assert resposta.headers["x-content-type-options"] == "nosniff"
    assert resposta.headers["x-frame-options"] == "DENY"
    assert "default-src 'none'" in resposta.headers["content-security-policy"]
    # A documentação interativa precisa carregar scripts: sem a CSP restritiva.
    assert "content-security-policy" not in client.get("/docs").headers
