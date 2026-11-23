"""Política de retenção (LGPD, art. 15 e 16): apaga o que não precisa mais ser guardado.

Executada a cada subida da API (`inicializar_banco`). É idempotente: rodar de novo só apaga
o que tiver vencido desde a última vez. Os prazos ficam em `app/core/config.py`:

- tokens de redefinição de senha: apagados `RETENCAO_TOKENS_VENCIDOS_HORAS` depois de vencerem
  (a folga mantém os pedidos da última hora, usados no limite de pedidos de "esqueci minha senha");
- notificações já lidas: apagadas `RETENCAO_NOTIFICACOES_LIDAS_DIAS` depois de criadas.

Não são apagados: notificações não lidas, ocorrências e seus eventos (registro de segurança da
instituição) e contas de usuário (eliminação é feita por anonimização, a pedido do titular).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import configuracoes
from app.entities.notificacao import Notificacao
from app.entities.token_redefinicao_senha import TokenRedefinicaoSenha


@dataclass(frozen=True)
class ResultadoRetencao:
    tokens_apagados: int
    notificacoes_apagadas: int

    @property
    def total(self) -> int:
        return self.tokens_apagados + self.notificacoes_apagadas


class RetencaoService:
    def __init__(self, sessao: Session) -> None:
        self.sessao = sessao

    def executar(self, agora: datetime | None = None) -> ResultadoRetencao:
        agora = agora or datetime.now(timezone.utc)
        limite_tokens = agora - timedelta(hours=configuracoes.retencao_tokens_vencidos_horas)
        limite_notificacoes = agora - timedelta(days=configuracoes.retencao_notificacoes_lidas_dias)

        tokens = self.sessao.execute(
            delete(TokenRedefinicaoSenha).where(TokenRedefinicaoSenha.expira_em < limite_tokens)
        ).rowcount
        notificacoes = self.sessao.execute(
            delete(Notificacao).where(Notificacao.lida.is_(True), Notificacao.criada_em < limite_notificacoes)
        ).rowcount
        self.sessao.commit()
        return ResultadoRetencao(tokens_apagados=tokens or 0, notificacoes_apagadas=notificacoes or 0)
