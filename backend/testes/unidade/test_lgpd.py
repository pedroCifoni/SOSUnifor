"""LGPD: ciência dos termos, exportação, pedido de exclusão, anonimização, retenção e minimização."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import FabricaSessao
from app.core.privacidade import NOME_ANONIMIZADO, VERSAO_TERMOS
from app.entities.evento_ocorrencia import EventoOcorrencia
from app.entities.notificacao import Notificacao
from app.entities.ocorrencia import Ocorrencia
from app.entities.token_redefinicao_senha import TokenRedefinicaoSenha
from app.entities.usuario import Usuario
from testes.conftest import token_de


def _cabecalho(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _criar_ocorrencia(client: TestClient, token: str, *, tipo: str = "manutencao", titulo: str = "Pedido", anonima: bool = False) -> dict:
    resposta = client.post(
        "/ocorrencias",
        headers=_cabecalho(token),
        json={"titulo": titulo, "descricao": "Detalhes", "local": "Bloco A", "tipo": tipo, "anonima": anonima},
    )
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


# ---------- ciência dos termos ----------
def test_aceite_de_termos_registra_versao_e_data(client: TestClient, criar_usuario) -> None:
    criar_usuario("titular@unifor.br")
    token = token_de(client, "titular@unifor.br", "senha123")

    situacao = client.get("/me/termos", headers=_cabecalho(token))
    assert situacao.status_code == 200
    assert situacao.json() == {"versaoAtual": VERSAO_TERMOS, "versaoAceita": None, "aceitosEm": None, "pendente": True}

    antiga = client.post("/me/termos", headers=_cabecalho(token), json={"versao": "1999-01"})
    assert antiga.status_code == 400

    aceite = client.post("/me/termos", headers=_cabecalho(token), json={"versao": VERSAO_TERMOS})
    assert aceite.status_code == 200, aceite.text
    assert aceite.json()["pendente"] is False
    assert aceite.json()["versaoAceita"] == VERSAO_TERMOS
    assert aceite.json()["aceitosEm"]

    assert client.get("/me/termos", headers=_cabecalho(token)).json()["pendente"] is False
    assert client.get("/me/termos").status_code == 401


def test_versao_nova_dos_termos_volta_a_ficar_pendente(client: TestClient, criar_usuario) -> None:
    usuario = criar_usuario("titular@unifor.br")
    with FabricaSessao() as sessao:
        registro = sessao.get(Usuario, usuario.id)
        registro.termos_versao = "versao-antiga"
        registro.termos_aceitos_em = datetime.now(timezone.utc)
        sessao.commit()
    token = token_de(client, "titular@unifor.br", "senha123")
    assert client.get("/me/termos", headers=_cabecalho(token)).json()["pendente"] is True


def test_sos_funciona_sem_aceite_dos_termos(client: TestClient, criar_usuario) -> None:
    """Proteção da vida (art. 7º, VII): o aceite pendente nunca bloqueia o SOS."""
    criar_usuario("titular@unifor.br")
    token = token_de(client, "titular@unifor.br", "senha123")
    assert client.get("/me/termos", headers=_cabecalho(token)).json()["pendente"] is True
    _criar_ocorrencia(client, token, tipo="sos")


# ---------- acesso e portabilidade ----------
def test_exportacao_contem_so_os_dados_do_proprio_titular(client: TestClient, criar_usuario) -> None:
    criar_usuario("titular@unifor.br", nome="Titular Teste")
    criar_usuario("vizinho@unifor.br", nome="Vizinho Teste")
    titular = token_de(client, "titular@unifor.br", "senha123")
    vizinho = token_de(client, "vizinho@unifor.br", "senha123")
    admin = token_de(client, "admin@unifor.br")

    minha = _criar_ocorrencia(client, titular, titulo="Minha lâmpada")
    minha_anonima = _criar_ocorrencia(client, titular, tipo="denuncia", titulo="Minha denúncia", anonima=True)
    alheia = _criar_ocorrencia(client, vizinho, titulo="Lâmpada do vizinho")
    tecnico_id = next(u["id"] for u in client.get("/usuarios", headers=_cabecalho(admin)).json() if u["perfil"] == "tecnico")
    for ocorrencia in (minha, alheia):
        assert client.patch(
            f"/ocorrencias/{ocorrencia['id']}/encaminhar", headers=_cabecalho(admin), json={"responsavelId": tecnico_id}
        ).status_code == 200
    client.post("/me/termos", headers=_cabecalho(titular), json={"versao": VERSAO_TERMOS})

    resposta = client.get("/me/dados", headers=_cabecalho(titular))
    assert resposta.status_code == 200, resposta.text
    dados = resposta.json()

    assert dados["titular"]["email"] == "titular@unifor.br"
    assert dados["titular"]["termosVersao"] == VERSAO_TERMOS
    assert dados["titular"]["termosAceitosEm"]
    assert {o["id"] for o in dados["ocorrencias"]} == {minha["id"], minha_anonima["id"]}
    exportada = next(o for o in dados["ocorrencias"] if o["id"] == minha["id"])
    assert [e["tipo"] for e in exportada["eventos"]] == ["criada", "encaminhada"]
    assert len(dados["notificacoes"]) == 1  # "Seu chamado foi encaminhado"
    assert all(n["ocorrenciaId"] == minha["id"] for n in dados["notificacoes"])

    texto = resposta.text
    assert "vizinho@unifor.br" not in texto
    assert "Vizinho Teste" not in texto
    assert alheia["id"] not in texto
    assert "senha" not in texto.lower()
    assert client.get("/me/dados").status_code == 401


# ---------- pedido de exclusão ----------
def test_pedido_de_exclusao_exige_confirmacao_e_notifica_admins(client: TestClient, criar_usuario) -> None:
    criar_usuario("titular@unifor.br", nome="Titular Teste")
    criar_usuario("admin2@unifor.br", perfil="admin", nome="Segundo Admin")
    titular = token_de(client, "titular@unifor.br", "senha123")
    admin = token_de(client, "admin@unifor.br")
    admin2 = token_de(client, "admin2@unifor.br", "senha123")

    assert client.post("/me/solicitar-exclusao", headers=_cabecalho(titular), json={"confirmar": False}).status_code == 400

    pedido = client.post("/me/solicitar-exclusao", headers=_cabecalho(titular), json={"confirmar": True})
    assert pedido.status_code == 200, pedido.text
    solicitada_em = pedido.json()["solicitadaEm"]

    for token in (admin, admin2):
        avisos = [n for n in client.get("/notificacoes", headers=_cabecalho(token)).json() if n["tipo"] == "privacidade"]
        assert len(avisos) == 1
        assert avisos[0]["ocorrenciaId"] is None
        assert "Titular Teste" in avisos[0]["mensagem"]
    # O titular e os demais perfis não recebem o aviso.
    seguranca = token_de(client, "seguranca@unifor.br")
    assert client.get("/notificacoes", headers=_cabecalho(seguranca)).json() == []

    # Pedido repetido não muda a data nem avisa de novo.
    repetido = client.post("/me/solicitar-exclusao", headers=_cabecalho(titular), json={"confirmar": True})
    assert repetido.json()["solicitadaEm"] == solicitada_em
    assert len([n for n in client.get("/notificacoes", headers=_cabecalho(admin)).json() if n["tipo"] == "privacidade"]) == 1

    pedidos = client.get("/usuarios/pedidos-exclusao", headers=_cabecalho(admin))
    assert pedidos.status_code == 200
    assert [p["email"] for p in pedidos.json()] == ["titular@unifor.br"]
    assert client.get("/usuarios/pedidos-exclusao", headers=_cabecalho(titular)).status_code == 403


# ---------- anonimização ----------
def test_anonimizacao_e_irreversivel_e_preserva_ocorrencias_sem_identificar(client: TestClient, criar_usuario) -> None:
    titular_entidade = criar_usuario("titular@unifor.br", nome="Fulano de Tal")
    criar_usuario("tecnico2@unifor.br", perfil="tecnico", nome="Beltrano Técnico")
    titular = token_de(client, "titular@unifor.br", "senha123")
    admin = token_de(client, "admin@unifor.br")

    chamado = _criar_ocorrencia(client, titular, titulo="Ar-condicionado")
    client.post("/me/solicitar-exclusao", headers=_cabecalho(titular), json={"confirmar": True})
    client.post("/auth/esqueci-senha", json={"email": "titular@unifor.br"})

    resposta = client.post(f"/usuarios/{titular_entidade.id}/anonimizar", headers=_cabecalho(admin))
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["nome"] == NOME_ANONIMIZADO

    with FabricaSessao() as sessao:
        registro = sessao.get(Usuario, titular_entidade.id)
        assert registro.nome == NOME_ANONIMIZADO
        assert registro.email.startswith("anonimizado-") and registro.email.endswith("@anonimizado.invalid")
        assert "titular" not in registro.email
        assert registro.ativo is False
        assert registro.anonimizado_em is not None
        assert registro.senha_hash != titular_entidade.senha_hash
        assert sessao.scalars(select(Usuario).where(Usuario.email == "titular@unifor.br")).first() is None
        assert sessao.scalars(select(TokenRedefinicaoSenha).where(TokenRedefinicaoSenha.usuario_id == registro.id)).all() == []
        assert sessao.scalars(select(Notificacao).where(Notificacao.destinatario_id == registro.id)).all() == []
        ocorrencia = sessao.get(Ocorrencia, UUID(chamado["id"]))
        assert ocorrencia is not None and ocorrencia.autor_id == registro.id

    # Não entra mais com a senha antiga.
    assert client.post("/auth/login", json={"email": "titular@unifor.br", "senha": "senha123"}).status_code == 401
    # A ocorrência continua lá, sem o nome da pessoa.
    detalhe = client.get(f"/ocorrencias/{chamado['id']}", headers=_cabecalho(admin)).json()
    assert detalhe["solicitante"] == NOME_ANONIMIZADO
    assert "Fulano" not in str(detalhe)
    # Sai da lista de pedidos pendentes e não pode ser anonimizada de novo.
    assert client.get("/usuarios/pedidos-exclusao", headers=_cabecalho(admin)).json() == []
    assert client.post(f"/usuarios/{titular_entidade.id}/anonimizar", headers=_cabecalho(admin)).status_code == 409


def test_anonimizacao_remove_nome_do_responsavel_dos_eventos(client: TestClient, criar_usuario) -> None:
    criar_usuario("titular@unifor.br")
    tecnico = criar_usuario("tecnico2@unifor.br", perfil="tecnico", nome="Beltrano Técnico")
    titular = token_de(client, "titular@unifor.br", "senha123")
    admin = token_de(client, "admin@unifor.br")
    chamado = _criar_ocorrencia(client, titular)
    client.patch(f"/ocorrencias/{chamado['id']}/encaminhar", headers=_cabecalho(admin), json={"responsavelId": str(tecnico.id)})

    assert client.post(f"/usuarios/{tecnico.id}/anonimizar", headers=_cabecalho(admin)).status_code == 200

    with FabricaSessao() as sessao:
        descricoes = sessao.scalars(select(EventoOcorrencia.descricao)).all()
    assert not any("Beltrano" in descricao for descricao in descricoes)
    assert any(NOME_ANONIMIZADO in descricao for descricao in descricoes)


def test_admin_nao_anonimiza_a_si_mesmo_e_so_admin_anonimiza(client: TestClient, criar_usuario) -> None:
    outro = criar_usuario("outro@unifor.br")
    admin = token_de(client, "admin@unifor.br")
    usuario = token_de(client, "outro@unifor.br", "senha123")
    with FabricaSessao() as sessao:
        admin_id = sessao.scalars(select(Usuario.id).where(Usuario.email == "admin@unifor.br")).one()

    resposta = client.post(f"/usuarios/{admin_id}/anonimizar", headers=_cabecalho(admin))
    assert resposta.status_code == 400
    assert "própria" in resposta.json()["detail"]
    assert client.post(f"/usuarios/{outro.id}/anonimizar", headers=_cabecalho(usuario)).status_code == 403


def test_ultimo_admin_nao_pode_ser_anonimizado(client: TestClient, criar_usuario) -> None:
    """Só um administrador ativo: nem outra conta de admin (já desativada) consegue anonimizá-lo."""
    from app.services.privacidade_service import PrivacidadeService
    from app.core.excecoes import RegraDeNegocioErro

    desativado = criar_usuario("admin-antigo@unifor.br", perfil="admin", ativo=False)
    with FabricaSessao() as sessao:
        unico_admin = sessao.scalars(select(Usuario).where(Usuario.email == "admin@unifor.br")).one()
        with pytest.raises(RegraDeNegocioErro, match="ao menos um administrador"):
            PrivacidadeService(sessao).anonimizar(unico_admin.id, desativado)
        assert sessao.get(Usuario, unico_admin.id).nome != NOME_ANONIMIZADO


def test_contas_iniciais_nao_voltam_depois_de_anonimizadas(client: TestClient) -> None:
    from app.core.inicializacao_banco import criar_usuarios_iniciais

    admin = token_de(client, "admin@unifor.br")
    with FabricaSessao() as sessao:
        tecnico_id = sessao.scalars(select(Usuario.id).where(Usuario.email == "tecnico@unifor.br")).one()
    assert client.post(f"/usuarios/{tecnico_id}/anonimizar", headers=_cabecalho(admin)).status_code == 200

    criar_usuarios_iniciais()
    with FabricaSessao() as sessao:
        assert sessao.scalars(select(Usuario).where(Usuario.email == "tecnico@unifor.br")).first() is None


# ---------- retenção ----------
def test_rotina_de_retencao_apaga_so_o_que_venceu(client: TestClient, criar_usuario) -> None:
    from app.services.retencao_service import RetencaoService

    usuario = criar_usuario("titular@unifor.br")
    token = token_de(client, "titular@unifor.br", "senha123")
    chamado = _criar_ocorrencia(client, token)
    agora = datetime.now(timezone.utc)

    def token_redefinicao(sufixo: str, expira_em: datetime) -> TokenRedefinicaoSenha:
        return TokenRedefinicaoSenha(
            usuario_id=usuario.id, token_hash=sufixo.ljust(64, "0"), criado_em=expira_em - timedelta(minutes=30), expira_em=expira_em
        )

    def notificacao(titulo: str, criada_em: datetime, lida: bool) -> Notificacao:
        return Notificacao(
            destinatario_id=usuario.id,
            tipo="criada",
            titulo=titulo,
            mensagem="m",
            ocorrencia_id=UUID(chamado["id"]),
            criada_em=criada_em,
            lida=lida,
        )

    with FabricaSessao() as sessao:
        sessao.add_all(
            [
                token_redefinicao("a", agora - timedelta(days=3)),  # vencido há muito: apaga
                token_redefinicao("b", agora - timedelta(hours=1)),  # vencido há pouco: fica (limite de pedidos)
                token_redefinicao("c", agora + timedelta(minutes=20)),  # válido: fica
                notificacao("lida-antiga", agora - timedelta(days=200), True),  # apaga
                notificacao("lida-recente", agora - timedelta(days=10), True),
                notificacao("nao-lida-antiga", agora - timedelta(days=400), False),
            ]
        )
        sessao.commit()

    with FabricaSessao() as sessao:
        resultado = RetencaoService(sessao).executar()
        assert (resultado.tokens_apagados, resultado.notificacoes_apagadas) == (1, 1)
        # Idempotente: a segunda execução não encontra mais nada.
        assert RetencaoService(sessao).executar().total == 0

        hashes = {t.token_hash[0] for t in sessao.scalars(select(TokenRedefinicaoSenha))}
        assert hashes == {"b", "c"}
        titulos = set(sessao.scalars(select(Notificacao.titulo).where(Notificacao.destinatario_id == usuario.id)))
        assert titulos == {"lida-recente", "nao-lida-antiga"}
        assert sessao.get(Ocorrencia, UUID(chamado["id"])) is not None


# ---------- minimização ----------
def test_email_da_equipe_so_vai_para_o_admin(client: TestClient, criar_usuario) -> None:
    criar_usuario("titular@unifor.br")
    usuario = token_de(client, "titular@unifor.br", "senha123")
    admin = token_de(client, "admin@unifor.br")

    for rota in ("/usuarios/segurancas", "/usuarios/tecnicos"):
        para_usuario = client.get(rota, headers=_cabecalho(usuario)).json()
        assert para_usuario and all(item["email"] is None for item in para_usuario)
        para_admin = client.get(rota, headers=_cabecalho(admin)).json()
        assert all(item["email"] for item in para_admin)
