"""Estratégias de exportação (Strategy + Factory), sem banco."""

import pytest

from app.core.excecoes import RegraDeNegocioErro
from app.core.exportacao import DocumentoTabular, ExportadorCsv, ExportadorPdf, criar_exportador


def _documento(linhas):
    return DocumentoTabular(titulo="Teste", cabecalho=("Nome", "E-mail"), linhas=linhas)


def test_factory_devolve_a_estrategia_do_formato() -> None:
    assert isinstance(criar_exportador("csv"), ExportadorCsv)
    assert isinstance(criar_exportador("PDF"), ExportadorPdf)
    with pytest.raises(RegraDeNegocioErro):
        criar_exportador("xlsx")


def test_csv_tem_bom_cabecalho_e_neutraliza_formulas() -> None:
    conteudo = b"".join(ExportadorCsv().gerar(_documento([["=HYPERLINK(1)", "a@edu.unifor.br"]])))

    texto = conteudo.decode("utf-8-sig").splitlines()
    assert conteudo.startswith(b"\xef\xbb\xbf")
    assert texto[0] == "Nome;E-mail"
    assert texto[1] == "'=HYPERLINK(1);a@edu.unifor.br"


def test_pdf_gera_documento_valido_mesmo_vazio_e_com_marcacao() -> None:
    vazio = b"".join(ExportadorPdf().gerar(_documento([])))
    com_tags = ExportadorPdf().gerar_bytes(_documento([["<b>nome</b> & cia", "x@edu.unifor.br"]]))

    assert vazio.startswith(b"%PDF")
    assert com_tags.startswith(b"%PDF")
