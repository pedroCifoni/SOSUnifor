"""Infraestrutura isolada da suíte HTTP.

As variáveis abaixo são definidas antes de qualquer import de ``app`` para que a
configuração do arquivo .env local nunca seja usada pelos testes.
"""

import os


# TESTES_DATABASE_URL permite que execuções em paralelo usem bancos diferentes
# (ex.: unisos_testes_lgpd), sem uma apagar os dados da outra. O banco precisa existir.
os.environ["DATABASE_URL"] = os.environ.get(
    "TESTES_DATABASE_URL", "postgresql+psycopg://unisos:uni12345@localhost:5433/unisos_testes"
)
os.environ["SMTP_HOST"] = ""
os.environ["BREVO_API_KEY"] = ""  # nunca usar uma chave real nos testes
# Porta fechada de propósito: os testes não publicam no RabbitMQ de desenvolvimento
# (a mensageria cai no modo local, só deste processo).
os.environ["RABBITMQ_URL"] = "amqp://guest:guest@127.0.0.1:1/"
os.environ["AMBIENTE"] = "teste"

from collections.abc import Callable
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.database import engine
from app.main import app


TABELAS_DE_TESTE = (
    "auditoria, notificacoes, eventos_ocorrencia, tokens_redefinicao_senha, tokens_verificacao_email, "
    "ocorrencias, areas_campus, tokens_sessao, tentativas_login, credentials"
)


@pytest.fixture
def emails(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, str | None]]:
    """Captura e-mails sem conectar ao SMTP configurado fora da suíte."""
    mensagens: list[dict[str, str | None]] = []

    def capturar(destinatario: str, assunto: str, texto: str, html: str | None = None) -> None:
        mensagens.append({"destinatario": destinatario, "assunto": assunto, "texto": texto, "html": html})

    monkeypatch.setattr("app.services.email_service.enviar_email", capturar)
    monkeypatch.setattr("app.core.email.enviar_email", capturar)
    return mensagens


@pytest.fixture(scope="session", autouse=True)
def preparar_banco_de_testes() -> None:
    """Executa uma vez o lifespan para criar a estrutura antes do primeiro TRUNCATE."""
    with TestClient(app):
        pass


@pytest.fixture
def client(preparar_banco_de_testes: None, emails: list[dict[str, str | None]]) -> TestClient:
    """Um banco vazio por teste; o lifespan recria as contas iniciais."""
    with engine.begin() as conexao:
        conexao.execute(text(f"TRUNCATE TABLE {TABELAS_DE_TESTE} RESTART IDENTITY CASCADE"))
    from app.core.cache import cache

    cache.invalidar()  # o banco foi zerado: nada do teste anterior pode vir do cache
    with TestClient(app, raise_server_exceptions=False) as cliente:
        yield cliente


@pytest.fixture
def criar_usuario() -> Callable[..., object]:
    """Cria uma conta de apoio sem passar pelo endpoint nem gerar e-mail."""
    from app.core.database import FabricaSessao
    from app.core.seguranca import gerar_hash_senha
    from app.entities.usuario import Usuario

    def criar(
        email: str,
        *,
        perfil: str = "usuario",
        senha: str = "senha123",
        ativo: bool = True,
        nome: str = "Pessoa de Teste",
        email_verificado: bool = True,
    ) -> Usuario:
        with FabricaSessao() as sessao:
            usuario = Usuario(
                nome=nome,
                email=email,
                senha_hash=gerar_hash_senha(senha),
                tipo_usuario=perfil,
                ativo=ativo,
                email_verificado_em=datetime.now(timezone.utc) if email_verificado else None,
            )
            sessao.add(usuario)
            sessao.commit()
            sessao.refresh(usuario)
            sessao.expunge(usuario)
            return usuario

    return criar


def token_de(client: TestClient, email: str, senha: str = "123456") -> str:
    resposta = client.post("/auth/login", json={"email": email, "senha": senha})
    assert resposta.status_code == 200, resposta.text
    return resposta.json()["token"]


@pytest.fixture
def token_admin(client: TestClient) -> str:
    return token_de(client, "admin@unifor.br")
