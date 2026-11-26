"""Reação ao evento "usuario.ativado" (padrão Observer sobre o RabbitMQ).

Fluxo: ``VerificacaoEmailService._ativar_conta`` publica "usuario.ativado" (aspecto
``publicar_evento``) → exchange "unisos.eventos" → fila "unisos.reacoes" → ``dar_boas_vindas``.
Sem broker, o mesmo observador é chamado no próprio processo (``eventos.notificar_localmente``).

Idempotente: uma reentrega da mensagem não duplica a notificação nem o e-mail.
"""

import logging
from uuid import UUID

from app.core.database import FabricaSessao
from app.core.eventos import Evento, assinar
from app.repositories.notificacao_repository import NotificacaoRepository
from app.repositories.usuario_repository import UsuarioRepository
from app.services.email_service import EmailService
from app.services.notificacao_service import NotificacaoService


logger = logging.getLogger(__name__)

TIPO_NOTIFICACAO = "boas_vindas"


@assinar("usuario.ativado")
def dar_boas_vindas(evento: Evento) -> None:
    usuario_id = UUID(str(evento.dados.get("entidade_id") or evento.ator_id))
    with FabricaSessao() as sessao:
        usuario = UsuarioRepository(sessao).buscar_por_id(usuario_id)
        if usuario is None or not usuario.ativo:
            return
        if NotificacaoRepository(sessao).existe_do_tipo(usuario.id, TIPO_NOTIFICACAO):
            return  # evento reentregue: já tratado
        NotificacaoService(sessao).criar(
            [usuario.id],
            TIPO_NOTIFICACAO,
            "Bem-vindo(a) ao Uni SOS",
            "Sua conta está ativa. Em uma emergência, segure o botão SOS por 2 segundos.",
            ocorrencia_id=None,
        )
        sessao.commit()
        nome, email = usuario.nome, usuario.email
    EmailService().enviar_boas_vindas(nome, email)
    logger.info("Boas-vindas enviadas para a conta %s (evento %s).", usuario_id, evento.id)
