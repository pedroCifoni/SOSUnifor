from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.cache import cache
from app.core.excecoes import NaoEncontradoErro
from app.dtos.area_campus_dto import AreaCampusEntrada, AreaCampusResposta, LocalizacaoResposta
from app.entities.area_campus import AreaCampus
from app.repositories.area_campus_repository import AreaCampusRepository
from app.services.geometria import distancia_ate_area, ponto_esta_dentro_da_area


TIPOS_AREA_ABERTA = {"area_verde", "area_externa"}


@dataclass
class Localizacao:
    dentro_campus: bool
    area: AreaCampus | None = None
    bloco_mais_proximo: AreaCampus | None = None

    def descrever(self) -> str:
        """Texto usado como local do SOS, ex.: "Praça Central · próximo ao Bloco C"."""
        if self.area is None:
            if self.bloco_mais_proximo:
                return f"Próximo ao {self.bloco_mais_proximo.nome}"
            return "Área do campus não mapeada"
        if self.area.tipo in TIPOS_AREA_ABERTA and self.bloco_mais_proximo:
            return f"{self.area.nome} · próximo ao {self.bloco_mais_proximo.nome}"
        return self.area.nome


CHAVE_CACHE_AREAS = "areas_campus:"
# Curto de propósito: outra réplica que editou uma área tem a mudança visível aqui em até 60 s.
TTL_CACHE_AREAS_SEGUNDOS = 60


class AreaCampusService:
    def __init__(self, sessao: Session) -> None:
        self.sessao = sessao
        self.areas = AreaCampusRepository(sessao)

    # ---------- cadastro ----------
    def listar(self) -> list[AreaCampusResposta]:
        return [AreaCampusResposta.de_entidade(area) for area in self.areas.listar_para_exibicao()]

    def criar(self, dados: AreaCampusEntrada) -> AreaCampusResposta:
        area = self.areas.adicionar(AreaCampus())
        self._preencher(area, dados)
        self.sessao.commit()
        cache.invalidar(CHAVE_CACHE_AREAS)
        self.sessao.refresh(area)
        return AreaCampusResposta.de_entidade(area)

    def atualizar(self, area_id: UUID, dados: AreaCampusEntrada) -> AreaCampusResposta:
        area = self._buscar(area_id)
        self._preencher(area, dados)
        self.sessao.commit()
        cache.invalidar(CHAVE_CACHE_AREAS)
        self.sessao.refresh(area)
        return AreaCampusResposta.de_entidade(area)

    def excluir(self, area_id: UUID) -> None:
        self._buscar(area_id).ativo = False
        self.sessao.commit()
        cache.invalidar(CHAVE_CACHE_AREAS)

    # ---------- localização ----------
    def identificar(self, latitude: float, longitude: float) -> LocalizacaoResposta:
        localizacao = self.localizar(latitude, longitude)
        return LocalizacaoResposta(
            dentro_campus=localizacao.dentro_campus,
            area=AreaCampusResposta.de_entidade(localizacao.area) if localizacao.area else None,
            bloco_mais_proximo=(
                AreaCampusResposta.de_entidade(localizacao.bloco_mais_proximo)
                if localizacao.bloco_mais_proximo
                else None
            ),
            local=localizacao.descrever() if localizacao.dentro_campus else "Área externa do campus",
        )

    def localizar(self, latitude: float, longitude: float) -> Localizacao:
        """Encontra a área de maior prioridade que contém o ponto e o bloco mais próximo dele."""
        # Caminho crítico do SOS: os polígonos vêm do cache em vez de uma consulta a cada alerta.
        areas = cache.obter_ou_calcular(
            CHAVE_CACHE_AREAS + "por_prioridade",
            TTL_CACHE_AREAS_SEGUNDOS,
            lambda: self.areas.copiar_sem_sessao(self.areas.listar_por_prioridade()),
        )
        limites = [area for area in areas if area.limite_campus]
        dentro_do_campus = any(ponto_esta_dentro_da_area(latitude, longitude, area.coordenadas) for area in limites)
        if not dentro_do_campus:
            return Localizacao(dentro_campus=False)
        area_do_ponto = next(
            (
                area
                for area in areas
                if not area.limite_campus and ponto_esta_dentro_da_area(latitude, longitude, area.coordenadas)
            ),
            None,
        )
        return Localizacao(
            dentro_campus=True,
            area=area_do_ponto,
            bloco_mais_proximo=self._bloco_mais_proximo(areas, latitude, longitude),
        )

    def existe_limite_do_campus(self) -> bool:
        return self.areas.existe_limite_ativo()

    # ---------- auxiliares ----------
    @staticmethod
    def _bloco_mais_proximo(areas: list[AreaCampus], latitude: float, longitude: float) -> AreaCampus | None:
        blocos = [area for area in areas if not area.limite_campus and area.tipo == "bloco"]
        if not blocos:
            return None
        return min(blocos, key=lambda bloco: distancia_ate_area(latitude, longitude, bloco.coordenadas))

    @staticmethod
    def _preencher(area: AreaCampus, dados: AreaCampusEntrada) -> None:
        area.nome = dados.nome.strip()
        area.tipo = dados.tipo.strip()
        area.coordenadas = [ponto.model_dump() for ponto in dados.coordenadas]
        area.limite_campus = dados.limite_campus
        area.prioridade = dados.prioridade

    def _buscar(self, area_id: UUID) -> AreaCampus:
        area = self.areas.buscar_ativa(area_id)
        if area is None:
            raise NaoEncontradoErro("Área não encontrada.")
        return area
