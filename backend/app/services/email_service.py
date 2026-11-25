"""Conteúdo dos e-mails enviados pelo sistema."""

from collections.abc import Callable
from html import escape

from app.core.config import configuracoes
from app.core.email import enviar_email


# Recebe a função de envio e seus argumentos. Na API, agenda o envio para depois da resposta.
AgendarTarefa = Callable[..., None]


def executar_agora(funcao: Callable[..., None], *argumentos: object) -> None:
    funcao(*argumentos)


def _html(titulo: str, corpo: str) -> str:
    return f"""<!doctype html>
<html lang="pt-BR"><body style="margin:0;background:#f4f6fb;font-family:Arial,Helvetica,sans-serif;color:#1f2937">
<div style="max-width:520px;margin:24px auto;background:#fff;border-radius:6px;padding:32px;border:1px solid #e5e7eb">
<h1 style="margin:0 0 16px;font-size:20px;color:#0b2a6f">{titulo}</h1>
{corpo}
<p style="margin-top:32px;font-size:12px;color:#6b7280">Uni SOS · Universidade de Fortaleza. Este é um e-mail automático, não responda.</p>
</div></body></html>"""


def _link_do_sistema(caminho: str = "") -> str:
    return configuracoes.frontend_url.rstrip("/") + caminho


def _botao(link: str, rotulo: str) -> str:
    return (
        f'<p style="margin:24px 0"><a href="{escape(link)}" style="background:#0b2a6f;color:#fff;text-decoration:none;'
        f'display:inline-block;padding:12px 24px;border-radius:4px;font-weight:bold">{escape(rotulo)}</a></p>'
    )


class EmailService:
    def __init__(self, agendar: AgendarTarefa = executar_agora) -> None:
        self.agendar = agendar

    def enviar_confirmacao_email(self, nome: str, email: str, token: str) -> None:
        """Link de confirmação: conta recém-cadastrada ou reenvio pedido pela pessoa ou pelo admin."""
        link = _link_do_sistema(f"/verificar-email?token={token}")
        horas = configuracoes.verificacao_email_expira_horas
        texto = (
            f"Olá, {nome}!\n\n"
            "Confirme que este e-mail é seu para continuar usando o Uni SOS.\n\n"
            f"Para confirmar, acesse: {link}\n"
            "Ao abrir o link, digite a senha que você escolheu no cadastro.\n\n"
            f"O link vale por {horas} horas e só pode ser usado uma vez.\n"
            "Se você não reconhece esta conta, ignore este e-mail."
        )
        html = _html(
            "Confirme o seu e-mail",
            f"""<p>Olá, {escape(nome)}!</p>
<p>Confirme que este e-mail é seu para continuar usando o Uni SOS.</p>
{_botao(link, "Confirmar e-mail")}
<p>Ao abrir o link, digite a senha que você escolheu no cadastro.</p>
<p style="font-size:13px;color:#6b7280">O link vale por {horas} horas e só pode ser usado uma vez.<br>
Se você não reconhece esta conta, ignore este e-mail.</p>""",
        )
        self.agendar(enviar_email, email, "Confirme o seu e-mail · Uni SOS", texto, html)

    def enviar_redefinicao_senha(self, nome: str, email: str, token: str) -> None:
        link = _link_do_sistema(f"/redefinir-senha?token={token}")
        minutos = configuracoes.redefinicao_senha_expira_minutos
        texto = (
            f"Olá, {nome}!\n\n"
            "Recebemos um pedido para redefinir a senha da sua conta no Uni SOS.\n\n"
            f"Para criar uma nova senha, acesse: {link}\n\n"
            f"O link vale por {minutos} minutos e só pode ser usado uma vez.\n"
            "Se você não fez este pedido, ignore este e-mail: sua senha continua a mesma."
        )
        html = _html(
            "Redefinição de senha",
            f"""<p>Olá, {escape(nome)}!</p>
<p>Recebemos um pedido para redefinir a senha da sua conta no Uni SOS.</p>
<p style="margin:24px 0"><a href="{escape(link)}" style="background:#0b2a6f;color:#fff;text-decoration:none;display:inline-block;padding:12px 24px;border-radius:4px;font-weight:bold">Criar nova senha</a></p>
<p style="font-size:13px;color:#6b7280">O link vale por {minutos} minutos e só pode ser usado uma vez.<br>
Se você não fez este pedido, ignore este e-mail: sua senha continua a mesma.</p>""",
        )
        self.agendar(enviar_email, email, "Redefinição de senha · Uni SOS", texto, html)

    def enviar_aviso_senha_alterada(self, nome: str, email: str) -> None:
        texto = (
            f"Olá, {nome}!\n\n"
            "A senha da sua conta no Uni SOS acabou de ser alterada.\n"
            "Se não foi você, procure o administrador do sistema imediatamente."
        )
        html = _html(
            "Sua senha foi alterada",
            f"""<p>Olá, {escape(nome)}!</p>
<p>A senha da sua conta no Uni SOS acabou de ser alterada.</p>
<p style="font-size:13px;color:#6b7280">Se não foi você, procure o administrador do sistema imediatamente.</p>""",
        )
        self.agendar(enviar_email, email, "Sua senha foi alterada · Uni SOS", texto, html)
