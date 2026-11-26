"""Controllers: recebem a requisição HTTP, chamam o service e devolvem o DTO."""

from app.controllers import (
    area_campus_controller,
    arquivo_controller,
    auditoria_controller,
    auth_controller,
    notificacao_controller,
    ocorrencia_controller,
    perfil_controller,
    privacidade_controller,
    relatorio_controller,
    saude_controller,
    tempo_real_controller,
    usuario_controller,
)


routers = [
    auth_controller.router,
    # Antes de usuario_controller: GET /usuarios/pedidos-exclusao não pode ser capturada por /usuarios/{id}.
    privacidade_controller.router,
    perfil_controller.router,
    usuario_controller.router,
    area_campus_controller.router,
    ocorrencia_controller.router,
    relatorio_controller.router,
    notificacao_controller.router,
    arquivo_controller.router,
    auditoria_controller.router,
    tempo_real_controller.router,
    saude_controller.router,
]
