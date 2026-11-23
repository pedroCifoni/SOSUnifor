"""Controllers: recebem a requisição HTTP, chamam o service e devolvem o DTO."""

from app.controllers import (
    area_campus_controller,
    arquivo_controller,
    auth_controller,
    notificacao_controller,
    ocorrencia_controller,
    privacidade_controller,
    saude_controller,
    tempo_real_controller,
    usuario_controller,
)

routers = [
    auth_controller.router,
    usuario_controller.router,
    area_campus_controller.router,
    ocorrencia_controller.router,
    notificacao_controller.router,
    arquivo_controller.router,
    privacidade_controller.router,
    tempo_real_controller.router,
    saude_controller.router,
]
