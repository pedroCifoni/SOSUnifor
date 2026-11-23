"""POA (aspectos) e eventos: auditoria, desempenho, mascaramento de logs, fallback e consumidores."""

import asyncio
import inspect
import json
import logging
import re
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core import eventos
from app.core.aspecto_http import FiltroDadosSensiveis, instalar_mascaramento_de_logs, mascarar
from app.core.aspectos import PontoDeCorte, auditar, medir_desempenho, tecer
from app.core.database import FabricaSessao
from app.core.eventos import Evento
from app.entities.registro_auditoria import RegistroAuditoria
from testes.conftest import token_de


def _cabecalho(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _registros(tipo: str | None = None) -> list[RegistroAuditoria]:
    with FabricaSessao() as sessao:
        consulta = select(RegistroAuditoria).order_by(RegistroAuditoria.ocorrido_em)
        if tipo:
            consulta = consulta.where(RegistroAuditoria.tipo == tipo)
        return list(sessao.scalars(consulta))


def _id_do_usuario(email: str) -> UUID:
    from app.entities.usuario import Usuario

    with FabricaSessao() as sessao:
        return sessao.scalar(select(Usuario.id).where(Usuario.email == email))


# ---------- aspectos aplicados aos services ----------
def test_criar_ocorrencia_audita_e_publica_evento_sem_conteudo_da_denuncia(client: TestClient, criar_usuario) -> None:
    autor = criar_usuario("autor@unifor.br", nome="Autor")
    token = token_de(client, "autor@unifor.br", "senha123")
    resposta = client.post(
        "/ocorrencias",
        headers={**_cabecalho(token), "X-Request-ID": "req-teste-123"},
        json={"titulo": "Assédio no bloco", "descricao": "CONTEUDO-SIGILOSO", "local": "Bloco A", "tipo": "denuncia"},
    )
    assert resposta.status_code == 201, resposta.text
    assert resposta.headers["X-Request-ID"] == "req-teste-123"
    ocorrencia_id = resposta.json()["id"]

    [acao] = _registros("auditoria.ocorrencia.criar")
    [evento] = _registros("ocorrencia.criada")
    for registro in (acao, evento):
        assert registro.resultado == "sucesso"
        assert registro.ator_id == autor.id
        assert registro.entidade == "ocorrencia"
        assert registro.entidade_id == ocorrencia_id
        assert registro.request_id == "req-teste-123"
        assert registro.origem == "direto"  # sem broker nos testes: fallback gravou direto no banco
        texto = json.dumps(registro.dados, ensure_ascii=False)
        assert "CONTEUDO-SIGILOSO" not in texto and "Assédio" not in texto
    assert evento.dados["tipo_ocorrencia"] == "denuncia"
    assert acao.dados["detalhes"]["protocolo"] == resposta.json()["protocolo"]


def test_denuncia_anonima_nao_revela_o_autor_na_auditoria(client: TestClient, criar_usuario) -> None:
    criar_usuario("anonimo@unifor.br")
    token = token_de(client, "anonimo@unifor.br", "senha123")
    resposta = client.post(
        "/ocorrencias",
        headers=_cabecalho(token),
        json={"titulo": "Denúncia", "local": "Bloco B", "tipo": "denuncia", "anonima": True},
    )
    assert resposta.status_code == 201, resposta.text
    assert all(registro.ator_id is None for registro in _registros())


def test_encaminhar_e_mudar_status_sao_auditados(client: TestClient, criar_usuario) -> None:
    criar_usuario("autor@unifor.br")
    autor = token_de(client, "autor@unifor.br", "senha123")
    admin = token_de(client, "admin@unifor.br")
    tecnico_id = _id_do_usuario("tecnico@unifor.br")
    ocorrencia = client.post(
        "/ocorrencias",
        headers=_cabecalho(autor),
        json={"titulo": "Projetor", "local": "Sala 1", "tipo": "manutencao"},
    ).json()

    encaminhada = client.patch(
        f"/ocorrencias/{ocorrencia['id']}/encaminhar", headers=_cabecalho(admin), json={"responsavelId": str(tecnico_id)}
    )
    assert encaminhada.status_code == 200, encaminhada.text
    tecnico = token_de(client, "tecnico@unifor.br")
    aceite = client.patch(
        f"/ocorrencias/{ocorrencia['id']}/status", headers=_cabecalho(tecnico), json={"status": "em_atendimento"}
    )
    assert aceite.status_code == 200, aceite.text

    [encaminhar] = _registros("auditoria.ocorrencia.encaminhar")
    assert encaminhar.ator_id == _id_do_usuario("admin@unifor.br")
    assert encaminhar.dados["detalhes"]["responsavel_id"] == str(tecnico_id)
    [status] = _registros("auditoria.ocorrencia.mudar_status")
    assert status.ator_id == tecnico_id and status.dados["detalhes"]["status"] == "em_atendimento"
    assert len(_registros("ocorrencia.encaminhada")) == len(_registros("ocorrencia.status_alterado")) == 1


def test_erro_de_negocio_e_auditado_com_resultado_erro_sem_senha(client: TestClient, token_admin: str) -> None:
    dados = {"nome": "Repetida", "email": "admin@unifor.br", "perfil": "usuario", "senha": "SENHA-SECRETA-1"}
    resposta = client.post("/usuarios", headers=_cabecalho(token_admin), json=dados)
    assert resposta.status_code == 409

    [registro] = _registros("auditoria.usuario.criar")
    assert registro.resultado == "erro"
    assert registro.ator_id == _id_do_usuario("admin@unifor.br")  # veio do contexto da requisição
    assert "ConflitoErro" in registro.dados["erro"]
    assert registro.dados["detalhes"] == {"perfil": "usuario"}
    assert "SENHA-SECRETA-1" not in json.dumps(registro.dados)
    # A operação falhou: nenhum evento de domínio é publicado.
    assert not [r for r in _registros() if not r.tipo.startswith("auditoria.")]


def test_edicao_exclusao_e_lote_sao_auditados_sem_valores_sensiveis(client: TestClient, token_admin: str) -> None:
    criado = client.post(
        "/usuarios",
        headers=_cabecalho(token_admin),
        json={"nome": "Pessoa", "email": "pessoa@unifor.br", "perfil": "usuario", "senha": "SENHA-INICIAL"},
    ).json()
    editado = client.put(
        f"/usuarios/{criado['id']}", headers=_cabecalho(token_admin), json={"senha": "SENHA-NOVA-99", "nome": "Outro Nome"}
    )
    assert editado.status_code == 200
    lote = client.post(
        "/usuarios/lote",
        headers=_cabecalho(token_admin),
        json={"criacoes": [{"nome": "Lote", "email": "lote@unifor.br", "perfil": "usuario", "senha": "SENHA-LOTE"}]},
    )
    assert lote.status_code == 200
    assert client.delete(f"/usuarios/{criado['id']}", headers=_cabecalho(token_admin)).status_code == 204

    [edicao] = _registros("auditoria.usuario.editar")
    assert edicao.entidade_id == criado["id"]
    assert edicao.dados["detalhes"] == {"campos_alterados": "nome,senha"}
    [em_lote] = _registros("auditoria.usuario.salvar_em_lote")
    assert em_lote.dados["detalhes"] == {"criacoes": 1, "atualizacoes": 0, "exclusoes": 0}
    [exclusao] = _registros("auditoria.usuario.excluir")
    assert exclusao.resultado == "sucesso" and exclusao.entidade_id == criado["id"]
    tudo = json.dumps([r.dados for r in _registros()])
    for segredo in ("SENHA-INICIAL", "SENHA-NOVA-99", "SENHA-LOTE", "pessoa@unifor.br", "lote@unifor.br"):
        assert segredo not in tudo


def test_redefinir_senha_auditada_com_o_dono_do_link_e_sem_token(client: TestClient, emails, monkeypatch) -> None:
    from app.services.auth_service import AuthService

    consultas: list[str] = []
    original = AuthService.dono_do_link
    monkeypatch.setattr(AuthService, "dono_do_link", lambda self, token: consultas.append("x") or original(self, token))

    client.post("/auth/esqueci-senha", json={"email": "admin@unifor.br"})
    token = re.search(r"token=([A-Za-z0-9_-]+)", emails[0]["texto"] or "").group(1)
    assert client.post("/auth/redefinir-senha", json={"token": token, "nova_senha": "NOVA-SENHA-7"}).status_code == 200
    assert len(consultas) == 1  # o dono do link é consultado uma vez só por chamada
    # Link já usado: a conta é conhecida, então a tentativa fica na trilha como erro.
    assert client.post("/auth/redefinir-senha", json={"token": token, "nova_senha": "OUTRA-SENHA-8"}).status_code == 400
    # Link que nem existe (ex.: script anônimo chutando tokens): não enche a trilha.
    for _ in range(3):
        resposta = client.post("/auth/redefinir-senha", json={"token": "link-falso-" + "a" * 40, "nova_senha": "x" * 8})
        assert resposta.status_code == 400

    sucesso, erro = _registros("auditoria.auth.redefinir_senha")
    admin_id = _id_do_usuario("admin@unifor.br")
    assert (sucesso.resultado, sucesso.ator_id, sucesso.entidade_id) == ("sucesso", admin_id, str(admin_id))
    assert (erro.resultado, erro.ator_id, erro.entidade_id) == ("erro", admin_id, str(admin_id))
    tudo = json.dumps([sucesso.dados, erro.dados])
    assert token not in tudo and "NOVA-SENHA-7" not in tudo and "OUTRA-SENHA-8" not in tudo and "link-falso" not in tudo


def test_lote_de_usuarios_audita_cada_conta_afetada(client: TestClient, token_admin: str) -> None:
    """O painel de usuários só usa POST /usuarios/lote: a trilha precisa dizer QUAIS contas mudaram."""
    cabecalho = {**_cabecalho(token_admin), "X-Request-ID": "req-lote-1"}
    editar = client.post(
        "/usuarios", headers=_cabecalho(token_admin), json={"nome": "Editar", "email": "editar@unifor.br", "perfil": "usuario", "senha": "senha123"}
    ).json()
    excluir = client.post(
        "/usuarios", headers=_cabecalho(token_admin), json={"nome": "Excluir", "email": "excluir@unifor.br", "perfil": "usuario", "senha": "senha123"}
    ).json()
    lote = client.post(
        "/usuarios/lote",
        headers=cabecalho,
        json={
            "criacoes": [{"nome": "Nova", "email": "nova-lote@unifor.br", "perfil": "tecnico", "senha": "SENHA-LOTE"}],
            "atualizacoes": [{"id": editar["id"], "perfil": "admin", "senha": None, "nome": "Novo Nome"}],
            "exclusoes": [excluir["id"]],
        },
    )
    assert lote.status_code == 200, lote.text
    [criado_id] = lote.json()["idsCriados"]
    assert criado_id == str(_id_do_usuario("nova-lote@unifor.br"))

    admin_id = _id_do_usuario("admin@unifor.br")
    do_lote = [r for r in _registros() if r.request_id == "req-lote-1"]
    por_acao = {r.tipo: r for r in do_lote}
    assert set(por_acao) == {
        "auditoria.usuario.salvar_em_lote",
        "auditoria.usuario.criar",
        "auditoria.usuario.editar",
        "auditoria.usuario.excluir",
    }
    assert all(r.ator_id == admin_id and r.resultado == "sucesso" and r.entidade == "usuario" for r in do_lote)
    assert por_acao["auditoria.usuario.criar"].entidade_id == criado_id
    assert por_acao["auditoria.usuario.criar"].dados["detalhes"] == {"perfil": "tecnico"}
    assert por_acao["auditoria.usuario.editar"].entidade_id == editar["id"]
    assert por_acao["auditoria.usuario.editar"].dados["detalhes"] == {"campos_alterados": "nome,perfil"}
    assert por_acao["auditoria.usuario.excluir"].entidade_id == excluir["id"]
    assert "SENHA-LOTE" not in json.dumps([r.dados for r in do_lote]) and "nova-lote" not in json.dumps([r.dados for r in do_lote])


def test_lote_que_falha_nao_registra_itens(client: TestClient, token_admin: str) -> None:
    resposta = client.post(
        "/usuarios/lote",
        headers={**_cabecalho(token_admin), "X-Request-ID": "req-lote-2"},
        json={
            "criacoes": [{"nome": "Nova", "email": "nova-falha@unifor.br", "perfil": "usuario", "senha": "senha123"}],
            "exclusoes": [str(uuid4())],
        },
    )
    assert resposta.status_code == 404
    [registro] = [r for r in _registros() if r.request_id == "req-lote-2"]
    assert (registro.tipo, registro.resultado) == ("auditoria.usuario.salvar_em_lote", "erro")


def test_falha_na_auditoria_nao_derruba_a_operacao(client: TestClient, token_admin: str, monkeypatch) -> None:
    def falhar(*_args, **_kwargs):
        raise RuntimeError("banco de auditoria fora do ar")

    monkeypatch.setattr("app.services.auditoria_service.gravar_evento", falhar)
    resposta = client.post(
        "/usuarios",
        headers=_cabecalho(token_admin),
        json={"nome": "Nova", "email": "nova@unifor.br", "perfil": "usuario", "senha": "senha123"},
    )
    assert resposta.status_code == 201


def test_com_broker_o_evento_vai_para_a_fila_e_nao_para_o_banco(client: TestClient, token_admin: str, monkeypatch) -> None:
    publicados: list[Evento] = []
    monkeypatch.setattr(eventos, "publicar", lambda evento: publicados.append(evento) or True)
    client.delete(f"/usuarios/{uuid4()}", headers=_cabecalho(token_admin))
    assert [e.tipo for e in publicados] == ["auditoria.usuario.excluir"]
    assert publicados[0].dados["resultado"] == "erro"
    assert _registros() == []  # quem grava é o consumidor da fila


def test_sem_broker_publicar_devolve_false() -> None:
    assert eventos.conectado() is False
    assert eventos.publicar(Evento(tipo="ocorrencia.criada")) is False


def test_broker_sem_confirmacao_fica_degradado_e_as_proximas_vao_direto_ao_fallback(monkeypatch) -> None:
    """CloudAMQP degradado (TCP vivo, confirms não chegam): só a primeira publicação espera o timeout."""
    import threading
    import time

    loop = asyncio.new_event_loop()
    threading.Thread(target=loop.run_forever, daemon=True).start()
    tentativas: list[str] = []

    async def nunca_confirma(evento: Evento) -> None:
        tentativas.append(evento.tipo)
        await asyncio.sleep(10)

    monkeypatch.setattr(eventos, "_degradado_ate", 0.0)
    monkeypatch.setattr(eventos, "_exchange", object())
    monkeypatch.setattr(eventos, "_loop", loop)
    monkeypatch.setattr(eventos, "publicar_async", nunca_confirma)
    monkeypatch.setattr(eventos, "TEMPO_CONFIRMACAO_SEGUNDOS", 0.05)
    try:
        assert eventos.publicar(Evento(tipo="ocorrencia.criada")) is False
        assert eventos.degradado()
        inicio = time.perf_counter()
        assert eventos.publicar(Evento(tipo="auditoria.ocorrencia.criar")) is False
        assert time.perf_counter() - inicio < 0.05
        assert tentativas == ["ocorrencia.criada"]  # a segunda nem foi ao broker
    finally:
        loop.call_soon_threadsafe(loop.stop)


def test_services_de_negocio_nao_chamam_auditoria_log_nem_eventos_diretamente() -> None:
    """O ponto da POA: os interesses transversais entram só pelos decorators."""
    pasta = Path(__file__).resolve().parents[2] / "app" / "services"
    proibidos = re.compile(r"\b(logging|logger|entregar|gravar_evento|eventos\.publicar|registrar_evento)\b")
    for nome in ("ocorrencia_service.py", "usuario_service.py", "auth_service.py"):
        codigo = (pasta / nome).read_text(encoding="utf-8")
        assert not proibidos.search(codigo), nome


# ---------- desempenho e tecelagem ----------
def test_medir_desempenho_registra_chamada_lenta(caplog) -> None:
    import time

    class RelatorioService:
        def gerar(self) -> str:
            time.sleep(0.03)
            return "ok"

        def rapido(self) -> str:
            return "ok"

    costurados = tecer(PontoDeCorte("teste", classe=r"^RelatorioService$"), "medir_desempenho", medir_desempenho(10), [RelatorioService])
    assert sorted(costurados) == ["RelatorioService.gerar", "RelatorioService.rapido"]
    # Tecer de novo não envolve duas vezes.
    assert tecer(PontoDeCorte("teste", classe=r"^RelatorioService$"), "medir_desempenho", medir_desempenho(10), [RelatorioService]) == []

    with caplog.at_level(logging.WARNING, logger="app.desempenho"):
        assert RelatorioService().gerar() == "ok"
        RelatorioService().rapido()
    lentas = [r.getMessage() for r in caplog.records if r.name == "app.desempenho"]
    assert len(lentas) == 1 and "RelatorioService.gerar" in lentas[0]


def test_services_da_aplicacao_estao_costurados() -> None:
    from app.services.ocorrencia_service import OcorrenciaService
    from app.services.usuario_service import UsuarioService

    assert OcorrenciaService.criar.__aspectos__ == ("publicar_evento", "auditar", "medir_desempenho")
    assert UsuarioService.excluir.__aspectos__ == ("auditar", "medir_desempenho")
    # listar tem um @medir_desempenho(300) explícito: a tecelagem por padrão não envolve de novo.
    assert OcorrenciaService.listar.__aspectos__ == ("medir_desempenho",)
    assert isinstance(inspect.getattr_static(OcorrenciaService, "pode_acessar"), staticmethod)


def test_auditar_preserva_retorno_e_excecao() -> None:
    entregues: list[Evento] = []

    class Alvo:
        @auditar("teste.acao", entidade="teste", entidade_id="item_id")
        def executar(self, item_id: str, falhar: bool = False) -> str:
            if falhar:
                raise ValueError("detalhe interno")
            return item_id

    original = eventos.publicar
    eventos.publicar = lambda evento: entregues.append(evento) or True  # type: ignore[assignment]
    try:
        assert Alvo().executar("abc") == "abc"
        with pytest.raises(ValueError):
            Alvo().executar("xyz", falhar=True)
    finally:
        eventos.publicar = original  # type: ignore[assignment]
    assert [(e.dados["entidade_id"], e.dados["resultado"]) for e in entregues] == [("abc", "sucesso"), ("xyz", "erro")]
    assert entregues[1].dados["erro"] == "ValueError"  # exceções inesperadas: só o nome, nunca a mensagem


# ---------- aspecto HTTP: mascaramento ----------
def test_token_do_websocket_mascarado_no_log_de_acesso_do_uvicorn(caplog) -> None:
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.assinatura"
    instalar_mascaramento_de_logs()
    with caplog.at_level(logging.INFO):
        logging.getLogger("uvicorn.access").info(
            '%s - "%s %s HTTP/%s" %d', "127.0.0.1:5000", "GET", f"/ws/notificacoes?token={jwt}", "1.1", 101
        )
        logging.getLogger("uvicorn.error").info('%s - "WebSocket %s" [accepted]', "127.0.0.1", f"/ws/notificacoes?token={jwt}")
        logging.getLogger("app.qualquer").info("Authorization: Bearer %s", jwt)
    assert jwt not in caplog.text
    assert caplog.text.count("token=***") == 2 and "Bearer ***" in caplog.text


def test_mascarar_cobre_query_senha_e_bearer() -> None:
    assert mascarar("/ws?x=1&token=abc.def&y=2") == "/ws?x=1&token=***&y=2"
    assert mascarar('{"senha": "123456"}') == '{"senha": "***"}'
    assert mascarar("Bearer abc.def") == "Bearer ***"
    registro = logging.LogRecord("t", logging.INFO, __file__, 1, "%s", ("access_token=zzz",), None)
    FiltroDadosSensiveis().filter(registro)
    assert registro.getMessage() == "access_token=***"


def test_middleware_gera_request_id_e_registra_a_requisicao(client: TestClient, caplog) -> None:
    with caplog.at_level(logging.INFO, logger="app.http"):
        resposta = client.get("/health?token=nao-deve-aparecer")
    request_id = resposta.headers["X-Request-ID"]
    assert re.fullmatch(r"[0-9a-f]{32}", request_id)
    linhas = [r.getMessage() for r in caplog.records if r.name == "app.http"]
    assert any(request_id in linha and "GET /health" in linha and "ms" in linha for linha in linhas)
    assert "nao-deve-aparecer" not in caplog.text
    # Cabeçalho inválido vindo do cliente é trocado por um novo.
    assert client.get("/health", headers={"X-Request-ID": "a b<script>"}).headers["X-Request-ID"] != "a b<script>"


# ---------- consumidores ----------
class MensagemFalsa:
    def __init__(self, corpo: bytes, redelivered: bool = False, headers: dict | None = None) -> None:
        self.body = corpo
        self.message_id = "teste"
        self.type = "ocorrencia.criada"
        self.headers = headers or {}
        self.redelivered = redelivered
        self.situacao: str | None = None

    async def ack(self) -> None:
        self.situacao = "ack"

    async def nack(self, requeue: bool = True) -> None:
        self.situacao = f"nack(requeue={requeue})"

    async def reject(self, requeue: bool = False) -> None:
        self.situacao = f"reject(requeue={requeue})"


def test_consumidor_de_auditoria_e_idempotente(client: TestClient) -> None:
    evento = Evento(tipo="ocorrencia.criada", dados={"entidade": "ocorrencia", "entidade_id": "x1", "resultado": "sucesso"})
    corpo = evento.model_dump_json().encode()
    primeira, reentrega = MensagemFalsa(corpo), MensagemFalsa(corpo, redelivered=True)
    asyncio.run(eventos.consumir_auditoria(primeira))
    asyncio.run(eventos.consumir_auditoria(reentrega))
    assert primeira.situacao == reentrega.situacao == "ack"
    [registro] = _registros()
    assert registro.id == evento.id and registro.origem == "broker" and registro.entidade_id == "x1"


def test_mensagem_invalida_vai_para_a_fila_de_mortos_sem_travar(client: TestClient) -> None:
    invalida = MensagemFalsa(b"{nao e json")
    asyncio.run(eventos.consumir_auditoria(invalida))
    assert invalida.situacao == "reject(requeue=False)"
    assert _registros() == []


def test_queda_curta_do_banco_e_coberta_pelas_novas_tentativas_com_espera(client: TestClient, monkeypatch) -> None:
    from app.services import auditoria_service

    esperas: list[float] = []

    async def esperar(segundos: float) -> None:
        esperas.append(segundos)

    gravar_de_verdade = auditoria_service.gravar_evento
    falhas = iter([RuntimeError("banco fora"), RuntimeError("banco fora")])

    def gravar(evento, origem):
        erro = next(falhas, None)
        if erro:
            raise erro
        return gravar_de_verdade(evento, origem)

    monkeypatch.setattr(eventos, "_esperar", esperar)
    monkeypatch.setattr("app.services.auditoria_service.gravar_evento", gravar)
    evento = Evento(tipo="ocorrencia.criada")
    # Mesmo uma reentrega (ex.: depois de um deploy) ganha todas as tentativas antes da fila de mortos.
    mensagem = MensagemFalsa(evento.model_dump_json().encode(), redelivered=True)
    asyncio.run(eventos.consumir_auditoria(mensagem))
    assert mensagem.situacao == "ack"
    assert esperas == list(eventos.ESPERAS_NOVA_TENTATIVA_SEGUNDOS[:2])
    assert [r.id for r in _registros()] == [evento.id]


def test_falha_persistente_vai_para_a_fila_de_mortos_depois_de_todas_as_tentativas(client: TestClient, monkeypatch) -> None:
    chamadas: list[str] = []

    async def esperar(_segundos: float) -> None:
        return None

    def falhar(*_args):
        chamadas.append("x")
        raise RuntimeError("banco fora")

    monkeypatch.setattr(eventos, "_esperar", esperar)
    monkeypatch.setattr("app.services.auditoria_service.gravar_evento", falhar)
    mensagem = MensagemFalsa(Evento(tipo="ocorrencia.criada").model_dump_json().encode())
    asyncio.run(eventos.consumir_auditoria(mensagem))
    assert mensagem.situacao == "reject(requeue=False)"
    assert len(chamadas) == len(eventos.ESPERAS_NOVA_TENTATIVA_SEGUNDOS) + 1
    assert sum(eventos.ESPERAS_NOVA_TENTATIVA_SEGUNDOS) >= 30  # cobre uma queda curta do banco


class FilaFalsa:
    def __init__(self, mensagens: list[MensagemFalsa]) -> None:
        self.mensagens = list(mensagens)
        self.declaration_result = type("Declaracao", (), {"message_count": len(mensagens)})()

    async def get(self, no_ack: bool = False, fail: bool = True) -> MensagemFalsa | None:
        return self.mensagens.pop(0) if self.mensagens else None


class CanalFalso:
    def __init__(self, fila: FilaFalsa) -> None:
        self.fila = fila
        self.republicadas: list[tuple[str, object]] = []
        canal = self

        class ExchangePadrao:
            async def publish(self, mensagem, routing_key: str) -> None:
                canal.republicadas.append((routing_key, mensagem))
                fila.mensagens.append(mensagem)

        self.default_exchange = ExchangePadrao()

    async def declare_queue(self, nome: str, durable: bool = True) -> FilaFalsa:
        assert nome == eventos.FILA_MORTOS
        return self.fila


def test_reprocessar_mortos_devolve_os_eventos_a_trilha(client: TestClient) -> None:
    perdidos = [Evento(tipo="auditoria.ocorrencia.criar", dados={"entidade": "ocorrencia", "entidade_id": f"o{i}"}) for i in range(2)]
    mensagens = [MensagemFalsa(e.model_dump_json().encode()) for e in perdidos] + [MensagemFalsa(b"lixo")]
    canal = CanalFalso(FilaFalsa(mensagens))
    resumo = asyncio.run(eventos.reprocessar_mortos(canal))
    assert resumo == {"regravados": 2, "descartados": 1, "devolvidos": 0}
    assert all(m.situacao == "ack" for m in mensagens)
    assert {r.id for r in _registros()} == {e.id for e in perdidos}
    # Idempotente: reprocessar de novo um evento que já está na trilha não duplica.
    asyncio.run(eventos.reprocessar_mortos(CanalFalso(FilaFalsa([MensagemFalsa(perdidos[0].model_dump_json().encode())]))))
    assert len(_registros()) == 2


def test_reprocessar_mortos_com_o_banco_ainda_fora_devolve_ao_fim_da_fila_e_para(client: TestClient, monkeypatch) -> None:
    def falhar(*_args):
        raise RuntimeError("banco fora")

    monkeypatch.setattr("app.services.auditoria_service.gravar_evento", falhar)
    mensagens = [MensagemFalsa(Evento(tipo="ocorrencia.criada").model_dump_json().encode()) for _ in range(3)]
    canal = CanalFalso(FilaFalsa(mensagens))
    resumo = asyncio.run(eventos.reprocessar_mortos(canal))
    assert resumo == {"regravados": 0, "descartados": 0, "devolvidos": 1}
    [(fila, republicada)] = canal.republicadas
    assert fila == eventos.FILA_MORTOS
    assert republicada.body == mensagens[0].body
    assert republicada.headers[eventos.CABECALHO_REPROCESSAMENTOS] == 1
    assert mensagens[0].situacao == "ack" and mensagens[1].situacao is None  # a rodada parou


def test_consumidor_de_metricas_conta_ocorrencias_por_tipo(caplog) -> None:
    antes = eventos.indicadores.por_tipo_de_ocorrencia["sos"]
    mensagem = MensagemFalsa(Evento(tipo="ocorrencia.criada", dados={"tipo_ocorrencia": "sos"}).model_dump_json().encode())
    with caplog.at_level(logging.INFO, logger="app.core.eventos"):
        asyncio.run(eventos.consumir_metricas(mensagem))
    assert mensagem.situacao == "ack"
    assert eventos.indicadores.por_tipo_de_ocorrencia["sos"] == antes + 1
    # Com vários workers a fila é repartida: o log não pode se passar por total do sistema.
    assert "parciais" in caplog.text and "processo" in caplog.text


# ---------- GET /auditoria ----------
def test_auditoria_so_para_admin(client: TestClient, criar_usuario) -> None:
    criar_usuario("comum@unifor.br")
    assert client.get("/auditoria").status_code == 401
    for email, senha in (("comum@unifor.br", "senha123"), ("seguranca@unifor.br", "123456"), ("tecnico@unifor.br", "123456")):
        assert client.get("/auditoria", headers=_cabecalho(token_de(client, email, senha))).status_code == 403
    assert client.get("/auditoria", headers=_cabecalho(token_de(client, "admin@unifor.br"))).status_code == 200


def test_auditoria_paginada_por_cursor_e_filtrada(client: TestClient, token_admin: str) -> None:
    for indice in range(3):
        client.post(
            "/usuarios",
            headers=_cabecalho(token_admin),
            json={"nome": f"P{indice}", "email": f"p{indice}@unifor.br", "perfil": "usuario", "senha": "senha123"},
        )
    client.delete(f"/usuarios/{uuid4()}", headers=_cabecalho(token_admin))

    pagina = client.get("/auditoria?limite=2", headers=_cabecalho(token_admin)).json()
    assert len(pagina) == 2
    assert pagina[0]["acao"] == "usuario.excluir" and pagina[0]["resultado"] == "erro"
    assert pagina[0]["atorNome"] == "Administrador" and pagina[0]["entidade"] == "usuario"
    ultimo = pagina[-1]
    resto = client.get(
        "/auditoria", headers=_cabecalho(token_admin), params={"antes_de": ultimo["ocorridoEm"], "antes_id": ultimo["id"]}
    ).json()
    assert len(resto) == 2 and not {r["id"] for r in resto} & {r["id"] for r in pagina}

    criacoes = client.get("/auditoria", headers=_cabecalho(token_admin), params={"tipo": "auditoria.usuario.criar"}).json()
    assert len(criacoes) == 3 and all(r["acao"] == "usuario.criar" for r in criacoes)
    futuro = client.get("/auditoria", headers=_cabecalho(token_admin), params={"desde": "2999-01-01T00:00:00Z"}).json()
    assert futuro == []
    periodo_invertido = client.get(
        "/auditoria", headers=_cabecalho(token_admin), params={"desde": "2025-02-01T00:00:00Z", "ate": "2025-01-01T00:00:00Z"}
    )
    assert periodo_invertido.status_code == 400
