from fastapi.testclient import TestClient

from testes.conftest import token_de


def _cabecalho(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _criar(client: TestClient, token: str, *, tipo: str, anonima: bool = False) -> dict:
    resposta = client.post(
        "/ocorrencias",
        headers=_cabecalho(token),
        json={"titulo": "Pedido", "descricao": "Detalhes", "local": "Bloco A", "tipo": tipo, "anonima": anonima},
    )
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def test_visibilidade_cancelamento_e_denuncia_anonima(client: TestClient, criar_usuario) -> None:
    criar_usuario("autor@edu.unifor.br", nome="Autor")
    criar_usuario("outro@edu.unifor.br", nome="Outro")
    autor = token_de(client, "autor@edu.unifor.br", "senha123")
    outro = token_de(client, "outro@edu.unifor.br", "senha123")
    admin = token_de(client, "admin@unifor.br")

    sos = _criar(client, autor, tipo="sos")
    assert client.get(f"/ocorrencias/{sos['id']}", headers=_cabecalho(outro)).status_code == 403
    assert client.patch(
        f"/ocorrencias/{sos['id']}/status", headers=_cabecalho(outro), json={"status": "cancelado"}
    ).status_code == 403
    cancelada = client.patch(
        f"/ocorrencias/{sos['id']}/status", headers=_cabecalho(autor), json={"status": "cancelado"}
    )
    assert cancelada.status_code == 200
    assert cancelada.json()["status"] == "cancelado"

    denuncia = _criar(client, autor, tipo="denuncia", anonima=True)
    detalhe_admin = client.get(f"/ocorrencias/{denuncia['id']}", headers=_cabecalho(admin))
    assert detalhe_admin.status_code == 200
    assert detalhe_admin.json()["solicitante"] == "Anônimo"


def test_anexo_de_outra_ocorrencia_nao_pode_ser_reaproveitado(client: TestClient, criar_usuario) -> None:
    """Quem sabe o nome de um arquivo alheio não pode citá-lo na própria ocorrência para baixá-lo."""
    from app.core.config import PASTA_ARQUIVOS

    criar_usuario("vitima@edu.unifor.br", nome="Vítima")
    criar_usuario("atacante@edu.unifor.br", nome="Atacante")
    vitima = token_de(client, "vitima@edu.unifor.br", "senha123")
    atacante = token_de(client, "atacante@edu.unifor.br", "senha123")

    envio = client.post(
        "/arquivos",
        headers=_cabecalho(vitima),
        files={"arquivo": ("foto.png", b"\x89PNG\r\n\x1a\n", "image/png")},
    )
    assert envio.status_code in (200, 201), envio.text
    anexo = envio.json()
    nome_armazenado = anexo["url"].rsplit("/", 1)[-1]
    try:
        corpo = {"titulo": "Pedido", "local": "Bloco A", "tipo": "manutencao"}
        assert client.post(
            "/ocorrencias", headers=_cabecalho(vitima), json={**corpo, "anexos": [anexo]}
        ).status_code == 201

        forjado = {**anexo, "url": f"https://atacante.example/arquivos/{nome_armazenado}"}
        resposta = client.post("/ocorrencias", headers=_cabecalho(atacante), json={**corpo, "anexos": [forjado]})
        assert resposta.status_code == 400, resposta.text
        assert client.get(f"/arquivos/{nome_armazenado}", headers=_cabecalho(atacante)).status_code == 404
        assert client.get(f"/arquivos/{nome_armazenado}", headers=_cabecalho(vitima)).status_code == 200

        invalido = {"nome": "x.png", "url": "https://qualquer/arquivos/nao-e-uuid.png", "tipo": "image/png"}
        assert client.post(
            "/ocorrencias", headers=_cabecalho(atacante), json={**corpo, "anexos": [invalido]}
        ).status_code == 400
    finally:
        (PASTA_ARQUIVOS / nome_armazenado).unlink(missing_ok=True)
