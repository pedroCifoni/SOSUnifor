"""Envio de e-mails: API HTTP da Brevo (produção) ou SMTP (desenvolvimento).

- Com `BREVO_API_KEY`, o envio é feito pela API HTTPS da Brevo (porta 443). É o caminho para
  produção no plano gratuito do Render, que bloqueia as portas de SMTP (25, 465 e 587).
- Senão, com `SMTP_HOST`, usa SMTP (Mailpit em desenvolvimento, Gmail etc.).
- Sem nenhum dos dois, o e-mail não é enviado: em desenvolvimento o conteúdo vai para o log.
"""

import json
import logging
import smtplib
import ssl
import urllib.error
import urllib.request
from email.message import EmailMessage
from email.utils import parseaddr

from app.core.config import configuracoes


logger = logging.getLogger("uvicorn.error")

URL_API_BREVO = "https://api.brevo.com/v3/smtp/email"


def _em_producao() -> bool:
    return configuracoes.ambiente.lower() in {"producao", "production"}


def enviar_email(destinatario: str, assunto: str, texto: str, html: str | None = None) -> None:
    """Envia um e-mail. Falhas são registradas no log e nunca interrompem quem chamou."""
    try:
        if configuracoes.brevo_api_key:
            _enviar_pela_brevo(destinatario, assunto, texto, html)
        elif configuracoes.smtp_host:
            _enviar_por_smtp(destinatario, assunto, texto, html)
        else:
            if _em_producao():
                # Em produção o conteúdo (senhas, links) nunca vai para o log.
                logger.error(
                    "Nenhum envio de e-mail configurado (BREVO_API_KEY ou SMTP_HOST). "
                    "E-mail '%s' para %s não foi enviado.", assunto, destinatario,
                )
            else:
                logger.warning("E-mail não configurado. E-mail para %s não enviado:\n%s\n%s", destinatario, assunto, texto)
            return
        logger.info("E-mail '%s' enviado para %s.", assunto, destinatario)
    except Exception:
        logger.exception("Falha ao enviar o e-mail '%s' para %s.", assunto, destinatario)


def _enviar_pela_brevo(destinatario: str, assunto: str, texto: str, html: str | None) -> None:
    nome_remetente, email_remetente = parseaddr(configuracoes.smtp_remetente)
    corpo = {
        "sender": {"name": nome_remetente or "Uni SOS", "email": email_remetente},
        "to": [{"email": destinatario}],
        "subject": assunto,
        "textContent": texto,
    }
    if html:
        corpo["htmlContent"] = html
    requisicao = urllib.request.Request(
        URL_API_BREVO,
        data=json.dumps(corpo).encode(),
        method="POST",
        headers={
            "api-key": configuracoes.brevo_api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(requisicao, timeout=15) as resposta:
            resposta.read()
    except urllib.error.HTTPError as erro:
        # A Brevo explica o motivo no corpo (ex.: remetente não verificado, chave inválida).
        detalhe = erro.read().decode(errors="replace")[:500]
        raise RuntimeError(f"Brevo recusou o envio (HTTP {erro.code}): {detalhe}") from None


def _enviar_por_smtp(destinatario: str, assunto: str, texto: str, html: str | None) -> None:
    mensagem = EmailMessage()
    mensagem["From"] = configuracoes.smtp_remetente
    mensagem["To"] = destinatario
    mensagem["Subject"] = assunto
    mensagem.set_content(texto)
    if html:
        mensagem.add_alternative(html, subtype="html")

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
