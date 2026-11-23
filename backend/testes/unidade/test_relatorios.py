from testes.conftest import token_de


def _cabecalho(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _criar(client, token: str, *, tipo: str, titulo: str = "Ocorrência de teste", anonima: bool = False) -> None:
    resposta = client.post(
        "/ocorrencias",
        headers=_cabecalho(token),
        json={"titulo": titulo, "local": "Bloco A", "tipo": tipo, "anonima": anonima},
    )
    assert resposta.status_code == 201, resposta.text


def test_admin_exporta_csv_filtrado_com_bom_e_protecao(client, criar_usuario) -> None:
    criar_usuario("autor.relatorio@unifor.br", nome="Solicitante")
    token_autor = token_de(client, "autor.relatorio@unifor.br", "senha123")
    _criar(client, token_autor, tipo="manutencao", titulo='=SOMA(1;1)')
    _criar(client, token_autor, tipo="sos", titulo="Não deve entrar")

    resposta = client.get("/relatorios/ocorrencias.csv?tipo=manutencao", headers=_cabecalho(token_de(client, "admin@unifor.br")))

    assert resposta.status_code == 200, resposta.text
    assert resposta.headers["content-type"].startswith("text/csv")
    assert resposta.content.startswith(b"\xef\xbb\xbf")
    texto = resposta.content.decode("utf-8-sig")
    assert texto.splitlines()[0] == "Protocolo;Data/hora;Tipo;Status;Título;Local;Solicitante;Responsável"
    assert "Manutenção" in texto
    assert "Não deve entrar" not in texto
    assert "'=SOMA(1;1)" in texto
    assert "ocorrencias_inicio_a_atual.csv" in resposta.headers["content-disposition"]


def test_admin_exporta_pdf_e_preserva_anonimato(client, criar_usuario) -> None:
    criar_usuario("anonima.relatorio@unifor.br", nome="Nome que não pode vazar")
    token_autor = token_de(client, "anonima.relatorio@unifor.br", "senha123")
    _criar(client, token_autor, tipo="denuncia", anonima=True)

    resposta_csv = client.get("/relatorios/ocorrencias.csv?tipo=denuncia", headers=_cabecalho(token_de(client, "admin@unifor.br")))
    resposta_pdf = client.get("/relatorios/ocorrencias.pdf?tipo=denuncia", headers=_cabecalho(token_de(client, "admin@unifor.br")))

    assert resposta_csv.status_code == 200
    assert "Anônimo" in resposta_csv.content.decode("utf-8-sig")
    assert "Nome que não pode vazar" not in resposta_csv.content.decode("utf-8-sig")
    assert resposta_pdf.status_code == 200
    assert resposta_pdf.headers["content-type"].startswith("application/pdf")
    assert resposta_pdf.content.startswith(b"%PDF")


def test_exportacao_exige_admin_e_rejeita_filtros_invalidos(client, criar_usuario) -> None:
    criar_usuario("comum.relatorio@unifor.br")
    comum = token_de(client, "comum.relatorio@unifor.br", "senha123")
    admin = token_de(client, "admin@unifor.br")

    assert client.get("/relatorios/ocorrencias.csv", headers=_cabecalho(comum)).status_code == 403
    assert client.get("/relatorios/ocorrencias.csv?tipo=invalido", headers=_cabecalho(admin)).status_code == 422
    assert client.get("/relatorios/ocorrencias.pdf?de=2026-05-02&ate=2026-05-01", headers=_cabecalho(admin)).status_code == 400
    assert client.get("/relatorios/ocorrencias.csv?de=data-invalida", headers=_cabecalho(admin)).status_code == 422
