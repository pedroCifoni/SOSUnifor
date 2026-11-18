"""Erros de negócio, independentes do FastAPI.

Os services lançam estas exceções; o handler registrado em `main.py` as converte
em respostas HTTP no formato `{"detail": "..."}`.
"""


class ErroAplicacao(Exception):
    status_code = 400

    def __init__(self, mensagem: str) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem


class RegraDeNegocioErro(ErroAplicacao):
    status_code = 400


class NaoAutenticadoErro(ErroAplicacao):
    status_code = 401


class AcessoNegadoErro(ErroAplicacao):
    status_code = 403


class NaoEncontradoErro(ErroAplicacao):
    status_code = 404


class ConflitoErro(ErroAplicacao):
    status_code = 409


class ArquivoGrandeDemaisErro(ErroAplicacao):
    status_code = 413


class TipoDeArquivoInvalidoErro(ErroAplicacao):
    status_code = 415
