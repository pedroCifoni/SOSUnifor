import pytest

from app.services.geometria import distancia_ate_area, distancia_ate_segmento, ponto_esta_dentro_da_area


QUADRADO = [
    {"latitude": 0.0, "longitude": 0.0},
    {"latitude": 0.0, "longitude": 1.0},
    {"latitude": 1.0, "longitude": 1.0},
    {"latitude": 1.0, "longitude": 0.0},
]
L = [
    {"latitude": 0.0, "longitude": 0.0},
    {"latitude": 0.0, "longitude": 2.0},
    {"latitude": 1.0, "longitude": 2.0},
    {"latitude": 1.0, "longitude": 1.0},
    {"latitude": 2.0, "longitude": 1.0},
    {"latitude": 2.0, "longitude": 0.0},
]


@pytest.mark.parametrize(
    ("latitude", "longitude", "esperado"),
    [(0.5, 0.5, True), (1.5, 0.5, False), (0.0, 0.5, True), (1.0, 1.0, True)],
)
def test_ray_casting_inclui_interior_exterior_e_borda(latitude: float, longitude: float, esperado: bool) -> None:
    assert ponto_esta_dentro_da_area(latitude, longitude, QUADRADO) is esperado


def test_ray_casting_respeita_vazio_do_poligono_concavo_em_l() -> None:
    assert ponto_esta_dentro_da_area(0.5, 1.5, L)
    assert ponto_esta_dentro_da_area(1.5, 0.5, L)
    assert not ponto_esta_dentro_da_area(1.5, 1.5, L)


def test_distancia_ate_segmento_e_area_em_metros() -> None:
    inicio = {"latitude": 0.0, "longitude": 0.0}
    fim = {"latitude": 0.0, "longitude": 1.0}
    assert distancia_ate_segmento(1.0, 0.5, inicio, fim) == pytest.approx(111_320, rel=0.01)
    assert distancia_ate_area(0.5, 0.5, QUADRADO) == 0
    assert distancia_ate_area(1.1, 0.5, QUADRADO) == pytest.approx(11_132, rel=0.02)
