"""Importa como rascunho os prédios da UNIFOR já mapeados no OpenStreetMap.

As áreas importadas nunca são marcadas como limite do campus: um administrador
deve revisar e ativar esse limite no painel antes de bloquear SOS externo.

Uso, a partir de backend/services/auth-service:
    python -m scripts.importar_areas_unifor_osm
"""

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import engine
from app.entities.area_campus import AreaCampus


CONSULTA_OVERPASS = """
[out:json];
way["building"]["name"](-3.775,-38.485,-3.763,-38.474);
out tags geom;
"""

NOMES_DA_UNIFOR = {
    "Biblioteca Central",
    "Centro de Convivência",
    "DCE",
    "Refeitório",
    "Reitoria",
    "Academia UNIFOR",
}


def pertence_a_unifor(nome: str) -> bool:
    return nome.startswith("Bloco ") or nome in NOMES_DA_UNIFOR


def definir_tipo_area(nome: str) -> str:
    if nome.startswith("Bloco "):
        return "bloco"
    if nome == "Biblioteca Central":
        return "biblioteca"
    if nome == "Reitoria":
        return "administracao"
    if nome == "DCE":
        return "servico"
    return "area_campus"


def buscar_predios_mapeados() -> list[dict]:
    dados = urlencode({"data": CONSULTA_OVERPASS}).encode("utf-8")
    requisicao = Request(
        "https://overpass-api.de/api/interpreter",
        data=dados,
        headers={"User-Agent": "UniSOS-MapImporter/1.0"},
    )
    with urlopen(requisicao, timeout=60) as resposta:
        return json.loads(resposta.read())["elements"]


def converter_coordenadas(geometria: list[dict]) -> list[dict[str, float]]:
    pontos = [{"latitude": ponto["lat"], "longitude": ponto["lon"]} for ponto in geometria]
    if len(pontos) > 1 and pontos[0] == pontos[-1]:
        return pontos[:-1]
    return pontos


def importar_areas() -> tuple[int, int]:
    elementos = buscar_predios_mapeados()
    adicionadas = 0
    ignoradas = 0
    with Session(engine) as banco:
        nomes_existentes = set(banco.scalars(select(AreaCampus.nome).where(AreaCampus.ativo)).all())
        for elemento in elementos:
            nome = elemento.get("tags", {}).get("name", "").strip()
            coordenadas = converter_coordenadas(elemento.get("geometry", []))
            if not pertence_a_unifor(nome) or nome in nomes_existentes or len(coordenadas) < 3:
                ignoradas += 1
                continue
            banco.add(
                AreaCampus(
                    nome=nome,
                    tipo=definir_tipo_area(nome),
                    coordenadas=coordenadas,
                    limite_campus=False,
                    prioridade=10,
                )
            )
            nomes_existentes.add(nome)
            adicionadas += 1
        banco.commit()
    return adicionadas, ignoradas


if __name__ == "__main__":
    adicionadas, ignoradas = importar_areas()
    print(f"AREAS_IMPORTADAS={adicionadas}; AREAS_IGNORADAS={ignoradas}")
