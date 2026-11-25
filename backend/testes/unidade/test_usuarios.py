from fastapi.testclient import TestClient
import pytest

from testes.conftest import token_de


def _cabecalho(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_admin_nao_cria_contas(client: TestClient, token_admin: str, emails) -> None:
    """As contas nascem pelo autocadastro (POST /auth/cadastro); o admin não tem mais rota de criação."""
    dados = {"nome": "Nova Pessoa", "email": "nova@unifor.br", "perfil": "admin", "senha": "minha-senha"}
    assert client.post("/usuarios", headers=_cabecalho(token_admin), json=dados).status_code == 405
    lote = client.post("/usuarios/lote", headers=_cabecalho(token_admin), json={"criacoes": [dados]})
    assert lote.status_code == 422
    assert emails == []
    lista = client.get("/usuarios", headers=_cabecalho(token_admin)).json()
    assert not any(usuario["email"] == "nova@unifor.br" for usuario in lista)


def test_admin_so_altera_nome_e_perfil(client: TestClient, token_admin: str, criar_usuario) -> None:
    pessoa = criar_usuario("pessoa@unifor.br", senha="senha123", nome="Nome Antigo")

    # E-mail e senha são do titular: o admin não os altera (422, nada é aplicado).
    for campos in ({"email": "outro@unifor.br"}, {"senha": "nova-senha-1"}, {"nome": "Outro", "email": "y@unifor.br"}):
        recusado = client.put(f"/usuarios/{pessoa.id}", headers=_cabecalho(token_admin), json=campos)
        assert recusado.status_code == 422, recusado.text
    lote = client.post(
        "/usuarios/lote",
        headers=_cabecalho(token_admin),
        json={"atualizacoes": [{"id": str(pessoa.id), "senha": "nova-senha-1"}]},
    )
    assert lote.status_code == 422

    aceito = client.put(
        f"/usuarios/{pessoa.id}", headers=_cabecalho(token_admin), json={"nome": "  Nome   Corrigido ", "perfil": "tecnico"}
    )
    assert aceito.status_code == 200, aceito.text
    assert aceito.json()["nome"] == "Nome Corrigido"
    assert aceito.json()["perfil"] == "tecnico"
    assert aceito.json()["email"] == "pessoa@unifor.br"
    # A senha continua a mesma.
    assert token_de(client, "pessoa@unifor.br", "senha123")


def test_lote_com_erro_eh_atomico(client: TestClient, token_admin: str, criar_usuario) -> None:
    from uuid import uuid4

    pessoa = criar_usuario("pessoa@unifor.br", nome="Nome Original")
    resposta = client.post(
        "/usuarios/lote",
        headers=_cabecalho(token_admin),
        json={"atualizacoes": [{"id": str(pessoa.id), "nome": "Nome Alterado"}], "exclusoes": [str(uuid4())]},
    )
    assert resposta.status_code == 404, resposta.text
    lista = client.get("/usuarios", params={"busca": "pessoa@unifor.br"}, headers=_cabecalho(token_admin)).json()
    assert [u["nome"] for u in lista] == ["Nome Original"]


def test_admin_desativa_conta_e_ela_nao_entra_mais(client: TestClient, token_admin: str, criar_usuario) -> None:
    pessoa = criar_usuario("pessoa@unifor.br", senha="senha123")
    assert client.delete(f"/usuarios/{pessoa.id}", headers=_cabecalho(token_admin)).status_code == 204
    assert client.post("/auth/login", json={"email": "pessoa@unifor.br", "senha": "senha123"}).status_code == 401


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


def test_admin_lista_desativadas_e_reativa_conta(client: TestClient, token_admin: str, criar_usuario) -> None:
    pessoa = criar_usuario("pessoa@unifor.br", senha="senha123", nome="Pessoa Desativada", perfil="tecnico")
    criar_usuario("ativa@unifor.br", nome="Pessoa Ativa")
    assert client.delete(f"/usuarios/{pessoa.id}", headers=_cabecalho(token_admin)).status_code == 204

    ativos = client.get("/usuarios", headers=_cabecalho(token_admin)).json()
    assert all(u["ativo"] for u in ativos) and "pessoa@unifor.br" not in [u["email"] for u in ativos]
    desativadas = client.get("/usuarios", params={"situacao": "desativados"}, headers=_cabecalho(token_admin))
    assert desativadas.status_code == 200, desativadas.text
    assert [(u["email"], u["ativo"]) for u in desativadas.json()] == [("pessoa@unifor.br", False)]
    resumo = client.get("/usuarios/resumo", params={"situacao": "desativados"}, headers=_cabecalho(token_admin))
    assert resumo.json() == {"total": 1}
    assert client.get("/usuarios", params={"situacao": "todos"}, headers=_cabecalho(token_admin)).status_code == 422

    reativada = client.post(f"/usuarios/{pessoa.id}/reativar", headers=_cabecalho(token_admin))
    assert reativada.status_code == 200, reativada.text
    # Volta como era: mesmo perfil, e-mail e senha.
    assert reativada.json()["ativo"] is True and reativada.json()["perfil"] == "tecnico"
    assert token_de(client, "pessoa@unifor.br", "senha123")
    assert client.get("/usuarios", params={"situacao": "desativados"}, headers=_cabecalho(token_admin)).json() == []

    # Reativar de novo, ou uma conta que não existe, não faz nada.
    assert client.post(f"/usuarios/{pessoa.id}/reativar", headers=_cabecalho(token_admin)).status_code == 400
    from uuid import uuid4

    assert client.post(f"/usuarios/{uuid4()}/reativar", headers=_cabecalho(token_admin)).status_code == 404


def test_reativar_exige_admin_e_fica_na_auditoria(client: TestClient, token_admin: str, criar_usuario) -> None:
    from sqlalchemy import select

    from app.core.database import FabricaSessao
    from app.entities.registro_auditoria import RegistroAuditoria

    pessoa = criar_usuario("pessoa@unifor.br", ativo=False)
    criar_usuario("comum@unifor.br", senha="senha123")
    token_comum = token_de(client, "comum@unifor.br", "senha123")
    assert client.post(f"/usuarios/{pessoa.id}/reativar", headers=_cabecalho(token_comum)).status_code == 403
    assert client.get("/usuarios", params={"situacao": "desativados"}, headers=_cabecalho(token_comum)).status_code == 403
    assert client.post(f"/usuarios/{pessoa.id}/reativar").status_code == 401

    assert client.post(f"/usuarios/{pessoa.id}/reativar", headers=_cabecalho(token_admin)).status_code == 200
    with FabricaSessao() as sessao:
        registros = list(
            sessao.scalars(select(RegistroAuditoria).where(RegistroAuditoria.tipo == "auditoria.usuario.reativar"))
        )
    sucesso = [r for r in registros if r.resultado == "sucesso"]
    assert len(sucesso) == 1 and sucesso[0].entidade_id == str(pessoa.id)


def test_conta_anonimizada_nao_aparece_nem_volta(client: TestClient, token_admin: str, criar_usuario) -> None:
    pessoa = criar_usuario("titular@unifor.br")
    assert client.post(f"/usuarios/{pessoa.id}/anonimizar", headers=_cabecalho(token_admin)).status_code == 200

    desativadas = client.get("/usuarios", params={"situacao": "desativados"}, headers=_cabecalho(token_admin)).json()
    assert str(pessoa.id) not in [u["id"] for u in desativadas]
    recusada = client.post(f"/usuarios/{pessoa.id}/reativar", headers=_cabecalho(token_admin))
    assert recusada.status_code == 400
    assert "anonimizada" in recusada.json()["detail"]
