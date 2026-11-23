from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.excecoes import ConflitoErro
from app.dtos.privacidade_dto import CienciaPrivacidadeEntrada, SituacaoPrivacidadeResposta
from app.entities.usuario import Usuario


# Versão (data) da Política de Privacidade em vigor. Ao mudar o texto da política no front-end
# (src/pages/Privacidade/politicaPrivacidade.ts), atualize as DUAS constantes para a mesma data:
# todos os usuários verão o aviso de novo no próximo acesso.
VERSAO_POLITICA_PRIVACIDADE = "2026-11-23"


class PrivacidadeService:
    """Registro da ciência da Política de Privacidade (transparência — LGPD, arts. 6º, VI, e 9º)."""

    def __init__(self, sessao: Session) -> None:
        self.sessao = sessao

    def situacao(self, usuario: Usuario) -> SituacaoPrivacidadeResposta:
        return SituacaoPrivacidadeResposta(
            versao_vigente=VERSAO_POLITICA_PRIVACIDADE,
            versao_ciente=usuario.politica_privacidade_versao,
            ciente_em=usuario.politica_privacidade_ciente_em,
            pendente=usuario.politica_privacidade_versao != VERSAO_POLITICA_PRIVACIDADE,
        )

    def registrar_ciencia(self, dados: CienciaPrivacidadeEntrada, usuario: Usuario) -> SituacaoPrivacidadeResposta:
        if dados.versao != VERSAO_POLITICA_PRIVACIDADE:
            raise ConflitoErro("A Política de Privacidade foi atualizada. Recarregue a página e leia a versão atual.")
        if usuario.politica_privacidade_versao != VERSAO_POLITICA_PRIVACIDADE:
            usuario.politica_privacidade_versao = VERSAO_POLITICA_PRIVACIDADE
            usuario.politica_privacidade_ciente_em = datetime.now(timezone.utc)
            self.sessao.commit()
        return self.situacao(usuario)
