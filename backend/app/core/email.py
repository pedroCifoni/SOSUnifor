"""Envio de e-mails com os padrões Strategy, Adapter e Factory.

- **Strategy**: ``EstrategiaEnvioEmail`` é o contrato comum; cada canal de envio é uma estratégia
  intercambiável, e quem envia (``enviar_email``) não sabe qual está em uso.
- **Adapter**: ``EnvioBrevo`` adapta a API HTTP da Brevo e ``EnvioSmtp`` adapta o ``smtplib`` à
  mesma interface ``enviar(destinatario, assunto, texto, html)``.
- **Factory**: ``criar_estrategia_email`` escolhe a estratégia a partir da configuração:
  - com ``BREVO_API_KEY``, API HTTPS da Brevo (porta 443) — produção no Render, que bloqueia SMTP;
  - senão, com ``SMTP_HOST``, SMTP (Mailpit em desenvolvimento, Gmail etc.);
  - sem nenhum dos dois, ``EnvioSomenteLog``: o e-mail não é enviado (em desenvolvimento vai para o log).
"""

import json
import logging
import smtplib
import ssl
import urllib.error
import urllib.request
from email.message import EmailMessage
from email.utils import parseaddr
from typing import Protocol, runtime_checkable

from app.core.config import Configuracoes, configuracoes


logger = logging.getLogger("uvicorn.error")

URL_API_BREVO = "https://api.brevo.com/v3/smtp/email"


@runtime_checkable
class EstrategiaEnvioEmail(Protocol):
    """Contrato comum (Strategy) de todos os canais de envio."""

    nome: str

    def enviar(self, destinatario: str, assunto: str, texto: str, html: str | None = None) -> None: ...


class EnvioBrevo:
    """Adapter da API transacional da Brevo."""

    nome = "brevo"

    def __init__(self, config: Configuracoes) -> None:
        self.config = config

    def enviar(self, destinatario: str, assunto: str, texto: str, html: str | None = None) -> None:
        nome_remetente, email_remetente = parseaddr(self.config.smtp_remetente)
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
                "api-key": self.config.brevo_api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(requisicao, timeout=15) as resposta:  # noqa: S310 (URL fixa https)
                resposta.read()
        except urllib.error.HTTPError as erro:
            # A Brevo explica o motivo no corpo (ex.: remetente não verificado, chave inválida).
            detalhe = erro.read().decode(errors="replace")[:500] if erro.fp else ""
            raise RuntimeError(f"Brevo recusou o envio (HTTP {erro.code}): {detalhe}") from None


class EnvioSmtp:
    """Adapter do ``smtplib`` (Mailpit, Gmail etc.)."""

    nome = "smtp"

    def __init__(self, config: Configuracoes) -> None:
        self.config = config

    def enviar(self, destinatario: str, assunto: str, texto: str, html: str | None = None) -> None:
        config = self.config
        mensagem = EmailMessage()
        mensagem["From"] = config.smtp_remetente
        mensagem["To"] = destinatario
        mensagem["Subject"] = assunto
        mensagem.set_content(texto)
        if html:
            mensagem.add_alternative(html, subtype="html")

        contexto = ssl.create_default_context()
        if config.smtp_ssl:
            servidor = smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, context=contexto, timeout=15)
        else:
            servidor = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=15)
        with servidor:
            if not config.smtp_ssl and config.smtp_starttls:
                servidor.starttls(context=contexto)
            if config.smtp_usuario:
                servidor.login(config.smtp_usuario, config.smtp_senha)
            servidor.send_message(mensagem)


class EnvioSomenteLog:
    """Estratégia nula: sem canal configurado, apenas registra (sem conteúdo em produção)."""

    nome = "log"

    def __init__(self, config: Configuracoes) -> None:
        self.config = config

    def enviar(self, destinatario: str, assunto: str, texto: str, html: str | None = None) -> None:
        if self.config.ambiente.lower() in {"producao", "production"}:
            # Em produção o conteúdo (senhas, links) nunca vai para o log.
            logger.error(
                "Nenhum envio de e-mail configurado (BREVO_API_KEY ou SMTP_HOST). "
                "E-mail '%s' para %s não foi enviado.", assunto, destinatario,
            )
        else:
            logger.warning("E-mail não configurado. E-mail para %s não enviado:\n%s\n%s", destinatario, assunto, texto)


def criar_estrategia_email(config: Configuracoes = configuracoes) -> EstrategiaEnvioEmail:
    """Factory: escolhe o canal de envio a partir da configuração atual."""
    if config.brevo_api_key:
        return EnvioBrevo(config)
    if config.smtp_host:
        return EnvioSmtp(config)
    return EnvioSomenteLog(config)


def enviar_email(destinatario: str, assunto: str, texto: str, html: str | None = None) -> None:
    """Envia um e-mail. Falhas são registradas no log e nunca interrompem quem chamou."""
    estrategia = criar_estrategia_email()
    try:
        estrategia.enviar(destinatario, assunto, texto, html)
        if not isinstance(estrategia, EnvioSomenteLog):
            logger.info("E-mail '%s' enviado para %s via %s.", assunto, destinatario, estrategia.nome)
    except Exception:
        logger.exception("Falha ao enviar o e-mail '%s' para %s.", assunto, destinatario)
