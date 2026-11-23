"""Direitos do titular (LGPD, art. 18): ciência dos termos, acesso/portabilidade e eliminação.

A eliminação é feita por anonimização: as ocorrências continuam guardadas (registro de segurança
da instituição e cumprimento de obrigação legal, art. 16, I), mas deixam de identificar a pessoa.
"""

import secrets
from collections import defaultdict
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.excecoes import ConflitoErro, NaoEncontradoErro, RegraDeNegocioErro
from app.core.privacidade import DOMINIO_ANONIMIZADO, NOME_ANONIMIZADO, VERSAO_TERMOS
from app.core.seguranca import gerar_hash_senha
from app.dtos.privacidade_dto import (
    AceiteTermosEntrada,
    AnonimizacaoResposta,
    DadosTitularResposta,
    NotificacaoExportada,
    OcorrenciaExportada,
    PedidoExclusaoResposta,
    SolicitacaoExclusaoEntrada,
    SolicitacaoExclusaoResposta,
    TermosResposta,
    TitularExportado,
)
from app.entities.usuario import Usuario
from app.repositories.evento_ocorrencia_repository import EventoOcorrenciaRepository
from app.repositories.notificacao_repository import NotificacaoRepository
from app.repositories.ocorrencia_repository import OcorrenciaRepository
from app.repositories.token_redefinicao_senha_repository import TokenRedefinicaoSenhaRepository
from app.repositories.usuario_repository import UsuarioRepository
from app.services.notificacao_service import AvisarEmTempoReal, NotificacaoService, nao_avisar


CONTROLADOR = "Universidade de Fortaleza (UNIFOR)"
MENSAGEM_PEDIDO_EXCLUSAO = (
    "Pedido registrado. A administração vai analisá-lo e anonimizar seus dados; as ocorrências que você abriu "
    "continuam guardadas como registro de segurança, sem identificar você."
)


def _agora() -> datetime:
    return datetime.now(timezone.utc)


class PrivacidadeService:
    def __init__(self, sessao: Session, avisar: AvisarEmTempoReal = nao_avisar) -> None:
        self.sessao = sessao
        self.usuarios = UsuarioRepository(sessao)
        self.ocorrencias = OcorrenciaRepository(sessao)
        self.eventos = EventoOcorrenciaRepository(sessao)
        self.notificacoes_repo = NotificacaoRepository(sessao)
        self.tokens = TokenRedefinicaoSenhaRepository(sessao)
        self.notificacoes = NotificacaoService(sessao)
        self.avisar = avisar

    # ---------- ciência da Política de Privacidade ----------
    @staticmethod
    def situacao_dos_termos(usuario: Usuario) -> TermosResposta:
        return TermosResposta(
            versao_atual=VERSAO_TERMOS,
            versao_aceita=usuario.termos_versao,
            aceitos_em=usuario.termos_aceitos_em.isoformat() if usuario.termos_aceitos_em else None,
            pendente=usuario.termos_versao != VERSAO_TERMOS,
        )

    def aceitar_termos(self, usuario: Usuario, dados: AceiteTermosEntrada) -> TermosResposta:
        """Só aceita a versão vigente: uma tela antiga em cache não registra ciência de outro texto."""
        if dados.versao != VERSAO_TERMOS:
            raise RegraDeNegocioErro("A Política de Privacidade foi atualizada. Recarregue a página e leia a versão atual.")
        usuario.termos_versao = VERSAO_TERMOS
        usuario.termos_aceitos_em = _agora()
        self.sessao.commit()
        return self.situacao_dos_termos(usuario)

    # ---------- acesso e portabilidade ----------
    def exportar_dados(self, usuario: Usuario) -> DadosTitularResposta:
        """Somente o que se refere ao próprio titular: perfil, ocorrências que ele abriu e notificações recebidas."""
        ocorrencias = self.ocorrencias.listar_do_autor(usuario.id)
        eventos_por_ocorrencia = defaultdict(list)
        for evento in self.eventos.listar_das_ocorrencias([ocorrencia.id for ocorrencia in ocorrencias]):
            eventos_por_ocorrencia[evento.ocorrencia_id].append(evento)
        return DadosTitularResposta(
            gerado_em=_agora().isoformat(),
            controlador=CONTROLADOR,
            versao_termos_atual=VERSAO_TERMOS,
            titular=TitularExportado.de_entidade(usuario),
            ocorrencias=[
                OcorrenciaExportada.de_entidade(ocorrencia, eventos_por_ocorrencia[ocorrencia.id])
                for ocorrencia in ocorrencias
            ],
            notificacoes=[
                NotificacaoExportada.de_entidade(notificacao)
                for notificacao in self.notificacoes_repo.listar_todas_do_destinatario(usuario.id)
            ],
        )

    # ---------- eliminação ----------
    def solicitar_exclusao(self, usuario: Usuario, dados: SolicitacaoExclusaoEntrada) -> SolicitacaoExclusaoResposta:
        if not dados.confirmar:
            raise RegraDeNegocioErro("Confirme o pedido de exclusão dos seus dados.")
        if usuario.exclusao_solicitada_em is not None:
            # Pedido repetido: mantém a data original e não avisa os administradores de novo.
            return SolicitacaoExclusaoResposta(
                mensagem=MENSAGEM_PEDIDO_EXCLUSAO, solicitada_em=usuario.exclusao_solicitada_em.isoformat()
            )

        usuario.exclusao_solicitada_em = _agora()
        administradores = [
            admin_id for admin_id in self.usuarios.ids_ativos_por_perfil("admin") if admin_id != usuario.id
        ]
        self.notificacoes.criar(
            administradores,
            "privacidade",
            "Pedido de exclusão de dados (LGPD)",
            f"{usuario.nome} pediu a eliminação dos dados pessoais. Veja em Usuários > Pedidos de exclusão.",
            None,
        )
        self.sessao.commit()
        self.avisar(administradores)
        return SolicitacaoExclusaoResposta(
            mensagem=MENSAGEM_PEDIDO_EXCLUSAO, solicitada_em=usuario.exclusao_solicitada_em.isoformat()
        )

    def listar_pedidos_de_exclusao(self) -> list[PedidoExclusaoResposta]:
        return [PedidoExclusaoResposta.de_entidade(usuario) for usuario in self.usuarios.listar_com_exclusao_pendente()]

    def anonimizar(self, usuario_id: UUID, administrador: Usuario) -> AnonimizacaoResposta:
        """Troca nome e e-mail por valores sem volta, invalida a senha e desativa a conta.

        As ocorrências e seus eventos são mantidos; o autor passa a aparecer como "Titular anonimizado".
        """
        if usuario_id == administrador.id:
            raise RegraDeNegocioErro("Você não pode anonimizar a sua própria conta.")
        usuario = self.usuarios.buscar_por_id(usuario_id)
        if usuario is None:
            raise NaoEncontradoErro("Usuário não encontrado.")
        if usuario.anonimizado_em is not None:
            raise ConflitoErro("Esta conta já foi anonimizada.")
        if usuario.tipo_usuario == "admin" and usuario.ativo and self.usuarios.contar_ativos_por_perfil("admin") <= 1:
            raise RegraDeNegocioErro("Deve existir ao menos um administrador.")

        nome_original = usuario.nome
        usuario.nome = NOME_ANONIMIZADO
        usuario.email = f"anonimizado-{uuid4()}@{DOMINIO_ANONIMIZADO}"
        usuario.matricula = None
        # Hash de uma senha aleatória que ninguém conhece (e que é descartada): nenhuma senha volta a conferir.
        usuario.senha_hash = gerar_hash_senha(secrets.token_urlsafe(32))
        usuario.ativo = False
        usuario.ultimo_acesso = None
        usuario.anonimizado_em = _agora()
        if usuario.exclusao_solicitada_em is None:
            usuario.exclusao_solicitada_em = usuario.anonimizado_em

        # Eventos guardam o nome de quem recebeu o encaminhamento ("Encaminhada para Fulano; ...").
        self.eventos.substituir_nas_descricoes(f"para {nome_original};", f"para {NOME_ANONIMIZADO};")
        self.notificacoes_repo.apagar_do_destinatario(usuario.id)
        self.tokens.apagar_do_usuario(usuario.id)
        self.sessao.commit()
        return AnonimizacaoResposta(
            id=str(usuario.id), nome=usuario.nome, anonimizado_em=usuario.anonimizado_em.isoformat()
        )
