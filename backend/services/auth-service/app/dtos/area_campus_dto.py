from pydantic import BaseModel, Field

from app.dtos.base import RespostaDTO
from app.entities.area_campus import AreaCampus


# ---------- entrada ----------
class CoordenadasEntrada(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class AreaCampusEntrada(BaseModel):
    nome: str = Field(min_length=2, max_length=160)
    tipo: str = Field(min_length=2, max_length=50)
    coordenadas: list[CoordenadasEntrada] = Field(min_length=3, max_length=200)
    limite_campus: bool = Field(default=False, alias="limiteCampus")
    prioridade: int = Field(default=0, ge=0, le=1000)


# ---------- saída ----------
class AreaCampusResposta(RespostaDTO):
    id: str
    nome: str
    tipo: str
    coordenadas: list[dict[str, float]]
    limite_campus: bool
    prioridade: int

    @classmethod
    def de_entidade(cls, area: AreaCampus) -> "AreaCampusResposta":
        return cls(
            id=str(area.id),
            nome=area.nome,
            tipo=area.tipo,
            coordenadas=area.coordenadas,
            limite_campus=area.limite_campus,
            prioridade=area.prioridade,
        )


class LocalizacaoResposta(RespostaDTO):
    dentro_campus: bool
    area: AreaCampusResposta | None
    bloco_mais_proximo: AreaCampusResposta | None
    local: str
