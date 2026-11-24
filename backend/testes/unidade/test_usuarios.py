from fastapi.testclient import TestClient
import pytest

from testes.conftest import token_de


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


def test_busca_por_nome_email_sem_acento_e_maiusculas(
    client: TestClient, token_admin: str, criar_usuario
) -> None:
    criar_usuario("joao.conceicao@unifor.br", nome="João Conceição", perfil="usuario")
    criar_usuario("maria.santos@unifor.br", nome="Maria Santos", perfil="seguranca")
    criar_usuario("inativo@unifor.br", nome="João Inativo", perfil="usuario", ativo=False)

    # Parte do nome sem acento e com maiúsculas variadas
    por_nome = client.get("/usuarios", params={"busca": "JOAO CONCEICAO"}, headers=_cabecalho(token_admin))
    assert por_nome.status_code == 200, por_nome.text
    emails_nome = [u["email"] for u in por_nome.json()]
    assert emails_nome == ["joao.conceicao@unifor.br"]

    # Busca com acento também encontra nome sem acento ou e-mail
    com_acento = client.get("/usuarios", params={"busca": "conceição"}, headers=_cabecalho(token_admin))
    assert com_acento.status_code == 200
    assert [u["email"] for u in com_acento.json()] == ["joao.conceicao@unifor.br"]

    # Busca por parte do e-mail (maiúsculas)
    por_email = client.get("/usuarios", params={"busca": "MARIA.SANTOS"}, headers=_cabecalho(token_admin))
    assert por_email.status_code == 200
    assert [u["email"] for u in por_email.json()] == ["maria.santos@unifor.br"]

    # Resumo devolve o mesmo total (ignorando inativos)
    resumo = client.get("/usuarios/resumo", params={"busca": "joao"}, headers=_cabecalho(token_admin))
    assert resumo.status_code == 200, resumo.text
    assert resumo.json() == {"total": 1}


def test_filtro_por_perfil_e_combinado_com_busca(
    client: TestClient, token_admin: str, criar_usuario
) -> None:
    criar_usuario("ana.seg@unifor.br", nome="Ana Segurança", perfil="seguranca")
    criar_usuario("ana.tec@unifor.br", nome="Ana Técnica", perfil="tecnico")

    resposta = client.get(
        "/usuarios",
        params={"perfil": "seguranca"},
        headers=_cabecalho(token_admin),
    )
    assert resposta.status_code == 200
    dados = resposta.json()
    assert len(dados) >= 2
    assert all(u["perfil"] == "seguranca" for u in dados)

    combinado = client.get(
        "/usuarios",
        params={"busca": "ana", "perfil": "tecnico"},
        headers=_cabecalho(token_admin),
    )
    assert combinado.status_code == 200
    assert [u["email"] for u in combinado.json()] == ["ana.tec@unifor.br"]

    resumo = client.get(
        "/usuarios/resumo",
        params={"busca": "ana", "perfil": "tecnico"},
        headers=_cabecalho(token_admin),
    )
    assert resumo.status_code == 200
    assert resumo.json() == {"total": 1}


@pytest.mark.parametrize("curinga", ["%", "_", "\\"])
def test_curingas_like_sao_tratados_como_texto_literal(
    client: TestClient, token_admin: str, criar_usuario, curinga: str
) -> None:
    criar_usuario("comum@unifor.br", nome="Pessoa Comum", perfil="usuario")
    criar_usuario(f"literal.{curinga.replace('\\', 'barra')}@unifor.br", nome=f"Nome com {curinga} literal", perfil="usuario")

    resposta = client.get("/usuarios", params={"busca": curinga}, headers=_cabecalho(token_admin))
    assert resposta.status_code == 200, resposta.text
    nomes = [u["nome"] for u in resposta.json()]
    assert nomes == [f"Nome com {curinga} literal"]


@pytest.mark.parametrize("email_nao_admin", ["eduardo.costa@unifor.br", "seguranca@unifor.br", "tecnico@unifor.br"])
def test_busca_e_resumo_de_usuarios_exigem_admin(client: TestClient, email_nao_admin: str) -> None:
    token = token_de(client, email_nao_admin)

    lista = client.get("/usuarios", params={"busca": "admin"}, headers=_cabecalho(token))
    assert lista.status_code == 403

    resumo = client.get("/usuarios/resumo", params={"busca": "admin"}, headers=_cabecalho(token))
    assert resumo.status_code == 403


def test_limite_e_paginacao_respeitados_e_ordenados_por_nome(
    client: TestClient, token_admin: str, criar_usuario
) -> None:
    for indice in range(1, 8):
        criar_usuario(f"teste.{indice:02d}@unifor.br", nome=f"Aluno Teste {indice:02d}", perfil="usuario")

    pagina_1 = client.get(
        "/usuarios",
        params={"busca": "Aluno Teste", "limite": 3, "pagina": 1},
        headers=_cabecalho(token_admin),
    )
    pagina_2 = client.get(
        "/usuarios",
        params={"busca": "Aluno Teste", "limite": 3, "pagina": 2},
        headers=_cabecalho(token_admin),
    )
    pagina_3 = client.get(
        "/usuarios",
        params={"busca": "Aluno Teste", "limite": 3, "pagina": 3},
        headers=_cabecalho(token_admin),
    )

    assert pagina_1.status_code == 200
    assert pagina_2.status_code == 200
    assert pagina_3.status_code == 200

    nomes_1 = [u["nome"] for u in pagina_1.json()]
    nomes_2 = [u["nome"] for u in pagina_2.json()]
    nomes_3 = [u["nome"] for u in pagina_3.json()]

    assert nomes_1 == ["Aluno Teste 01", "Aluno Teste 02", "Aluno Teste 03"]
    assert nomes_2 == ["Aluno Teste 04", "Aluno Teste 05", "Aluno Teste 06"]
    assert nomes_3 == ["Aluno Teste 07"]

    # Limite acima de 200 é ajustado sem erro
    limite_alto = client.get("/usuarios", params={"limite": 500}, headers=_cabecalho(token_admin))
    assert limite_alto.status_code == 200
    assert len(limite_alto.json()) <= 200
