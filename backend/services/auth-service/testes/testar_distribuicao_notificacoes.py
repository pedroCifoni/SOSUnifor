"""Teste HTTP isolado da distribuição de SOS e encaminhamento técnico.

Inicie a API usando um banco temporário na porta 8002 antes de executar este arquivo.
"""

import json
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen


BASE_URL = "http://127.0.0.1:8002"
SENHA_TESTE = "123456"


def requisitar(caminho: str, metodo: str = "GET", dados: dict | None = None, token: str | None = None):
    corpo = json.dumps(dados).encode("utf-8") if dados is not None else None
    cabecalhos = {"Content-Type": "application/json"} if corpo is not None else {}
    if token:
        cabecalhos["Authorization"] = f"Bearer {token}"
    requisicao = Request(f"{BASE_URL}{caminho}", data=corpo, headers=cabecalhos, method=metodo)
    try:
        with urlopen(requisicao, timeout=5) as resposta:
            conteudo = resposta.read().decode("utf-8")
            return json.loads(conteudo) if conteudo else None
    except HTTPError as erro:
        detalhe = erro.read().decode("utf-8")
        raise AssertionError(f"{metodo} {caminho} retornou {erro.code}: {detalhe}") from erro


def entrar(email: str) -> str:
    resposta = requisitar("/auth/login", "POST", {"email": email, "senha": SENHA_TESTE})
    return resposta["token"]


def notificacoes_da_ocorrencia(token: str, ocorrencia_id: str, tipo: str) -> list[dict]:
    notificacoes = requisitar("/notificacoes", token=token)
    return [
        notificacao
        for notificacao in notificacoes
        if notificacao["ocorrenciaId"] == ocorrencia_id and notificacao["tipo"] == tipo
    ]


def testar_distribuicao() -> None:
    token_admin = entrar("admin@unifor.br")
    token_autor = entrar("eduardo.costa@unifor.br")
    token_seguranca = entrar("seguranca@unifor.br")
    token_tecnico = entrar("tecnico@unifor.br")
    requisitar(
        "/usuarios",
        "POST",
        {
            "nome": "Usuária conectada",
            "email": "conectada.teste@unifor.br",
            "perfil": "usuario",
            "senha": SENHA_TESTE,
        },
        token_admin,
    )
    token_usuario_conectado = entrar("conectada.teste@unifor.br")

    # A consulta autenticada marca as duas abas de usuário como ativas.
    requisitar("/notificacoes", token=token_autor)
    requisitar("/notificacoes", token=token_usuario_conectado)
    ocorrencia = requisitar(
        "/ocorrencias",
        "POST",
        {
            "titulo": "Teste de zona vermelha",
            "descricao": "Validação isolada",
            "local": "Bloco A",
            "tipo": "sos",
            "anonima": False,
            "anexos": [],
        },
        token_autor,
    )
    ocorrencia_id = ocorrencia["id"]

    assert len(notificacoes_da_ocorrencia(token_admin, ocorrencia_id, "criada")) == 1
    assert len(notificacoes_da_ocorrencia(token_usuario_conectado, ocorrencia_id, "alerta")) == 1
    assert len(notificacoes_da_ocorrencia(token_autor, ocorrencia_id, "alerta")) == 0
    assert len(notificacoes_da_ocorrencia(token_seguranca, ocorrencia_id, "criada")) == 0

    seguranca = requisitar("/usuarios/segurancas", token=token_admin)[0]
    requisitar(
        f"/ocorrencias/{ocorrencia_id}/encaminhar",
        "PATCH",
        {"responsavelId": seguranca["id"]},
        token_admin,
    )
    assert len(notificacoes_da_ocorrencia(token_seguranca, ocorrencia_id, "encaminhada")) == 1

    chamado_tecnico = requisitar(
        "/ocorrencias",
        "POST",
        {
            "titulo": "Projetor sem imagem",
            "descricao": "O projetor do laboratório não exibe imagem.",
            "local": "Bloco D - Laboratório 02",
            "tipo": "manutencao",
            "anonima": False,
            "anexos": [],
        },
        token_autor,
    )
    chamado_tecnico_id = chamado_tecnico["id"]
    assert len(notificacoes_da_ocorrencia(token_admin, chamado_tecnico_id, "criada")) == 1
    assert len(notificacoes_da_ocorrencia(token_usuario_conectado, chamado_tecnico_id, "alerta")) == 0
    assert len(notificacoes_da_ocorrencia(token_tecnico, chamado_tecnico_id, "criada")) == 0

    try:
        requisitar(
            f"/ocorrencias/{chamado_tecnico_id}/encaminhar",
            "PATCH",
            {"responsavelId": seguranca["id"]},
            token_admin,
        )
        raise AssertionError("Um chamado técnico não pode ser encaminhado para segurança.")
    except AssertionError as erro:
        assert "Responsável técnico inválido" in str(erro), erro

    tecnico = requisitar("/usuarios/tecnicos", token=token_admin)[0]
    requisitar(
        f"/ocorrencias/{chamado_tecnico_id}/encaminhar",
        "PATCH",
        {"responsavelId": tecnico["id"]},
        token_admin,
    )
    assert len(notificacoes_da_ocorrencia(token_tecnico, chamado_tecnico_id, "encaminhada")) == 1
    chamados_do_tecnico = requisitar("/ocorrencias", token=token_tecnico)
    assert any(chamado["id"] == chamado_tecnico_id for chamado in chamados_do_tecnico)


if __name__ == "__main__":
    try:
        testar_distribuicao()
    except (AssertionError, OSError) as erro:
        print(f"REGRA_NOTIFICACOES=FALHOU: {erro}")
        sys.exit(1)
    print("REGRA_NOTIFICACOES=OK")
