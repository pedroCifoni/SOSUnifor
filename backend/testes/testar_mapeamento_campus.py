"""Teste HTTP isolado do cadastro de áreas e da identificação do SOS."""

import json
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen


BASE_URL = "http://127.0.0.1:8003"


def requisitar(caminho: str, metodo: str = "GET", dados: dict | None = None, token: str | None = None):
    corpo = json.dumps(dados).encode("utf-8") if dados is not None else None
    cabecalhos = {"Content-Type": "application/json"} if corpo is not None else {}
    if token:
        cabecalhos["Authorization"] = f"Bearer {token}"
    requisicao = Request(f"{BASE_URL}{caminho}", data=corpo, headers=cabecalhos, method=metodo)
    try:
        with urlopen(requisicao, timeout=5) as resposta:
            conteudo = resposta.read().decode("utf-8")
            return resposta.status, json.loads(conteudo) if conteudo else None
    except HTTPError as erro:
        conteudo = erro.read().decode("utf-8")
        return erro.code, json.loads(conteudo) if conteudo else None


def entrar(email: str) -> str:
    status, resposta = requisitar("/auth/login", "POST", {"email": email, "senha": "123456"})
    assert status == 200, resposta
    return resposta["token"]


def salvar_area(
    token: str, nome: str, limite_campus: bool, coordenadas: list[tuple[float, float]], tipo: str = "bloco"
) -> None:
    status, resposta = requisitar(
        "/areas-campus",
        "POST",
        {
            "nome": nome,
            "tipo": "limite" if limite_campus else tipo,
            "limiteCampus": limite_campus,
            "prioridade": 10,
            "coordenadas": [{"latitude": latitude, "longitude": longitude} for latitude, longitude in coordenadas],
        },
        token,
    )
    assert status == 201, resposta


def testar_mapeamento() -> None:
    token_admin = entrar("admin@unifor.br")
    token_usuario = entrar("eduardo.costa@unifor.br")
    salvar_area(token_admin, "Campus de teste", True, [(0, 0), (0, 10), (10, 10), (10, 0)])
    salvar_area(token_admin, "Bloco D", False, [(2, 2), (2, 4), (4, 4), (4, 2)])
    salvar_area(token_admin, "Praça verde", False, [(6, 2), (6, 4), (8, 4), (8, 2)], "area_verde")

    status, localizacao = requisitar("/areas-campus/identificar", "POST", {"latitude": 3, "longitude": 3}, token_usuario)
    assert status == 200 and localizacao["dentroCampus"] is True and localizacao["local"] == "Bloco D", localizacao

    status, localizacao = requisitar("/areas-campus/identificar", "POST", {"latitude": 7, "longitude": 3}, token_usuario)
    assert status == 200 and localizacao["local"] == "Praça verde · próximo ao Bloco D", localizacao

    status, localizacao = requisitar("/areas-campus/identificar", "POST", {"latitude": 4.5, "longitude": 3}, token_usuario)
    assert status == 200 and localizacao["local"] == "Próximo ao Bloco D", localizacao

    status, localizacao = requisitar("/areas-campus/identificar", "POST", {"latitude": 0, "longitude": 5}, token_usuario)
    assert status == 200 and localizacao["dentroCampus"] is True, localizacao

    status, localizacao = requisitar("/areas-campus/identificar", "POST", {"latitude": 12, "longitude": 12}, token_usuario)
    assert status == 200 and localizacao["dentroCampus"] is False, localizacao

    status, ocorrencia = requisitar(
        "/ocorrencias",
        "POST",
        {"titulo": "SOS de teste", "local": "não confiar", "tipo": "sos", "latitude": 3, "longitude": 3, "precisaoMetros": 8},
        token_usuario,
    )
    assert status == 201 and ocorrencia["local"] == "Bloco D", ocorrencia

    status, erro = requisitar(
        "/ocorrencias",
        "POST",
        {"titulo": "SOS externo", "local": "não confiar", "tipo": "sos", "latitude": 12, "longitude": 12},
        token_usuario,
    )
    assert status == 400 and "muito longe" in erro["detail"], erro


if __name__ == "__main__":
    try:
        testar_mapeamento()
    except (AssertionError, OSError) as erro:
        print(f"MAPEAMENTO_CAMPUS=FALHOU: {erro}")
        sys.exit(1)
    print("MAPEAMENTO_CAMPUS=OK")
