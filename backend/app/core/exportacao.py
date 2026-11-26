"""Exportação de dados tabulares em CSV ou PDF (padrões Strategy e Factory).

Os services descrevem *o que* exportar montando um ``DocumentoTabular``; a estratégia
(``ExportadorCsv`` ou ``ExportadorPdf``) decide *como* serializar. A ``criar_exportador``
escolhe a estratégia pelo formato pedido, então um novo formato (ex.: XLSX) entra sem
mudar nenhum service ou controller.
"""

import csv
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO, StringIO
from typing import Protocol
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.excecoes import RegraDeNegocioErro


FUSO_FORTALEZA = ZoneInfo("America/Fortaleza")


@dataclass
class DocumentoTabular:
    """O que exportar, independente do formato."""

    titulo: str
    cabecalho: Sequence[str]
    linhas: Iterable[Sequence[str]]
    informacoes: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    larguras_mm: Sequence[float] | None = None
    mensagem_vazio: str = "Nenhum registro encontrado."


class Exportador(Protocol):
    """Contrato comum (Strategy) dos formatos de exportação."""

    extensao: str
    media_type: str

    def gerar(self, documento: DocumentoTabular) -> Iterator[bytes]: ...


class ExportadorCsv:
    """CSV incremental (streaming), com BOM para o Excel e proteção contra injeção de fórmulas."""

    extensao = "csv"
    media_type = "text/csv; charset=utf-8"

    def gerar(self, documento: DocumentoTabular) -> Iterator[bytes]:
        yield b"\xef\xbb\xbf"
        yield self._linha(documento.cabecalho)
        for linha in documento.linhas:
            yield self._linha([self.proteger(valor) for valor in linha])

    @staticmethod
    def proteger(valor: str) -> str:
        return f"'{valor}" if valor.startswith(("=", "+", "-", "@", "\t", "\r")) else valor

    @staticmethod
    def _linha(valores: Sequence[str]) -> bytes:
        buffer = StringIO(newline="")
        csv.writer(buffer, delimiter=";", lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL).writerow(valores)
        return buffer.getvalue().encode("utf-8")


class ExportadorPdf:
    """PDF A4 paisagem com cabeçalho informativo, tabela paginada e número de página."""

    extensao = "pdf"
    media_type = "application/pdf"

    def gerar(self, documento: DocumentoTabular) -> Iterator[bytes]:
        yield self.gerar_bytes(documento)

    def gerar_bytes(self, documento: DocumentoTabular) -> bytes:
        arquivo = BytesIO()
        pdf = SimpleDocTemplate(
            arquivo, pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm, topMargin=14 * mm, bottomMargin=14 * mm
        )
        estilos = getSampleStyleSheet()
        pequeno = ParagraphStyle("pequeno", parent=estilos["Normal"], fontName="Helvetica", fontSize=6.7, leading=8)
        destaque = ParagraphStyle("destaque", parent=estilos["Normal"], textColor=colors.HexColor("#9b1c1c"), fontSize=8)

        elementos = [Paragraph(documento.titulo, estilos["Title"])]
        elementos.extend(Paragraph(info, estilos["Normal"]) for info in documento.informacoes)
        gerado_em = datetime.now(FUSO_FORTALEZA).strftime("%d/%m/%Y %H:%M")
        elementos.append(Paragraph(f"Gerado em: {gerado_em} (America/Fortaleza)", estilos["Normal"]))
        elementos.extend(Paragraph(aviso, destaque) for aviso in documento.avisos)
        elementos.append(Spacer(1, 4 * mm))

        colunas = len(documento.cabecalho)
        tabela = [[Paragraph(self._escapar(titulo), pequeno) for titulo in documento.cabecalho]]
        tabela.extend([[Paragraph(self._escapar(valor), pequeno) for valor in linha] for linha in documento.linhas])
        if len(tabela) == 1:
            tabela.append([Paragraph(documento.mensagem_vazio, pequeno), *["" for _ in range(colunas - 1)]])
        larguras = [largura * mm for largura in documento.larguras_mm] if documento.larguras_mm else None
        grade = Table(tabela, colWidths=larguras, repeatRows=1)
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
        pdf.build(elementos, onFirstPage=self._rodape, onLaterPages=self._rodape)
        return arquivo.getvalue()

    @staticmethod
    def _escapar(valor: str) -> str:
        # Paragraph interpreta marcação; dados do usuário não podem virar tags.
        return valor.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    @staticmethod
    def _rodape(canvas, documento) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(landscape(A4)[0] - 12 * mm, 8 * mm, f"Página {documento.page}")
        canvas.restoreState()


_EXPORTADORES: dict[str, type[Exportador]] = {"csv": ExportadorCsv, "pdf": ExportadorPdf}


def criar_exportador(formato: str) -> Exportador:
    """Factory: devolve a estratégia de exportação do formato pedido."""
    try:
        return _EXPORTADORES[formato.lower()]()
    except KeyError:
        raise RegraDeNegocioErro(f"Formato de exportação não suportado: {formato}.") from None
