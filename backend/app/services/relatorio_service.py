"""Geração de relatórios de ocorrências, sem expor dados pessoais desnecessários.

O service só monta o ``DocumentoTabular`` (o quê); a serialização em CSV ou PDF fica com as
estratégias de ``app.core.exportacao`` (como).
"""

from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.core.excecoes import RegraDeNegocioErro
from app.core.exportacao import FUSO_FORTALEZA, DocumentoTabular, ExportadorCsv, ExportadorPdf
from app.entities.ocorrencia import Ocorrencia
from app.repositories.ocorrencia_repository import OcorrenciaRepository


LIMITE_LINHAS_PDF = 5_000
CABECALHO = ("Protocolo", "Data/hora", "Tipo", "Status", "Título", "Local", "Solicitante", "Responsável")
LARGURAS_PDF_MM = (23, 25, 20, 29, 42, 37, 32, 31)
TIPOS = {"sos": "SOS", "manutencao": "Manutenção", "denuncia": "Denúncia"}
STATUS = {
    "pendente": "Pendente",
    "aguardando_aceite": "Aguardando aceite",
    "em_atendimento": "Em atendimento",
    "concluido": "Concluído",
    "cancelado": "Cancelado",
}


@dataclass(frozen=True)
class LinhaRelatorio:
    protocolo: str
    data_hora: str
    tipo: str
    status: str
    titulo: str
    local: str
    solicitante: str
    responsavel: str

    def como_lista(self) -> list[str]:
        return [
            self.protocolo,
            self.data_hora,
            self.tipo,
            self.status,
            self.titulo,
            self.local,
            self.solicitante,
            self.responsavel,
        ]


class RelatorioService:
    def __init__(self, sessao: Session) -> None:
        self.ocorrencias = OcorrenciaRepository(sessao)

    @staticmethod
    def validar_periodo(de: date | None, ate: date | None) -> None:
        if de is not None and ate is not None and de > ate:
            raise RegraDeNegocioErro("O início do período não pode ser posterior ao fim.")

    def iterar_linhas(
        self, *, de: date | None = None, ate: date | None = None, tipo: str | None = None, status: str | None = None
    ) -> Iterator[LinhaRelatorio]:
        self.validar_periodo(de, ate)
        for ocorrencia, nome_autor, nome_responsavel in self.ocorrencias.iterar_para_relatorio(
            de=de, ate=ate, tipo=tipo, status=status
        ):
            yield self._linha(ocorrencia, nome_autor, nome_responsavel)

    def gerar_csv(
        self, *, de: date | None = None, ate: date | None = None, tipo: str | None = None, status: str | None = None
    ) -> Iterator[bytes]:
        """CSV incremental: as linhas saem do banco direto para a resposta."""
        linhas = (linha.como_lista() for linha in self.iterar_linhas(de=de, ate=ate, tipo=tipo, status=status))
        documento = DocumentoTabular(titulo="Relatório de ocorrências", cabecalho=CABECALHO, linhas=linhas)
        return ExportadorCsv().gerar(documento)

    def gerar_pdf(
        self, *, de: date | None = None, ate: date | None = None, tipo: str | None = None, status: str | None = None
    ) -> bytes:
        self.validar_periodo(de, ate)
        linhas: list[list[str]] = []
        truncado = False
        for linha in self.iterar_linhas(de=de, ate=ate, tipo=tipo, status=status):
            if len(linhas) == LIMITE_LINHAS_PDF:
                truncado = True
                break
            linhas.append(linha.como_lista())

        contagens = self.ocorrencias.contar_para_relatorio(de=de, ate=ate, tipo=tipo, status=status)
        documento = DocumentoTabular(
            titulo="Relatório de ocorrências · Uni SOS",
            cabecalho=CABECALHO,
            linhas=linhas,
            informacoes=self._informacoes(contagens, de, ate, tipo, status),
            avisos=["Relatório truncado em 5.000 linhas. Filtre por período para obter o conjunto completo."] if truncado else [],
            larguras_mm=LARGURAS_PDF_MM,
            mensagem_vazio="Nenhuma ocorrência encontrada.",
        )
        return ExportadorPdf().gerar_bytes(documento)

    @staticmethod
    def nome_arquivo(extensao: str, de: date | None, ate: date | None) -> str:
        inicio = de.isoformat() if de else "inicio"
        fim = ate.isoformat() if ate else "atual"
        return f"ocorrencias_{inicio}_a_{fim}.{extensao}"

    @staticmethod
    def _linha(ocorrencia: Ocorrencia, nome_autor: str | None, nome_responsavel: str | None) -> LinhaRelatorio:
        data = ocorrencia.criado_em
        if data.tzinfo is None:
            data = data.replace(tzinfo=FUSO_FORTALEZA)
        data_local = data.astimezone(FUSO_FORTALEZA)
        solicitante = "Anônimo" if ocorrencia.tipo == "denuncia" and ocorrencia.anonima else (nome_autor or "Usuário")
        return LinhaRelatorio(
            protocolo=ocorrencia.protocolo,
            data_hora=data_local.strftime("%d/%m/%Y %H:%M"),
            tipo=TIPOS.get(ocorrencia.tipo, ocorrencia.tipo),
            status=STATUS.get(ocorrencia.status, ocorrencia.status),
            titulo=ocorrencia.titulo,
            local=ocorrencia.local,
            solicitante=solicitante,
            responsavel=nome_responsavel or "Não atribuído",
        )

    @classmethod
    def _informacoes(
        cls, contagens: list[tuple[str, str, int]], de: date | None, ate: date | None, tipo: str | None, status: str | None
    ) -> list[str]:
        filtros = [f"tipo: {TIPOS[tipo]}" if tipo else "tipo: todos", f"status: {STATUS[status]}" if status else "status: todos"]
        por_tipo: Counter[str] = Counter()
        por_status: Counter[str] = Counter()
        for tipo_linha, status_linha, quantidade in contagens:
            por_tipo[TIPOS.get(tipo_linha, tipo_linha)] += quantidade
            por_status[STATUS.get(status_linha, status_linha)] += quantidade
        resumo_tipo = ", ".join(f"{nome}: {qtd}" for nome, qtd in sorted(por_tipo.items())) or "nenhuma ocorrência"
        resumo_status = ", ".join(f"{nome}: {qtd}" for nome, qtd in sorted(por_status.items())) or "nenhuma ocorrência"
        return [
            f"Período: {cls._periodo(de, ate)}",
            f"Filtros: {' · '.join(filtros)}",
            f"Resumo por tipo: {resumo_tipo}",
            f"Resumo por status: {resumo_status}",
        ]

    @staticmethod
    def _periodo(de: date | None, ate: date | None) -> str:
        inicio = de.strftime("%d/%m/%Y") if de else "início dos registros"
        fim = ate.strftime("%d/%m/%Y") if ate else "hoje"
        return f"{inicio} a {fim}"
