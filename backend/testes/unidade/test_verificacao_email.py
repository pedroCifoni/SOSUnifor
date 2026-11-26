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


def _cadastrar(client: TestClient, email: str = "nova@edu.unifor.br", senha: str = "senha-nova1") -> None:
    from app.core.privacidade import VERSAO_TERMOS

    resposta = client.post(
        "/auth/cadastro",
        json={"nome": "Nova Pessoa", "email": email, "senha": senha, "versao_termos": VERSAO_TERMOS},
    )
    assert resposta.status_code == 202, resposta.text


def _confirmar(client: TestClient, token: str, senha: str = "senha-nova1"):
    return client.post("/auth/verificar-email", json={"token": token, "senha": senha})


def test_fluxo_completo_conta_autocadastrada(client: TestClient, token_admin: str, emails) -> None:
    _cadastrar(client)
    assert len(emails) == 1
    confirmacao = emails[0]
    assert confirmacao["destinatario"] == "nova@edu.unifor.br"
    # A senha nunca vai por e-mail.
    assert "senha-nova1" not in (confirmacao["texto"] or "") + (confirmacao["html"] or "")
    assert "Confirmar e-mail" in (confirmacao["html"] or "")
    token = _token_do_email(confirmacao)

    # Antes de confirmar: 403 com código próprio; o resto do formato de erro não muda.
    recusado = _login(client, "nova@edu.unifor.br", "senha-nova1")
    assert recusado.status_code == 403
    assert recusado.json()["codigo"] == "email_nao_verificado"
    assert "não foi confirmado" in recusado.json()["detail"]

    # Só o hash fica no banco.
    with FabricaSessao() as sessao:
        hashes = list(sessao.scalars(select(TokenVerificacaoEmail.token_hash)))
    assert hashes and token not in hashes

    # O link sozinho não confirma: é preciso a senha da conta. Senha errada não gasta o link.
    assert client.post("/auth/verificar-email", json={"token": token}).status_code == 422
    errada = _confirmar(client, token, "senha-de-outra-pessoa")
    assert errada.status_code == 400
    assert errada.json()["codigo"] == "senha_nao_confere"

    confirmado = _confirmar(client, token)
    assert confirmado.status_code == 200, confirmado.text
    assert _login(client, "nova@edu.unifor.br", "senha-nova1").status_code == 200

    lista = client.get("/usuarios", headers=_cabecalho(token_admin)).json()
    criada = next(u for u in lista if u["email"] == "nova@edu.unifor.br")
    assert criada["emailVerificado"] is True
    assert criada["perfil"] == "usuario"

    # Uso único.
    assert _confirmar(client, token).status_code == 400


def test_login_403_so_com_senha_correta(client: TestClient, criar_usuario) -> None:
    criar_usuario("pendente@edu.unifor.br", senha="senha123", email_verificado=False)
    errada = _login(client, "pendente@edu.unifor.br", "senha-errada")
    inexistente = _login(client, "ninguem@edu.unifor.br", "senha-errada")
    assert errada.status_code == inexistente.status_code == 401
    assert errada.json() == inexistente.json() == {"detail": "E-mail ou senha inválidos."}

    certa = _login(client, "pendente@edu.unifor.br", "senha123")
    assert certa.status_code == 403
    assert certa.json()["codigo"] == "email_nao_verificado"


def test_token_expirado_invalido_e_pedido_novo_invalida_anterior(client: TestClient, emails) -> None:
    _cadastrar(client)
    primeiro = _token_do_email(emails[0])

    assert client.post("/auth/reenviar-verificacao", json={"email": "nova@edu.unifor.br"}).status_code == 200
    segundo = _token_do_email(emails[-1])
    assert "Confirme o seu e-mail" in (emails[-1]["assunto"] or "")
    # O link antigo deixou de valer quando o novo foi pedido.
    assert _confirmar(client, primeiro).status_code == 400

    with FabricaSessao() as sessao:
        for registro in sessao.scalars(select(TokenVerificacaoEmail).where(TokenVerificacaoEmail.usado_em.is_(None))):
            registro.expira_em = datetime.now(timezone.utc) - timedelta(seconds=1)
        sessao.commit()
    assert _confirmar(client, segundo).status_code == 400
    assert _confirmar(client, "x" * 43).status_code == 400
    assert _login(client, "nova@edu.unifor.br", "senha-nova1").status_code == 403


def test_reenvio_nao_revela_contas_e_respeita_limite(client: TestClient, criar_usuario, emails) -> None:
    criar_usuario("pendente@edu.unifor.br", email_verificado=False)
    criar_usuario("confirmada@edu.unifor.br")

    respostas = [
        client.post("/auth/reenviar-verificacao", json={"email": email})
        for email in ("pendente@edu.unifor.br", "confirmada@edu.unifor.br", "nao-existe@edu.unifor.br")
    ]
    assert {r.status_code for r in respostas} == {200}
    assert len({r.text for r in respostas}) == 1
    assert [m["destinatario"] for m in emails] == ["pendente@edu.unifor.br"]

    # Mais dois são permitidos na mesma hora; o quarto recebe a mesma resposta, mas nada é enviado.
    for _ in range(3):
        resposta = client.post("/auth/reenviar-verificacao", json={"email": "pendente@edu.unifor.br"})
        assert resposta.text == respostas[0].text
    assert len(emails) == 3


def test_redefinicao_de_senha_comprova_o_email(client: TestClient, criar_usuario, emails) -> None:
    criar_usuario("pendente@edu.unifor.br", email_verificado=False)
    client.post("/auth/esqueci-senha", json={"email": "pendente@edu.unifor.br"})
    token = re.search(r"token=([A-Za-z0-9_-]+)", emails[-1]["texto"] or "").group(1)
    assert client.post("/auth/redefinir-senha", json={"token": token, "nova_senha": "nova-senha1"}).status_code == 200
    assert _login(client, "pendente@edu.unifor.br", "nova-senha1").status_code == 200


def test_admin_reenvia_confirmacao(client: TestClient, token_admin: str, criar_usuario, emails) -> None:
    pendente = criar_usuario("pendente@edu.unifor.br", email_verificado=False)
    confirmada = criar_usuario("confirmada@edu.unifor.br")

    resposta = client.post(f"/usuarios/{pendente.id}/reenviar-verificacao", headers=_cabecalho(token_admin))
    assert resposta.status_code == 200, resposta.text
    assert emails[-1]["destinatario"] == "pendente@edu.unifor.br"

    assert client.post(f"/usuarios/{confirmada.id}/reenviar-verificacao", headers=_cabecalho(token_admin)).status_code == 400
    for _ in range(2):
        client.post(f"/usuarios/{pendente.id}/reenviar-verificacao", headers=_cabecalho(token_admin))
    assert client.post(f"/usuarios/{pendente.id}/reenviar-verificacao", headers=_cabecalho(token_admin)).status_code == 429

    # Só admin pode.
    token_comum = client.post("/auth/login", json={"email": "confirmada@edu.unifor.br", "senha": "senha123"}).json()["token"]
    assert client.post(f"/usuarios/{pendente.id}/reenviar-verificacao", headers=_cabecalho(token_comum)).status_code == 403


def test_contas_existentes_continuam_entrando_apos_a_migracao(client: TestClient) -> None:
    """Simula o banco de produção antes da verificação existir: a coluna nasce já marcando todos."""
    with engine.begin() as conexao:
        conexao.execute(text("ALTER TABLE credentials DROP COLUMN email_verificado_em CASCADE"))
        conexao.execute(
            text(
                "INSERT INTO credentials (id, nome, email, senha_hash, tipo_usuario, ativo) "
                "SELECT gen_random_uuid(), 'Conta Antiga', 'antiga@edu.unifor.br', senha_hash, 'usuario', true "
                "FROM credentials WHERE email = 'admin@unifor.br'"
            )
        )
    engine.dispose()  # descarta conexões com planos preparados para a estrutura antiga
    adicionar_verificacao_de_email()
    engine.dispose()

    assert _login(client, "antiga@edu.unifor.br", "123456").status_code == 200
    assert _login(client, "admin@unifor.br", "123456").status_code == 200

    # Rodar de novo (nova subida da API) não confirma contas criadas depois.
    with FabricaSessao() as sessao:
        sessao.add(Usuario(nome="Nova", email="depois@edu.unifor.br", senha_hash="x", tipo_usuario="usuario"))
        sessao.commit()
    adicionar_verificacao_de_email()
    with FabricaSessao() as sessao:
        assert sessao.scalar(select(Usuario.email_verificado_em).where(Usuario.email == "depois@edu.unifor.br")) is None


def _id_por_email(client: TestClient, token_admin: str, email: str) -> str:
    lista = client.get("/usuarios", headers=_cabecalho(token_admin)).json()
    return next(u["id"] for u in lista if u["email"] == email)


def test_sessao_aberta_para_quando_o_email_deixa_de_estar_confirmado(client: TestClient, criar_usuario) -> None:
    pessoa = criar_usuario("logada@edu.unifor.br", senha="senha123")
    token = _login(client, "logada@edu.unifor.br", "senha123").json()["token"]
    assert client.get("/notificacoes", headers=_cabecalho(token)).status_code == 200

    with FabricaSessao() as sessao:
        sessao.get(Usuario, pessoa.id).email_verificado_em = None
        sessao.commit()
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
    criar_usuario("pendente.tec@edu.unifor.br", perfil="tecnico", email_verificado=False)
    criar_usuario("aluno@edu.unifor.br", senha="senha123")
    token_aluno = _login(client, "aluno@edu.unifor.br", "senha123").json()["token"]

    for caminho in ("/usuarios/tecnicos", "/usuarios/segurancas"):
        lista = client.get(caminho, headers=_cabecalho(token_aluno)).json()
        assert lista and all("emailVerificado" not in u for u in lista)
    assert all("emailVerificado" in u for u in client.get("/usuarios", headers=_cabecalho(token_admin)).json())


def test_links_nao_guardam_o_endereco_e_somem_com_a_conta(client: TestClient, token_admin: str, emails) -> None:
    _cadastrar(client, email="privacidade@edu.unifor.br")
    with engine.connect() as conexao:
        colunas = set(conexao.execute(text("SELECT * FROM tokens_verificacao_email LIMIT 0")).keys())
        linhas = conexao.execute(text("SELECT * FROM tokens_verificacao_email")).all()
    assert "email" not in colunas
    assert linhas and all("privacidade@edu.unifor.br" not in str(valor) for linha in linhas for valor in linha)

    # Links vencidos há muito tempo são apagados no próximo envio, de qualquer conta.
    with FabricaSessao() as sessao:
        for registro in sessao.scalars(select(TokenVerificacaoEmail)):
            registro.criado_em = registro.expira_em = datetime.now(timezone.utc) - timedelta(days=30)
        sessao.commit()
    _cadastrar(client, email="outra@edu.unifor.br")
    with FabricaSessao() as sessao:
        assert sessao.scalar(select(func.count()).select_from(TokenVerificacaoEmail)) == 1

    # Excluir a conta apaga os links dela.
    outra_id = _id_por_email(client, token_admin, "outra@edu.unifor.br")
    assert client.delete(f"/usuarios/{outra_id}", headers=_cabecalho(token_admin)).status_code == 204
    with FabricaSessao() as sessao:
        assert sessao.scalar(select(func.count()).select_from(TokenVerificacaoEmail)) == 0
    assert _id_por_email(client, token_admin, "privacidade@edu.unifor.br") != outra_id


def test_reenvios_simultaneos_respeitam_o_limite(client: TestClient, criar_usuario, emails) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from app.dtos.auth_dto import ReenviarVerificacaoEntrada
    from app.services.verificacao_email_service import LIMITE_ENVIOS_VERIFICACAO, VerificacaoEmailService

    criar_usuario("alvo@edu.unifor.br", email_verificado=False)
    quantos = 8
    largada = Barrier(quantos)

    def pedir() -> None:
        with FabricaSessao() as sessao:
            largada.wait()
            VerificacaoEmailService(sessao).reenviar(ReenviarVerificacaoEntrada(email="alvo@edu.unifor.br"))

    with ThreadPoolExecutor(max_workers=quantos) as executor:
        for futuro in [executor.submit(pedir) for _ in range(quantos)]:
            futuro.result()
    assert len(emails) == LIMITE_ENVIOS_VERIFICACAO


def test_migracao_tira_o_email_em_claro_dos_links(client: TestClient, emails) -> None:
    """Bancos que rodaram a primeira versão da tabela (coluna `email`) passam a `email_hash`."""
    from app.core.inicializacao_banco import remover_email_em_claro_dos_links_de_confirmacao

    _cadastrar(client)
    with engine.begin() as conexao:
        conexao.execute(text("ALTER TABLE tokens_verificacao_email DROP COLUMN email_hash"))
        conexao.execute(text("ALTER TABLE tokens_verificacao_email ADD COLUMN email VARCHAR(150) NOT NULL DEFAULT 'x@edu.unifor.br'"))
    engine.dispose()
    remover_email_em_claro_dos_links_de_confirmacao()
    remover_email_em_claro_dos_links_de_confirmacao()  # idempotente
    engine.dispose()

    with engine.connect() as conexao:
        colunas = set(conexao.execute(text("SELECT * FROM tokens_verificacao_email LIMIT 0")).keys())
    assert "email" not in colunas and "email_hash" in colunas
    # O link antigo foi descartado; um novo pedido funciona normalmente.
    assert _confirmar(client, _token_do_email(emails[0])).status_code == 400
    client.post("/auth/reenviar-verificacao", json={"email": "nova@edu.unifor.br"})
    assert _confirmar(client, _token_do_email(emails[-1])).status_code == 200


def test_ativacao_publica_evento_e_observador_da_boas_vindas(client: TestClient, emails) -> None:
    """usuario.ativado → observador (sem broker, chamado no próprio processo) → notificação + e-mail."""
    from app.entities.notificacao import Notificacao
    from app.entities.registro_auditoria import RegistroAuditoria

    _cadastrar(client, "boasvindas@edu.unifor.br")
    assert _confirmar(client, _token_do_email(emails[0])).status_code == 200

    assert [m["assunto"] for m in emails][-1] == "Bem-vindo(a) ao Uni SOS"
    with FabricaSessao() as sessao:
        tipos = set(sessao.scalars(select(RegistroAuditoria.tipo)))
        notificacoes = list(sessao.scalars(select(Notificacao).where(Notificacao.tipo == "boas_vindas")))
    assert {"usuario.criado", "usuario.ativado"} <= tipos
    assert len(notificacoes) == 1

    # Confirmar de novo (link já usado) não repete as boas-vindas.
    assert _confirmar(client, _token_do_email(emails[0])).status_code == 400
    with FabricaSessao() as sessao:
        assert sessao.scalar(select(func.count()).select_from(Notificacao).where(Notificacao.tipo == "boas_vindas")) == 1
