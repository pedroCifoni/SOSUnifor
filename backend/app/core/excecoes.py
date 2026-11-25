"""Erros de negócio, independentes do FastAPI.

Os services lançam estas exceções; o handler registrado em `main.py` as converte
em respostas HTTP no formato `{"detail": "..."}`. Quando o front precisa tratar um caso
específico, a exceção define `codigo`, que vai junto: `{"detail": "...", "codigo": "..."}`.
"""


class ErroAplicacao(Exception):
    status_code = 400
    codigo: str | None = None

    def __init__(self, mensagem: str) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem


class RegraDeNegocioErro(ErroAplicacao):
    status_code = 400


class NaoAutenticadoErro(ErroAplicacao):
    status_code = 401


class AcessoNegadoErro(ErroAplicacao):
    status_code = 403


class EmailNaoVerificadoErro(AcessoNegadoErro):
    """Senha correta, mas a conta ainda não confirmou o e-mail."""

    codigo = "email_nao_verificado"


class SenhaNaoConfereErro(RegraDeNegocioErro):
    """Link de confirmação válido, mas a senha informada não é a da conta."""

    codigo = "senha_nao_confere"


class NaoEncontradoErro(ErroAplicacao):
    status_code = 404


class ConflitoErro(ErroAplicacao):
    status_code = 409


class MuitasTentativasErro(ErroAplicacao):
    status_code = 429


class ArquivoGrandeDemaisErro(ErroAplicacao):
    status_code = 413


class TipoDeArquivoInvalidoErro(ErroAplicacao):
    status_code = 415
