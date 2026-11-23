import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.aspectos import auditar, campos, medir_desempenho, publicar_evento
from app.core.excecoes import AcessoNegadoErro, NaoEncontradoErro, RegraDeNegocioErro
from app.dtos.ocorrencia_dto import (
    CursorPagina,
    EncaminhamentoEntrada,
    OcorrenciaDetalheResposta,
    OcorrenciaEntrada,
    OcorrenciaResposta,
    ResumoOcorrenciasResposta,
    StatusEntrada,
)
from app.entities.ocorrencia import Ocorrencia
from app.entities.usuario import Usuario
from app.repositories.evento_ocorrencia_repository import EventoOcorrenciaRepository
from app.repositories.ocorrencia_repository import OcorrenciaRepository
from app.repositories.usuario_repository import UsuarioRepository
from app.services.area_campus_service import AreaCampusService
from app.services.notificacao_service import AvisarEmTempoReal, NotificacaoService, nao_avisar


# Usuários com acesso nos últimos 30 s recebem o alerta de "zona vermelha" quando alguém aciona um SOS.
JANELA_USUARIO_ONLINE = timedelta(seconds=30)
# Números do protocolo já usados fora da sequência são pulados; acima disso algo está errado.
TENTATIVAS_PROTOCOLO = 50
PERFIS_DE_ATENDIMENTO = {"seguranca", "tecnico"}

# Formato exato dos nomes gerados por ArquivoService.salvar: UUID + extensão permitida.
PADRAO_URL_ANEXO = re.compile(
    r"/arquivos/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(?:jpg|jpeg|png|webp|mp4))$"
)
# Chamados de manutenção vão para o técnico; SOS e denúncias, para a segurança.
PERFIL_RESPONSAVEL_POR_TIPO = {"manutencao": "tecnico"}
PERFIL_RESPONSAVEL_PADRAO = "seguranca"

TITULO_NOVA_OCORRENCIA = {"sos": "SOS acionado", "manutencao": "Novo chamado de manutenção", "denuncia": "Nova denúncia"}
DESCRICAO_DO_STATUS = {
    "em_atendimento": "Atendimento aceito pela equipe responsável.",
    "concluido": "Atendimento concluído.",
    "cancelado": "SOS cancelado pelo solicitante.",
    "aguardando_aceite": "Ocorrência aguardando aceite da equipe.",
    "pendente": "Ocorrência retornou para a fila de triagem.",
}


class OcorrenciaService:
    def __init__(self, sessao: Session, avisar: AvisarEmTempoReal = nao_avisar) -> None:
        self.sessao = sessao
        self.ocorrencias = OcorrenciaRepository(sessao)
        self.eventos = EventoOcorrenciaRepository(sessao)
        self.usuarios = UsuarioRepository(sessao)
        self.areas = AreaCampusService(sessao)
        self.notificacoes = NotificacaoService(sessao)
        self.avisar = avisar

    # ---------- consultas ----------
    @medir_desempenho(limite_ms=300)  # listagem é o caminho mais usado: limite mais apertado que o padrão
    def listar(
        self,
        usuario: Usuario,
        cursor: CursorPagina | None = None,
        limite: int = 50,
        status: str | None = None,
        tipo: str | None = None,
    ) -> list[OcorrenciaResposta]:
        """Usuário vê as próprias; segurança/técnico veem as encaminhadas a eles; admin vê todas."""
        cursor = cursor or CursorPagina()
        linhas = self.ocorrencias.listar_com_nome_do_autor(
            **self._filtro_de_visibilidade(usuario),
            status=status,
            tipo=tipo,
            antes_de=cursor.antes_de,
            antes_id=cursor.antes_id,
            limite=limite,
        )
        return [OcorrenciaResposta.de_entidade(ocorrencia, self._solicitante(ocorrencia, nome)) for ocorrencia, nome in linhas]

    def resumir(self, usuario: Usuario) -> ResumoOcorrenciasResposta:
        """Totais por status e por tipo, contados no banco com a mesma regra de visibilidade da listagem."""
        return ResumoOcorrenciasResposta.de_contagens(
            self.ocorrencias.contar_por_status_e_tipo(**self._filtro_de_visibilidade(usuario))
        )

    @staticmethod
    def _filtro_de_visibilidade(usuario: Usuario) -> dict[str, UUID]:
        if usuario.tipo_usuario == "usuario":
            return {"autor_id": usuario.id}
        if usuario.tipo_usuario in PERFIS_DE_ATENDIMENTO:
            return {"responsavel_id": usuario.id}
        return {}

    def detalhar(self, ocorrencia_id: UUID, usuario: Usuario) -> OcorrenciaDetalheResposta:
        ocorrencia = self.buscar_acessivel(ocorrencia_id, usuario)
        return OcorrenciaDetalheResposta.de_entidade_com_eventos(
            ocorrencia, self._solicitante_do_banco(ocorrencia), self.eventos.listar_da_ocorrencia(ocorrencia.id)
        )

    def buscar_acessivel(self, ocorrencia_id: UUID, usuario: Usuario) -> Ocorrencia:
        ocorrencia = self.ocorrencias.buscar_por_id(ocorrencia_id)
        if ocorrencia is None:
            raise NaoEncontradoErro("Ocorrência não encontrada.")
        if not self.pode_acessar(ocorrencia, usuario):
            raise AcessoNegadoErro("Você não pode acessar esta ocorrência.")
        return ocorrencia

    @staticmethod
    def pode_acessar(ocorrencia: Ocorrencia, usuario: Usuario) -> bool:
        return usuario.tipo_usuario == "admin" or usuario.id in {ocorrencia.autor_id, ocorrencia.responsavel_id}

    # ---------- abertura ----------
    @auditar(
        "ocorrencia.criar",
        entidade="ocorrencia",
        entidade_id="resultado.id",
        ator="autor.id",
        anonimo_se="dados.anonima",
        detalhes=campos(tipo="dados.tipo", protocolo="resultado.protocolo", anonima="dados.anonima"),
    )
    @publicar_evento(
        "ocorrencia.criada",
        entidade="ocorrencia",
        entidade_id="resultado.id",
        ator="autor.id",
        anonimo_se="dados.anonima",
        dados=campos(tipo_ocorrencia="dados.tipo", protocolo="resultado.protocolo", status="resultado.status"),
    )
    def criar(self, dados: OcorrenciaEntrada, autor: Usuario) -> OcorrenciaResposta:
        if (dados.latitude is None) != (dados.longitude is None):
            raise RegraDeNegocioErro("Envie latitude e longitude juntas.")
        self._validar_anexos(dados)

        ocorrencia = self.ocorrencias.adicionar(
            Ocorrencia(
                protocolo=self._proximo_protocolo(),
                titulo=dados.titulo.strip(),
                descricao=dados.descricao.strip() if dados.descricao else None,
                local=self._definir_local(dados),
                tipo=dados.tipo,
                autor_id=autor.id,
                anonima=dados.anonima,
                anexos=[anexo.model_dump() for anexo in dados.anexos],
                latitude=dados.latitude,
                longitude=dados.longitude,
                precisao_metros=dados.precisao_metros,
            )
        )
        self.eventos.registrar(ocorrencia.id, "criada", "Ocorrência registrada pelo usuário.", autor.id)

        avisados = self.usuarios.ids_ativos_por_perfil("admin")
        mensagem = ocorrencia.local if dados.tipo == "sos" else f"{ocorrencia.titulo} · {ocorrencia.protocolo}"
        self.notificacoes.criar(avisados, "criada", TITULO_NOVA_OCORRENCIA[dados.tipo], mensagem, ocorrencia.id, autor.id)
        if dados.tipo == "sos":
            avisados += self._alertar_usuarios_online(ocorrencia, autor)

        self.sessao.commit()
        self.avisar(avisados)
        self.sessao.refresh(ocorrencia)
        return OcorrenciaResposta.de_entidade(ocorrencia, "Anônimo" if ocorrencia.anonima else autor.nome)

    def _validar_anexos(self, dados: OcorrenciaEntrada) -> None:
        """Só aceita anexos enviados por POST /arquivos e que ainda não pertençam a outra ocorrência.

        O download libera o arquivo a quem pode ver uma ocorrência que o cita. Sem esta regra, alguém
        que soubesse o nome de um arquivo alheio poderia citá-lo na própria ocorrência e baixá-lo.
        """
        for anexo in dados.anexos:
            if not anexo.url:
                continue
            encontrado = PADRAO_URL_ANEXO.search(urlparse(anexo.url).path)
            if encontrado is None:
                raise RegraDeNegocioErro("Anexo inválido. Envie o arquivo novamente.")
            nome = encontrado.group(1)
            sufixo = f"/arquivos/{nome}"
            ja_usado = any(
                isinstance(existente, dict) and urlparse(str(existente.get("url") or "")).path.endswith(sufixo)
                for ocorrencia in self.ocorrencias.listar_que_citam_arquivo(nome)
                for existente in ocorrencia.anexos or []
            )
            if ja_usado:
                raise RegraDeNegocioErro("Anexo inválido. Envie o arquivo novamente.")

    def _definir_local(self, dados: OcorrenciaEntrada) -> str:
        """No SOS o local vem do GPS, identificado pelas áreas do campus; nos demais, do formulário."""
        if dados.tipo != "sos":
            return dados.local.strip()
        if dados.latitude is None or dados.longitude is None:
            return "Localização não obtida"
        localizacao = self.areas.localizar(dados.latitude, dados.longitude)
        if not localizacao.dentro_campus:
            if not self.areas.existe_limite_do_campus():
                raise RegraDeNegocioErro("O limite do campus ainda não foi configurado.")
            raise RegraDeNegocioErro("Você está muito longe do campus para ativar o SOS. Em emergência, ligue para 190.")
        return localizacao.descrever()

    def _alertar_usuarios_online(self, ocorrencia: Ocorrencia, autor: Usuario) -> list[UUID]:
        online = self.usuarios.ids_de_usuarios_online(desde=datetime.now(timezone.utc) - JANELA_USUARIO_ONLINE)
        self.notificacoes.criar(
            online,
            "alerta",
            "Atenção: zona vermelha",
            "Um SOS foi acionado no campus. Mantenha-se atento e evite a área, se possível.",
            ocorrencia.id,
            autor.id,
        )
        return online

    def _proximo_protocolo(self) -> str:
        """Pula números já gravados por fora da sequência (ex.: instância antiga ainda ativa durante um deploy)."""
        ano = datetime.now(timezone.utc).year
        for _ in range(TENTATIVAS_PROTOCOLO):
            protocolo = f"#{ano}-{self.ocorrencias.proximo_numero_protocolo():04d}"
            if not self.ocorrencias.protocolo_existe(protocolo):
                return protocolo
        raise RegraDeNegocioErro("Não foi possível gerar o protocolo. Tente novamente.")

    # ---------- atendimento ----------
    @auditar(
        "ocorrencia.encaminhar",
        entidade="ocorrencia",
        entidade_id="ocorrencia_id",
        ator="administrador.id",
        detalhes=campos(responsavel_id="dados.responsavel_id"),
    )
    @publicar_evento(
        "ocorrencia.encaminhada",
        entidade="ocorrencia",
        entidade_id="ocorrencia_id",
        ator="administrador.id",
        dados=campos(tipo_ocorrencia="resultado.tipo", responsavel_id="resultado.responsavel_id", status="resultado.status"),
    )
    def encaminhar(self, ocorrencia_id: UUID, dados: EncaminhamentoEntrada, administrador: Usuario) -> OcorrenciaResposta:
        """O administrador encaminha manutenção para um técnico e SOS/denúncia para a Equipe de Segurança."""
        ocorrencia = self.ocorrencias.buscar_por_id(ocorrencia_id)
        if ocorrencia is None:
            raise NaoEncontradoErro("Ocorrência não encontrada.")
        try:
            responsavel = self.usuarios.buscar_por_id(UUID(dados.responsavel_id))
        except ValueError:
            responsavel = None
        perfil_esperado = PERFIL_RESPONSAVEL_POR_TIPO.get(ocorrencia.tipo, PERFIL_RESPONSAVEL_PADRAO)
        if responsavel is None or not responsavel.ativo or responsavel.tipo_usuario != perfil_esperado:
            if perfil_esperado == "tecnico":
                raise RegraDeNegocioErro("Chamados de manutenção devem ser encaminhados a um técnico ativo.")
            raise RegraDeNegocioErro("Responsável da segurança inválido.")

        ocorrencia.responsavel_id = responsavel.id
        ocorrencia.status = "aguardando_aceite"
        self.eventos.registrar(
            ocorrencia.id,
            "encaminhada",
            f"Encaminhada para {responsavel.nome}; aguardando aceite do atendimento.",
            administrador.id,
        )
        titulo = (
            "Chamado de manutenção encaminhado para você"
            if ocorrencia.tipo == "manutencao"
            else "Ocorrência encaminhada para você"
        )
        self.notificacoes.criar([responsavel.id], "encaminhada", titulo, f"{ocorrencia.titulo} · {ocorrencia.local}", ocorrencia.id)
        self.notificacoes.criar(
            [ocorrencia.autor_id],
            "encaminhada",
            "Seu chamado foi encaminhado",
            f"{ocorrencia.protocolo} · aguardando aceite da equipe",
            ocorrencia.id,
        )
        self.sessao.commit()
        self.avisar([responsavel.id, ocorrencia.autor_id])
        self.sessao.refresh(ocorrencia)
        return OcorrenciaResposta.de_entidade(ocorrencia, self._solicitante_do_banco(ocorrencia))

    @auditar(
        "ocorrencia.mudar_status",
        entidade="ocorrencia",
        entidade_id="ocorrencia_id",
        ator="usuario.id",
        detalhes=campos(status="dados.status"),
    )
    @publicar_evento(
        "ocorrencia.status_alterado",
        entidade="ocorrencia",
        entidade_id="ocorrencia_id",
        ator="usuario.id",
        dados=campos(tipo_ocorrencia="resultado.tipo", status="resultado.status"),
    )
    def atualizar_status(self, ocorrencia_id: UUID, dados: StatusEntrada, usuario: Usuario) -> OcorrenciaResposta:
        ocorrencia = self.buscar_acessivel(ocorrencia_id, usuario)
        if not self._pode_mudar_status(ocorrencia, usuario, dados.status):
            raise AcessoNegadoErro("Você não pode alterar esta ocorrência.")

        ocorrencia.status = dados.status
        self.eventos.registrar(ocorrencia.id, dados.status, DESCRICAO_DO_STATUS[dados.status], usuario.id)
        avisados: list[UUID] = []
        if dados.status in {"concluido", "cancelado"}:
            avisados = [ocorrencia.autor_id, *self.usuarios.ids_ativos_por_perfil("admin")]
            if dados.status == "cancelado":
                titulo = "SOS cancelado"
            else:
                titulo = "SOS encerrado" if ocorrencia.tipo == "sos" else "Chamado resolvido"
            self.notificacoes.criar(
                avisados, "concluida", titulo, f"{ocorrencia.protocolo} · {ocorrencia.titulo}", ocorrencia.id, usuario.id
            )
        self.sessao.commit()
        if avisados:
            self.avisar(avisados)
        self.sessao.refresh(ocorrencia)
        return OcorrenciaResposta.de_entidade(ocorrencia, self._solicitante_do_banco(ocorrencia))

    @staticmethod
    def _pode_mudar_status(ocorrencia: Ocorrencia, usuario: Usuario, novo_status: str) -> bool:
        """Admin pode tudo; o responsável aceita e conclui; o autor só pode cancelar o próprio SOS."""
        if usuario.tipo_usuario == "admin":
            return True
        if usuario.id == ocorrencia.responsavel_id and novo_status in {"em_atendimento", "concluido"}:
            return True
        return usuario.id == ocorrencia.autor_id and ocorrencia.tipo == "sos" and novo_status == "cancelado"

    # ---------- auxiliares ----------
    @staticmethod
    def _solicitante(ocorrencia: Ocorrencia, nome_do_autor: str | None) -> str:
        if ocorrencia.anonima:
            return "Anônimo"
        return nome_do_autor or "Usuário"

    def _solicitante_do_banco(self, ocorrencia: Ocorrencia) -> str:
        if ocorrencia.anonima:
            return "Anônimo"
        autor = self.usuarios.buscar_por_id(ocorrencia.autor_id)
        return self._solicitante(ocorrencia, autor.nome if autor else None)
