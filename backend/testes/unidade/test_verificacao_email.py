import re
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from app.core.database import FabricaSessao, engine
from app.core.inicializacao_banco import adicionar_verificacao_de_email
from app.entities.token_verificacao_email import TokenVerificacaoEmail
from app.entities.usuario import Usuario


def _cabecalho(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _token_do_email(mensagem: dict) -> str:
    achado = re.search(r"verificar-email\?token=([A-Za-z0-9_-]+)", mensagem["texto"] or "")
    assert achado, mensagem["texto"]
    return achado.group(1)


def _login(client: TestClient, email: str, senha: str):
    return client.post("/auth/login", json={"email": email, "senha": senha})


def _criar_pelo_admin(client: TestClient, token_admin: str, email: str = "nova@unifor.br", senha: str = "senha-nova1"):
    resposta = client.post(
        "/usuarios",
        headers=_cabecalho(token_admin),
        json={"nome": "Nova Pessoa", "email": email, "perfil": "usuario", "senha": senha},
    )
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def test_fluxo_completo_conta_criada_pelo_admin(client: TestClient, token_admin: str, emails) -> None:
    criada = _criar_pelo_admin(client, token_admin)
    assert criada["emailVerificado"] is False
    assert len(emails) == 1
    boas_vindas = emails[0]
    assert "senha-nova1" in (boas_vindas["texto"] or "")
    assert "Confirmar e-mail" in (boas_vindas["html"] or "")
    token = _token_do_email(boas_vindas)

    # Antes de confirmar: 403 com código próprio; o resto do formato de erro não muda.
    recusado = _login(client, "nova@unifor.br", "senha-nova1")
    assert recusado.status_code == 403
    assert recusado.json()["codigo"] == "email_nao_verificado"
    assert "não foi confirmado" in recusado.json()["detail"]

    # Só o hash fica no banco.
    with FabricaSessao() as sessao:
        hashes = list(sessao.scalars(select(TokenVerificacaoEmail.token_hash)))
    assert hashes and token not in hashes

    confirmado = client.post("/auth/verificar-email", json={"token": token})
    assert confirmado.status_code == 200, confirmado.text
    assert _login(client, "nova@unifor.br", "senha-nova1").status_code == 200

    lista = client.get("/usuarios", headers=_cabecalho(token_admin)).json()
    assert next(u for u in lista if u["email"] == "nova@unifor.br")["emailVerificado"] is True

    # Uso único.
    assert client.post("/auth/verificar-email", json={"token": token}).status_code == 400


def test_login_403_so_com_senha_correta(client: TestClient, criar_usuario) -> None:
    criar_usuario("pendente@unifor.br", senha="senha123", email_verificado=False)
    errada = _login(client, "pendente@unifor.br", "senha-errada")
    inexistente = _login(client, "ninguem@unifor.br", "senha-errada")
    assert errada.status_code == inexistente.status_code == 401
    assert errada.json() == inexistente.json() == {"detail": "E-mail ou senha inválidos."}

    certa = _login(client, "pendente@unifor.br", "senha123")
    assert certa.status_code == 403
    assert certa.json()["codigo"] == "email_nao_verificado"


def test_token_expirado_invalido_e_pedido_novo_invalida_anterior(client: TestClient, token_admin: str, emails) -> None:
    _criar_pelo_admin(client, token_admin)
    primeiro = _token_do_email(emails[0])

    assert client.post("/auth/reenviar-verificacao", json={"email": "nova@unifor.br"}).status_code == 200
    segundo = _token_do_email(emails[-1])
    assert "Confirme o seu e-mail" in (emails[-1]["assunto"] or "")
    # O link antigo deixou de valer quando o novo foi pedido.
    assert client.post("/auth/verificar-email", json={"token": primeiro}).status_code == 400

    with FabricaSessao() as sessao:
        for registro in sessao.scalars(select(TokenVerificacaoEmail).where(TokenVerificacaoEmail.usado_em.is_(None))):
            registro.expira_em = datetime.now(timezone.utc) - timedelta(seconds=1)
        sessao.commit()
    assert client.post("/auth/verificar-email", json={"token": segundo}).status_code == 400
    assert client.post("/auth/verificar-email", json={"token": "x" * 43}).status_code == 400
    assert _login(client, "nova@unifor.br", "senha-nova1").status_code == 403


def test_reenvio_nao_revela_contas_e_respeita_limite(client: TestClient, criar_usuario, emails) -> None:
    criar_usuario("pendente@unifor.br", email_verificado=False)
    criar_usuario("confirmada@unifor.br")

    respostas = [
        client.post("/auth/reenviar-verificacao", json={"email": email})
        for email in ("pendente@unifor.br", "confirmada@unifor.br", "nao-existe@unifor.br")
    ]
    assert {r.status_code for r in respostas} == {200}
    assert len({r.text for r in respostas}) == 1
    assert [m["destinatario"] for m in emails] == ["pendente@unifor.br"]

    # Mais dois são permitidos na mesma hora; o quarto recebe a mesma resposta, mas nada é enviado.
    for _ in range(3):
        resposta = client.post("/auth/reenviar-verificacao", json={"email": "pendente@unifor.br"})
        assert resposta.text == respostas[0].text
    assert len(emails) == 3


def test_troca_de_email_pelo_admin_exige_nova_confirmacao(client: TestClient, token_admin: str, criar_usuario, emails) -> None:
    pessoa = criar_usuario("antigo@unifor.br", senha="senha123")
    assert _login(client, "antigo@unifor.br", "senha123").status_code == 200

    # Pedido de senha aberto para o endereço antigo: não pode servir para "comprovar" o novo.
    client.post("/auth/esqueci-senha", json={"email": "antigo@unifor.br"})
    link_senha_antigo = re.search(r"token=([A-Za-z0-9_-]+)", emails[-1]["texto"] or "").group(1)

    resposta = client.put(f"/usuarios/{pessoa.id}", headers=_cabecalho(token_admin), json={"email": "novo@unifor.br"})
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["emailVerificado"] is False
    assert emails[-1]["destinatario"] == "novo@unifor.br"
    token = _token_do_email(emails[-1])

    assert client.post("/auth/redefinir-senha", json={"token": link_senha_antigo, "nova_senha": "outra-senha"}).status_code == 400
    assert _login(client, "novo@unifor.br", "senha123").status_code == 403
    assert client.post("/auth/verificar-email", json={"token": token}).status_code == 200
    assert _login(client, "novo@unifor.br", "senha123").status_code == 200

    # Salvar o mesmo e-mail (ex.: só mudou o nome) não desfaz a confirmação.
    quantos = len(emails)
    client.post(
        "/usuarios/lote",
        headers=_cabecalho(token_admin),
        json={"atualizacoes": [{"id": str(pessoa.id), "nome": "Outro Nome", "email": "novo@unifor.br"}]},
    )
    assert len(emails) == quantos
    assert _login(client, "novo@unifor.br", "senha123").status_code == 200


def test_troca_de_email_em_lote_invalida_link_do_endereco_antigo(client: TestClient, token_admin: str, emails) -> None:
    criada = _criar_pelo_admin(client, token_admin, email="primeiro@unifor.br")
    link_antigo = _token_do_email(emails[-1])
    resposta = client.post(
        "/usuarios/lote",
        headers=_cabecalho(token_admin),
        json={"atualizacoes": [{"id": criada["id"], "email": "segundo@unifor.br"}]},
    )
    assert resposta.status_code == 200, resposta.text
    assert emails[-1]["destinatario"] == "segundo@unifor.br"
    assert client.post("/auth/verificar-email", json={"token": link_antigo}).status_code == 400
    assert client.post("/auth/verificar-email", json={"token": _token_do_email(emails[-1])}).status_code == 200


def test_lote_cria_contas_nao_verificadas_com_link(client: TestClient, token_admin: str, emails) -> None:
    resposta = client.post(
        "/usuarios/lote",
        headers=_cabecalho(token_admin),
        json={"criacoes": [{"nome": "Lote", "email": "lote@unifor.br", "perfil": "tecnico", "senha": "senha123"}]},
    )
    assert resposta.status_code == 200, resposta.text
    assert len(emails) == 1
    assert _login(client, "lote@unifor.br", "senha123").status_code == 403
    assert client.post("/auth/verificar-email", json={"token": _token_do_email(emails[0])}).status_code == 200
    assert _login(client, "lote@unifor.br", "senha123").status_code == 200


def test_redefinicao_de_senha_comprova_o_email(client: TestClient, criar_usuario, emails) -> None:
    criar_usuario("pendente@unifor.br", email_verificado=False)
    client.post("/auth/esqueci-senha", json={"email": "pendente@unifor.br"})
    token = re.search(r"token=([A-Za-z0-9_-]+)", emails[-1]["texto"] or "").group(1)
    assert client.post("/auth/redefinir-senha", json={"token": token, "nova_senha": "nova-senha1"}).status_code == 200
    assert _login(client, "pendente@unifor.br", "nova-senha1").status_code == 200


def test_admin_reenvia_confirmacao(client: TestClient, token_admin: str, criar_usuario, emails) -> None:
    pendente = criar_usuario("pendente@unifor.br", email_verificado=False)
    confirmada = criar_usuario("confirmada@unifor.br")

    resposta = client.post(f"/usuarios/{pendente.id}/reenviar-verificacao", headers=_cabecalho(token_admin))
    assert resposta.status_code == 200, resposta.text
    assert emails[-1]["destinatario"] == "pendente@unifor.br"

    assert client.post(f"/usuarios/{confirmada.id}/reenviar-verificacao", headers=_cabecalho(token_admin)).status_code == 400
    for _ in range(2):
        client.post(f"/usuarios/{pendente.id}/reenviar-verificacao", headers=_cabecalho(token_admin))
    assert client.post(f"/usuarios/{pendente.id}/reenviar-verificacao", headers=_cabecalho(token_admin)).status_code == 429

    # Só admin pode.
    token_comum = client.post("/auth/login", json={"email": "confirmada@unifor.br", "senha": "senha123"}).json()["token"]
    assert client.post(f"/usuarios/{pendente.id}/reenviar-verificacao", headers=_cabecalho(token_comum)).status_code == 403


def test_contas_existentes_continuam_entrando_apos_a_migracao(client: TestClient) -> None:
    """Simula o banco de produção antes da verificação existir: a coluna nasce já marcando todos."""
    with engine.begin() as conexao:
        conexao.execute(text("ALTER TABLE credentials DROP COLUMN email_verificado_em CASCADE"))
        conexao.execute(
            text(
                "INSERT INTO credentials (id, nome, email, senha_hash, tipo_usuario, ativo) "
                "SELECT gen_random_uuid(), 'Conta Antiga', 'antiga@unifor.br', senha_hash, 'usuario', true "
                "FROM credentials WHERE email = 'admin@unifor.br'"
            )
        )
    engine.dispose()  # descarta conexões com planos preparados para a estrutura antiga
    adicionar_verificacao_de_email()
    engine.dispose()

    assert _login(client, "antiga@unifor.br", "123456").status_code == 200
    assert _login(client, "admin@unifor.br", "123456").status_code == 200

    # Rodar de novo (nova subida da API) não confirma contas criadas depois.
    with FabricaSessao() as sessao:
        sessao.add(Usuario(nome="Nova", email="depois@unifor.br", senha_hash="x", tipo_usuario="usuario"))
        sessao.commit()
    adicionar_verificacao_de_email()
    with FabricaSessao() as sessao:
        assert sessao.scalar(select(Usuario.email_verificado_em).where(Usuario.email == "depois@unifor.br")) is None


def _id_por_email(client: TestClient, token_admin: str, email: str) -> str:
    lista = client.get("/usuarios", headers=_cabecalho(token_admin)).json()
    return next(u["id"] for u in lista if u["email"] == email)


def test_admin_so_troca_o_proprio_email_se_houver_outro_admin_confirmado(
    client: TestClient, token_admin: str, criar_usuario, emails
) -> None:
    meu_id = _id_por_email(client, token_admin, "admin@unifor.br")
    # Um admin ainda não confirmado não resolve: ele também não conseguiria entrar.
    criar_usuario("outro.admin@unifor.br", perfil="admin", email_verificado=False)

    for envio in (
        lambda: client.put(f"/usuarios/{meu_id}", headers=_cabecalho(token_admin), json={"email": "admim@unifor.br"}),
        lambda: client.post(
            "/usuarios/lote",
            headers=_cabecalho(token_admin),
            json={"atualizacoes": [{"id": meu_id, "email": "admim@unifor.br"}]},
        ),
    ):
        recusado = envio()
        assert recusado.status_code == 400, recusado.text
        assert "outro administrador" in recusado.json()["detail"]
    assert emails == []
    assert _login(client, "admin@unifor.br", "123456").status_code == 200

    # Mudar só o nome continua permitido.
    assert client.put(f"/usuarios/{meu_id}", headers=_cabecalho(token_admin), json={"nome": "Admin"}).status_code == 200

    criar_usuario("reserva@unifor.br", perfil="admin")
    aceito = client.put(f"/usuarios/{meu_id}", headers=_cabecalho(token_admin), json={"email": "admin.novo@unifor.br"})
    assert aceito.status_code == 200, aceito.text
    assert aceito.json()["emailVerificado"] is False


def test_sessao_aberta_para_quando_o_email_deixa_de_estar_confirmado(
    client: TestClient, token_admin: str, criar_usuario
) -> None:
    pessoa = criar_usuario("logada@unifor.br", senha="senha123")
    token = _login(client, "logada@unifor.br", "senha123").json()["token"]
    assert client.get("/notificacoes", headers=_cabecalho(token)).status_code == 200

    client.put(f"/usuarios/{pessoa.id}", headers=_cabecalho(token_admin), json={"email": "trocado@unifor.br"})
    barrado = client.get("/notificacoes", headers=_cabecalho(token))
    assert barrado.status_code == 403
    assert barrado.json()["codigo"] == "email_nao_verificado"

    # O canal de tempo real também recusa a conta.
    from starlette.websockets import WebSocketDisconnect

    try:
        with client.websocket_connect(f"/ws/notificacoes?token={token}") as canal:
            canal.receive_text()
        raise AssertionError("O canal deveria ter sido fechado.")
    except WebSocketDisconnect as fechamento:
        assert fechamento.code == 1008


def test_status_de_confirmacao_so_aparece_para_o_admin(client: TestClient, token_admin: str, criar_usuario) -> None:
    criar_usuario("pendente.tec@unifor.br", perfil="tecnico", email_verificado=False)
    criar_usuario("aluno@unifor.br", senha="senha123")
    token_aluno = _login(client, "aluno@unifor.br", "senha123").json()["token"]

    for caminho in ("/usuarios/tecnicos", "/usuarios/segurancas"):
        lista = client.get(caminho, headers=_cabecalho(token_aluno)).json()
        assert lista and all("emailVerificado" not in u for u in lista)
    assert all("emailVerificado" in u for u in client.get("/usuarios", headers=_cabecalho(token_admin)).json())


def test_links_nao_guardam_o_endereco_e_somem_com_a_conta(client: TestClient, token_admin: str, emails) -> None:
    criada = _criar_pelo_admin(client, token_admin, email="privacidade@unifor.br")
    with engine.connect() as conexao:
        colunas = {c for c in conexao.execute(text("SELECT * FROM tokens_verificacao_email LIMIT 0")).keys()}
        linhas = conexao.execute(text("SELECT * FROM tokens_verificacao_email")).all()
    assert "email" not in colunas
    assert linhas and all("privacidade@unifor.br" not in str(valor) for linha in linhas for valor in linha)

    # Links vencidos há muito tempo são apagados no próximo envio, de qualquer conta.
    with FabricaSessao() as sessao:
        for registro in sessao.scalars(select(TokenVerificacaoEmail)):
            registro.criado_em = registro.expira_em = datetime.now(timezone.utc) - timedelta(days=30)
        sessao.commit()
    _criar_pelo_admin(client, token_admin, email="outra@unifor.br")
    with FabricaSessao() as sessao:
        assert sessao.scalar(select(func.count()).select_from(TokenVerificacaoEmail)) == 1

    # Excluir a conta apaga os links dela.
    outra_id = _id_por_email(client, token_admin, "outra@unifor.br")
    assert client.delete(f"/usuarios/{outra_id}", headers=_cabecalho(token_admin)).status_code == 204
    with FabricaSessao() as sessao:
        assert sessao.scalar(select(func.count()).select_from(TokenVerificacaoEmail)) == 0
    assert criada["id"] != outra_id


def test_reenvios_simultaneos_respeitam_o_limite(client: TestClient, criar_usuario, emails) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from app.dtos.auth_dto import ReenviarVerificacaoEntrada
    from app.services.verificacao_email_service import LIMITE_ENVIOS_VERIFICACAO, VerificacaoEmailService

    criar_usuario("alvo@unifor.br", email_verificado=False)
    quantos = 8
    largada = Barrier(quantos)

    def pedir() -> None:
        with FabricaSessao() as sessao:
            largada.wait()
            VerificacaoEmailService(sessao).reenviar(ReenviarVerificacaoEntrada(email="alvo@unifor.br"))

    with ThreadPoolExecutor(max_workers=quantos) as executor:
        for futuro in [executor.submit(pedir) for _ in range(quantos)]:
            futuro.result()
    assert len(emails) == LIMITE_ENVIOS_VERIFICACAO


def test_migracao_tira_o_email_em_claro_dos_links(client: TestClient, token_admin: str, emails) -> None:
    """Bancos que rodaram a primeira versão da tabela (coluna `email`) passam a `email_hash`."""
    from app.core.inicializacao_banco import remover_email_em_claro_dos_links_de_confirmacao

    _criar_pelo_admin(client, token_admin)
    with engine.begin() as conexao:
        conexao.execute(text("ALTER TABLE tokens_verificacao_email DROP COLUMN email_hash"))
        conexao.execute(text("ALTER TABLE tokens_verificacao_email ADD COLUMN email VARCHAR(150) NOT NULL DEFAULT 'x@unifor.br'"))
    engine.dispose()
    remover_email_em_claro_dos_links_de_confirmacao()
    remover_email_em_claro_dos_links_de_confirmacao()  # idempotente
    engine.dispose()

    with engine.connect() as conexao:
        colunas = set(conexao.execute(text("SELECT * FROM tokens_verificacao_email LIMIT 0")).keys())
    assert "email" not in colunas and "email_hash" in colunas
    # O link antigo foi descartado; um novo pedido funciona normalmente.
    assert client.post("/auth/verificar-email", json={"token": _token_do_email(emails[0])}).status_code == 400
    client.post("/auth/reenviar-verificacao", json={"email": "nova@unifor.br"})
    assert client.post("/auth/verificar-email", json={"token": _token_do_email(emails[-1])}).status_code == 200
