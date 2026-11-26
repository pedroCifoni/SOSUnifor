"""Perfil do próprio usuário (/me) e exportação da lista de contas pelo administrador."""

from testes.conftest import token_de


PNG_MINIMO = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def _cabecalho(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_consulta_e_corrige_o_proprio_nome(client, criar_usuario) -> None:
    criar_usuario("perfil@edu.unifor.br", nome="Nome Antigo")
    token = token_de(client, "perfil@edu.unifor.br", "senha123")

    perfil = client.get("/me", headers=_cabecalho(token))
    assert perfil.status_code == 200
    assert perfil.json()["email"] == "perfil@edu.unifor.br" and perfil.json()["temAvatar"] is False

    alterado = client.put("/me", headers=_cabecalho(token), json={"nome": "  Nome   Novo  "})
    assert alterado.status_code == 200, alterado.text
    assert alterado.json()["nome"] == "Nome Novo"
    # E-mail e perfil não mudam por aqui.
    assert client.put("/me", headers=_cabecalho(token), json={"nome": "Outro", "perfil": "admin"}).status_code == 422
    assert client.get("/me").status_code == 401


def test_troca_de_senha_exige_a_atual_e_avisa_por_email(client, criar_usuario, emails) -> None:
    criar_usuario("troca@edu.unifor.br")
    token = token_de(client, "troca@edu.unifor.br", "senha123")

    errada = client.put("/me/senha", headers=_cabecalho(token), json={"senhaAtual": "x", "novaSenha": "nova-senha-1"})
    assert client.put(
        "/me/senha", headers=_cabecalho(token), json={"senha_atual": "errada", "nova_senha": "nova-senha-1"}
    ).status_code == 400
    assert errada.status_code == 422  # campos em camelCase não fazem parte da entrada
    assert client.put(
        "/me/senha", headers=_cabecalho(token), json={"senha_atual": "senha123", "nova_senha": "curta"}
    ).status_code == 422

    ok = client.put("/me/senha", headers=_cabecalho(token), json={"senha_atual": "senha123", "nova_senha": "nova-senha-1"})
    assert ok.status_code == 200, ok.text
    assert client.post("/auth/login", json={"email": "troca@edu.unifor.br", "senha": "senha123"}).status_code == 401
    assert client.post("/auth/login", json={"email": "troca@edu.unifor.br", "senha": "nova-senha-1"}).status_code == 200
    assert emails[-1]["assunto"] == "Sua senha foi alterada · Uni SOS"


def test_foto_de_perfil_valida_conteudo_e_tamanho(client, criar_usuario) -> None:
    criar_usuario("foto@edu.unifor.br")
    token = token_de(client, "foto@edu.unifor.br", "senha123")

    assert client.get("/me/avatar", headers=_cabecalho(token)).status_code == 404
    # O tipo declarado não basta: o conteúdo precisa ser mesmo uma imagem.
    falsa = client.put("/me/avatar", headers=_cabecalho(token), files={"arquivo": ("x.png", b"<script>", "image/png")})
    assert falsa.status_code == 415
    grande = client.put(
        "/me/avatar", headers=_cabecalho(token), files={"arquivo": ("x.png", PNG_MINIMO + b"0" * 1024 * 1024, "image/png")}
    )
    assert grande.status_code == 413

    enviada = client.put("/me/avatar", headers=_cabecalho(token), files={"arquivo": ("eu.png", PNG_MINIMO, "image/png")})
    assert enviada.status_code == 200, enviada.text
    assert enviada.json()["temAvatar"] is True
    baixada = client.get("/me/avatar", headers=_cabecalho(token))
    assert baixada.status_code == 200 and baixada.content == PNG_MINIMO and baixada.headers["content-type"] == "image/png"

    assert client.delete("/me/avatar", headers=_cabecalho(token)).json()["temAvatar"] is False


def test_admin_exporta_contas_em_csv_e_pdf_com_filtros(client, criar_usuario, token_admin) -> None:
    criar_usuario("tecnica.export@edu.unifor.br", nome="Técnica Exportada", perfil="tecnico")
    criar_usuario("formula.export@edu.unifor.br", nome="=CMD()", perfil="usuario")

    csv = client.get("/usuarios/exportar.csv?perfil=tecnico", headers=_cabecalho(token_admin))
    assert csv.status_code == 200, csv.text
    assert csv.headers["content-type"].startswith("text/csv")
    texto = csv.content.decode("utf-8-sig")
    assert texto.splitlines()[0] == "Nome;E-mail;Perfil;E-mail confirmado;Situação;Último acesso"
    assert "Técnica Exportada" in texto and "=CMD()" not in texto

    todos = client.get("/usuarios/exportar.csv", headers=_cabecalho(token_admin)).content.decode("utf-8-sig")
    assert "'=CMD()" in todos

    pdf = client.get("/usuarios/exportar.pdf?busca=export", headers=_cabecalho(token_admin))
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")

    assert client.get("/usuarios/exportar.xlsx", headers=_cabecalho(token_admin)).status_code == 422
    comum = token_de(client, "tecnica.export@edu.unifor.br", "senha123")
    assert client.get("/usuarios/exportar.csv", headers=_cabecalho(comum)).status_code == 403
