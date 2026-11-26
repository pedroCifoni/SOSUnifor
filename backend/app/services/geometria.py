"""Cálculos geométricos sobre os polígonos do campus (sem acesso a banco)."""

from math import cos, radians, sqrt


Coordenada = dict[str, float]


def ponto_esta_dentro_da_area(latitude: float, longitude: float, coordenadas: list[Coordenada]) -> bool:
    """Ray casting. Pontos exatamente sobre a borda contam como dentro."""
    dentro = False
    quantidade_pontos = len(coordenadas)
    for indice_atual in range(quantidade_pontos):
        ponto_atual = coordenadas[indice_atual]
        ponto_anterior = coordenadas[(indice_atual - 1) % quantidade_pontos]
        latitude_atual, longitude_atual = ponto_atual["latitude"], ponto_atual["longitude"]
        latitude_anterior, longitude_anterior = ponto_anterior["latitude"], ponto_anterior["longitude"]

        produto_vetorial = (longitude - longitude_anterior) * (latitude_atual - latitude_anterior) - (
            latitude - latitude_anterior
        ) * (longitude_atual - longitude_anterior)
        esta_na_linha = abs(produto_vetorial) < 0.0000000001
        dentro_dos_extremos = (
            min(latitude_anterior, latitude_atual) <= latitude <= max(latitude_anterior, latitude_atual)
            and min(longitude_anterior, longitude_atual) <= longitude <= max(longitude_anterior, longitude_atual)
        )
        if esta_na_linha and dentro_dos_extremos:
            return True

        if (latitude_atual > latitude) == (latitude_anterior > latitude):
            continue
        longitude_no_cruzamento = (longitude_anterior - longitude_atual) * (latitude - latitude_atual) / (
            latitude_anterior - latitude_atual
        ) + longitude_atual
        if longitude < longitude_no_cruzamento:
            dentro = not dentro
    return dentro


def distancia_ate_segmento(latitude: float, longitude: float, inicio: Coordenada, fim: Coordenada) -> float:
    """Menor distância, em metros, entre um ponto e uma lateral do polígono."""
    metros_por_grau_latitude = 111_320
    metros_por_grau_longitude = 111_320 * cos(radians(latitude))
    inicio_x = (inicio["longitude"] - longitude) * metros_por_grau_longitude
    inicio_y = (inicio["latitude"] - latitude) * metros_por_grau_latitude
    fim_x = (fim["longitude"] - longitude) * metros_por_grau_longitude
    fim_y = (fim["latitude"] - latitude) * metros_por_grau_latitude
    vetor_x, vetor_y = fim_x - inicio_x, fim_y - inicio_y
    tamanho_quadrado = vetor_x**2 + vetor_y**2
    if tamanho_quadrado == 0:
        return sqrt(inicio_x**2 + inicio_y**2)
    proporcao = max(0, min(1, -(inicio_x * vetor_x + inicio_y * vetor_y) / tamanho_quadrado))
    return sqrt((inicio_x + proporcao * vetor_x) ** 2 + (inicio_y + proporcao * vetor_y) ** 2)


def distancia_ate_area(latitude: float, longitude: float, coordenadas: list[Coordenada]) -> float:
    """Zero dentro do polígono; fora dele, a distância até a borda mais próxima."""
    if ponto_esta_dentro_da_area(latitude, longitude, coordenadas):
        return 0
    return min(
        distancia_ate_segmento(latitude, longitude, coordenadas[indice - 1], coordenadas[indice])
        for indice in range(len(coordenadas))
    )
