"""Envio de e-mails por SMTP.

Sem `SMTP_HOST` configurado, o e-mail não é enviado: o conteúdo vai para o log da API,
o que basta para desenvolver sem um servidor de e-mail.
"""

import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import configuracoes


logger = logging.getLogger("uvicorn.error")


def enviar_email(destinatario: str, assunto: str, texto: str, html: str | None = None) -> None:
    """Envia um e-mail. Falhas são registradas no log e nunca interrompem quem chamou."""
    mensagem = EmailMessage()
    mensagem["From"] = configuracoes.smtp_remetente
    mensagem["To"] = destinatario
    mensagem["Subject"] = assunto
    mensagem.set_content(texto)
    if html:
        mensagem.add_alternative(html, subtype="html")

    if not configuracoes.smtp_host:
        if configuracoes.ambiente.lower() in {"producao", "production"}:
            # Em produção o conteúdo (senhas, links) nunca vai para o log.
            logger.error("SMTP_HOST não configurado. E-mail '%s' para %s não foi enviado.", assunto, destinatario)
        else:
            logger.warning("SMTP_HOST não configurado. E-mail para %s não enviado:\n%s\n%s", destinatario, assunto, texto)
        return

    try:
        contexto = ssl.create_default_context()
        if configuracoes.smtp_ssl:
            servidor = smtplib.SMTP_SSL(configuracoes.smtp_host, configuracoes.smtp_port, context=contexto, timeout=15)
        else:
            servidor = smtplib.SMTP(configuracoes.smtp_host, configuracoes.smtp_port, timeout=15)
        with servidor:
            if not configuracoes.smtp_ssl and configuracoes.smtp_starttls:
                servidor.starttls(context=contexto)
            if configuracoes.smtp_usuario:
                servidor.login(configuracoes.smtp_usuario, configuracoes.smtp_senha)
            servidor.send_message(mensagem)
        logger.info("E-mail '%s' enviado para %s.", assunto, destinatario)
    except Exception:
        logger.exception("Falha ao enviar o e-mail '%s' para %s.", assunto, destinatario)
