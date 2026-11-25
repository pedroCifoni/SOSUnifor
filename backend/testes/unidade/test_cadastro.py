"""Autocadastro (POST /auth/cadastro): só e-mail @unifor.br, perfil sempre "usuario", sem revelar contas."""

import json
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import FabricaSessao
from app.core.privacidade import VERSAO_TERMOS
from app.entities.registro_auditoria import RegistroAuditoria
from app.entities.usuario import Usuario
from app.services.verificacao_email_service import LIMITE_ENVIOS_VERIFICACAO


def _cadastrar(client: TestClient, email: str = "nova.pessoa@unifor.br", senha: str = "senha-forte-1", **extras):
    dados = {"nome": "Nova Pessoa", "email": email, "senha": senha, "versao_termos": VERSAO_TERMOS, **extras}
    return client.post("/auth/cadastro", json=dados)


def _token_do_email(mensagem: dict) -> str:
    achado = re.search(r"verificar-email\?token=([A-Za-z0-9_-]+)", mensagem["texto"] or "")
    assert achado, mensagem["texto"]
    return achado.group(1)


def _confirmar(client: TestClient, token: str, senha: str):
    return client.post("/auth/verificar-email", json={"token": token, "senha": senha})


def _login(client: TestClient, email: str, senha: str):
    return client.post("/auth/login", json={"email": email, "senha": senha})


def _conta(email: str) -> Usuario | None:
    with FabricaSessao() as sessao:
        return sessao.scalar(select(Usuario).where(Usuario.email == email))


def test_cadastro_cria_conta_de_usuario_pendente_e_envia_link(client: TestClient, emails) -> None:
    resposta = _cadastrar(client, email="  Nova.Pessoa@UNIFOR.BR ", nome="  Nova   Pessoa ")
    assert resposta.status_code == 202, resposta.text

    conta = _conta("nova.pessoa@unifor.br")
    assert conta is not None
    assert conta.nome == "Nova Pessoa"
    assert conta.tipo_usuario == "usuario"
    assert conta.ativo is True
    assert conta.email_verificado_em is None
    assert conta.senha_hash != "senha-forte-1"
    # A ciência da Política de Privacidade fica registrada no próprio cadastro.
    assert conta.termos_versao == VERSAO_TERMOS and conta.termos_aceitos_em is not None

    assert [m["destinatario"] for m in emails] == ["nova.pessoa@unifor.br"]
    assert "senha-forte-1" not in (emails[0]["texto"] or "") + (emails[0]["html"] or "")

    # Só entra depois de confirmar (link + senha).
    assert _login(client, "nova.pessoa@unifor.br", "senha-forte-1").status_code == 403
    assert _confirmar(client, _token_do_email(emails[0]), "senha-forte-1").status_code == 200
    assert _login(client, "nova.pessoa@unifor.br", "senha-forte-1").status_code == 200


@pytest.mark.parametrize(
    "email",
    [
        "pessoa@gmail.com",
        "pessoa@aluno.unifor.br",  # subdomínio
        "pessoa@unifor.br.com",
        "pessoa@unifor.com.br",
        "pessoa@unifor.br.",
        "pessoa@xunifor.br",
        "pessoa@unifor.br@gmail.com",
        ".pessoa@unifor.br",
        "pessoa.@unifor.br",
        "pe..ssoa@unifor.br",
        "pe ssoa@unifor.br",
        "@unifor.br",
    ],
)
def test_so_aceita_email_exatamente_do_dominio_unifor(client: TestClient, emails, email: str) -> None:
    resposta = _cadastrar(client, email=email)
    assert resposta.status_code == 422, resposta.text
    assert emails == []
    with FabricaSessao() as sessao:
        assert sessao.scalar(select(Usuario).where(Usuario.nome == "Nova Pessoa")) is None


def test_mensagem_de_dominio_errado_orienta_o_usuario(client: TestClient) -> None:
    resposta = _cadastrar(client, email="pessoa@gmail.com")
    assert "@unifor.br" in json.dumps(resposta.json(), ensure_ascii=False)


@pytest.mark.parametrize(
    "campos",
    [
        {"perfil": "admin"},
        {"tipo_usuario": "admin"},
        {"ativo": False},
        {"email_verificado_em": "2026-01-01T00:00:00Z"},
    ],
)
def test_nao_aceita_campos_alem_do_formulario(client: TestClient, emails, campos: dict) -> None:
    """Ninguém escolhe o próprio perfil nem pula a confirmação: campos extras são recusados."""
    assert _cadastrar(client, **campos).status_code == 422
    assert _conta("nova.pessoa@unifor.br") is None
    assert emails == []


@pytest.mark.parametrize(
    ("campos", "motivo"),
    [
        ({"senha": "curta12"}, "senha com menos de 8 caracteres"),
        ({"senha": " " * 10}, "senha só com espaços"),
        ({"senha": "nova.pessoa"}, "senha igual ao começo do e-mail"),
        ({"senha": "Nova.Pessoa@unifor.br"}, "senha igual ao e-mail"),
        ({"senha": "x" * 101}, "senha acima do máximo do login"),
        ({"nome": "ab"}, "nome curto demais"),
        ({"nome": "12345"}, "nome sem letras"),
    ],
)
def test_validacoes_de_nome_e_senha(client: TestClient, emails, campos: dict, motivo: str) -> None:
    resposta = _cadastrar(client, **campos)
    assert resposta.status_code == 422, motivo
    assert emails == []


def test_versao_dos_termos_precisa_ser_a_vigente(client: TestClient, emails) -> None:
    resposta = _cadastrar(client, versao_termos="1999-01")
    assert resposta.status_code == 400
    assert "Política de Privacidade" in resposta.json()["detail"]
    assert _conta("nova.pessoa@unifor.br") is None
    assert emails == []


def test_email_ja_confirmado_recebe_a_mesma_resposta_e_nada_muda(client: TestClient, criar_usuario, emails) -> None:
    criar_usuario("existente@unifor.br", senha="senha-antiga-1", nome="Pessoa Existente")
    nova = _cadastrar(client, email="nova.pessoa@unifor.br")
    repetida = _cadastrar(client, email="existente@unifor.br", senha="senha-do-invasor")

    # Mesma resposta: a tela não revela que o e-mail já tem conta.
    assert (repetida.status_code, repetida.json()) == (nova.status_code, nova.json())
    assert [m["destinatario"] for m in emails] == ["nova.pessoa@unifor.br"]
    assert _login(client, "existente@unifor.br", "senha-antiga-1").status_code == 200
    assert _login(client, "existente@unifor.br", "senha-do-invasor").status_code == 401
    assert _conta("existente@unifor.br").nome == "Pessoa Existente"


def test_conta_desativada_nao_e_recriada(client: TestClient, criar_usuario, emails) -> None:
    criar_usuario("desativada@unifor.br", senha="senha-antiga-1", ativo=False)
    resposta = _cadastrar(client, email="desativada@unifor.br")
    assert resposta.status_code == 202
    assert emails == []
    assert _conta("desativada@unifor.br").ativo is False


def test_pre_sequestro_de_conta_nao_funciona(client: TestClient, emails) -> None:
    """Alguém cadastra o e-mail de outra pessoa com uma senha sua e espera a vítima confirmar."""
    _cadastrar(client, senha="senha-do-invasor")
    link_do_invasor = _token_do_email(emails[-1])  # chega na caixa da vítima, não do invasor

    # Sem a senha da conta, o link sozinho não ativa nada.
    assert _confirmar(client, link_do_invasor, "senha-da-vitima").json()["codigo"] == "senha_nao_confere"

    # A vítima se cadastra: substitui a senha e recebe um link novo; o anterior deixa de valer.
    _cadastrar(client, senha="senha-da-vitima")
    link_da_vitima = _token_do_email(emails[-1])
    assert _confirmar(client, link_do_invasor, "senha-do-invasor").status_code == 400
    assert _confirmar(client, link_da_vitima, "senha-do-invasor").status_code == 400
    assert _confirmar(client, link_da_vitima, "senha-da-vitima").status_code == 200

    assert _login(client, "nova.pessoa@unifor.br", "senha-da-vitima").status_code == 200
    assert _login(client, "nova.pessoa@unifor.br", "senha-do-invasor").status_code == 401


def test_recadastro_de_conta_pendente_respeita_o_limite_de_envios(client: TestClient, emails) -> None:
    for indice in range(LIMITE_ENVIOS_VERIFICACAO):
        _cadastrar(client, senha=f"senha-tentativa-{indice}")
    assert len(emails) == LIMITE_ENVIOS_VERIFICACAO

    # Passou do limite: mesma resposta, nada é enviado e a senha não é trocada.
    excedente = _cadastrar(client, senha="senha-excedente")
    assert excedente.status_code == 202
    assert len(emails) == LIMITE_ENVIOS_VERIFICACAO
    ultima = f"senha-tentativa-{LIMITE_ENVIOS_VERIFICACAO - 1}"
    assert _confirmar(client, _token_do_email(emails[-1]), "senha-excedente").status_code == 400
    assert _confirmar(client, _token_do_email(emails[-1]), ultima).status_code == 200


def test_cadastro_e_auditado_sem_dados_pessoais(client: TestClient, emails) -> None:
    _cadastrar(client, senha="SENHA-NA-TRILHA")
    conta = _conta("nova.pessoa@unifor.br")
    with FabricaSessao() as sessao:
        [registro] = list(
            sessao.scalars(select(RegistroAuditoria).where(RegistroAuditoria.tipo == "auditoria.usuario.cadastrar"))
        )
    assert registro.resultado == "sucesso"
    assert registro.ator_id == conta.id
    assert registro.entidade_id == str(conta.id)
    trilha = json.dumps(registro.dados)
    for dado in ("SENHA-NA-TRILHA", "nova.pessoa@unifor.br", "Nova Pessoa"):
        assert dado not in trilha
