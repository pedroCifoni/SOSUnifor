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


class EmailService:
    def __init__(self, agendar: AgendarTarefa = executar_agora) -> None:
        self.agendar = agendar

    def enviar_boas_vindas(self, nome: str, email: str, senha: str) -> None:
        link = _link_do_sistema("/login")
        texto = (
            f"Olá, {nome}!\n\n"
            "Uma conta foi criada para você no Uni SOS.\n\n"
            f"E-mail de acesso: {email}\n"
            f"Senha: {senha}\n\n"
            f"Acesse em: {link}\n\n"
            "Por segurança, não compartilhe esta senha. Se quiser trocá-la, use a opção "
            "\"Esqueci minha senha\" na tela de login."
        )
        html = _html(
            "Sua conta no Uni SOS foi criada",
            f"""<p>Olá, {escape(nome)}!</p>
<p>Uma conta foi criada para você no Uni SOS. Use os dados abaixo para entrar:</p>
<table style="background:#f4f6fb;border-radius:4px;padding:16px;width:100%;font-size:14px">
<tr><td style="color:#6b7280;padding:4px 0">E-mail</td><td><strong>{escape(email)}</strong></td></tr>
<tr><td style="color:#6b7280;padding:4px 0">Senha</td><td><strong style="font-family:monospace;font-size:16px">{escape(senha)}</strong></td></tr>
</table>
<p style="margin:24px 0"><a href="{escape(link)}" style="background:#0b2a6f;color:#fff;text-decoration:none;display:inline-block;padding:12px 24px;border-radius:4px;font-weight:bold">Acessar o sistema</a></p>
<p style="font-size:13px;color:#6b7280">Por segurança, não compartilhe esta senha. Se quiser trocá-la, use a opção "Esqueci minha senha" na tela de login.</p>""",
        )
        self.agendar(enviar_email, email, "Sua conta no Uni SOS foi criada", texto, html)

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
