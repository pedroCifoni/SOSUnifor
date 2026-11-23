"""Geração de relatórios de ocorrências, sem expor dados pessoais desnecessários."""

import csv
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO, StringIO
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from app.core.excecoes import RegraDeNegocioErro
from app.entities.ocorrencia import Ocorrencia
from app.repositories.ocorrencia_repository import OcorrenciaRepository


FUSO_FORTALEZA = ZoneInfo("America/Fortaleza")
LIMITE_LINHAS_PDF = 5_000
CABECALHO = ("Protocolo", "Data/hora", "Tipo", "Status", "Título", "Local", "Solicitante", "Responsável")
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
        """CSV incremental com BOM para Excel e proteção contra fórmulas maliciosas."""
        yield b"\xef\xbb\xbf"
        yield self._csv(CABECALHO)
        for linha in self.iterar_linhas(de=de, ate=ate, tipo=tipo, status=status):
            yield self._csv(tuple(self._proteger_csv(valor) for valor in linha.como_lista()))

    def gerar_pdf(
        self, *, de: date | None = None, ate: date | None = None, tipo: str | None = None, status: str | None = None
    ) -> bytes:
        self.validar_periodo(de, ate)
        linhas: list[LinhaRelatorio] = []
        truncado = False
        for linha in self.iterar_linhas(de=de, ate=ate, tipo=tipo, status=status):
            if len(linhas) == LIMITE_LINHAS_PDF:
                truncado = True
                break
            linhas.append(linha)

        contagens = self.ocorrencias.contar_para_relatorio(de=de, ate=ate, tipo=tipo, status=status)
        return self._montar_pdf(linhas, contagens, de, ate, tipo, status, truncado)

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

    @staticmethod
    def _proteger_csv(valor: str) -> str:
        return f"'{valor}" if valor.startswith(("=", "+", "-", "@", "\t", "\r")) else valor

    @staticmethod
    def _csv(valores: tuple[str, ...]) -> bytes:
        buffer = StringIO(newline="")
        csv.writer(buffer, delimiter=";", lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL).writerow(valores)
        return buffer.getvalue().encode("utf-8")

    def _montar_pdf(
        self,
        linhas: list[LinhaRelatorio],
        contagens: list[tuple[str, str, int]],
        de: date | None,
        ate: date | None,
        tipo: str | None,
        status: str | None,
        truncado: bool,
    ) -> bytes:
        arquivo = BytesIO()
        documento = SimpleDocTemplate(
            arquivo, pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm, topMargin=14 * mm, bottomMargin=14 * mm
        )
        estilos = getSampleStyleSheet()
        pequeno = ParagraphStyle("pequeno", parent=estilos["Normal"], fontName="Helvetica", fontSize=6.7, leading=8)
        destaque = ParagraphStyle("destaque", parent=estilos["Normal"], textColor=colors.HexColor("#9b1c1c"), fontSize=8)
        elementos = [Paragraph("Relatório de ocorrências · Uni SOS", estilos["Title"])]
        elementos.append(Paragraph(f"Período: {self._periodo(de, ate)}", estilos["Normal"]))
        filtros = [f"tipo: {TIPOS[tipo]}" if tipo else "tipo: todos", f"status: {STATUS[status]}" if status else "status: todos"]
        elementos.append(Paragraph(f"Filtros: {' · '.join(filtros)}", estilos["Normal"]))
        gerado_em = datetime.now(FUSO_FORTALEZA).strftime("%d/%m/%Y %H:%M")
        elementos.append(Paragraph(f"Gerado em: {gerado_em} (America/Fortaleza)", estilos["Normal"]))
        elementos.append(Spacer(1, 4 * mm))

        por_tipo: Counter[str] = Counter()
        por_status: Counter[str] = Counter()
        for tipo_linha, status_linha, quantidade in contagens:
            por_tipo[TIPOS.get(tipo_linha, tipo_linha)] += quantidade
            por_status[STATUS.get(status_linha, status_linha)] += quantidade
        resumo_tipo = ", ".join(f"{nome}: {quantidade}" for nome, quantidade in sorted(por_tipo.items())) or "nenhuma ocorrência"
        resumo_status = ", ".join(f"{nome}: {quantidade}" for nome, quantidade in sorted(por_status.items())) or "nenhuma ocorrência"
        elementos.extend([Paragraph(f"Resumo por tipo: {resumo_tipo}", estilos["Normal"]), Paragraph(f"Resumo por status: {resumo_status}", estilos["Normal"])])
        if truncado:
            elementos.append(Paragraph("Relatório truncado em 5.000 linhas. Filtre por período para obter o conjunto completo.", destaque))
        elementos.append(Spacer(1, 4 * mm))

        tabela = [[Paragraph(cabecalho, pequeno) for cabecalho in CABECALHO]]
        tabela.extend([[Paragraph(valor, pequeno) for valor in linha.como_lista()] for linha in linhas])
        if not linhas:
            tabela.append([Paragraph("Nenhuma ocorrência encontrada.", pequeno), *["" for _ in range(len(CABECALHO) - 1)]])
        grade = Table(tabela, colWidths=[23 * mm, 25 * mm, 20 * mm, 29 * mm, 42 * mm, 37 * mm, 32 * mm, 31 * mm], repeatRows=1)
        grade.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#103b5c")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 1), (-1, -1), colors.white),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        elementos.append(grade)
        documento.build(elementos, onFirstPage=self._rodape, onLaterPages=self._rodape)
        return arquivo.getvalue()

    @staticmethod
    def _periodo(de: date | None, ate: date | None) -> str:
        inicio = de.strftime("%d/%m/%Y") if de else "início dos registros"
        fim = ate.strftime("%d/%m/%Y") if ate else "hoje"
        return f"{inicio} a {fim}"

    @staticmethod
    def _rodape(canvas, documento) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(landscape(A4)[0] - 12 * mm, 8 * mm, f"Página {documento.page}")
        canvas.restoreState()
