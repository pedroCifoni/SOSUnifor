from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response, StreamingResponse

from app.controllers.dependencias import Administrador, relatorio_service
from app.dtos.ocorrencia_dto import StatusOcorrencia, TipoOcorrencia
from app.services.relatorio_service import RelatorioService


router = APIRouter(prefix="/relatorios", tags=["Relatórios"])
Servico = Annotated[RelatorioService, Depends(relatorio_service)]


def _cabecalho_download(nome: str) -> dict[str, str]:
    return {"Content-Disposition": f'attachment; filename="{nome}"'}


@router.get("/ocorrencias.csv")
def exportar_csv(
    administrador: Administrador,
    servico: Servico,
    de: Annotated[date | None, Query(description="Data inicial (YYYY-MM-DD)")] = None,
    ate: Annotated[date | None, Query(description="Data final (YYYY-MM-DD)")] = None,
    tipo: TipoOcorrencia | None = None,
    status: StatusOcorrencia | None = None,
) -> StreamingResponse:
    servico.validar_periodo(de, ate)
    nome = servico.nome_arquivo("csv", de, ate)
    return StreamingResponse(
        servico.gerar_csv(de=de, ate=ate, tipo=tipo, status=status),
        media_type="text/csv; charset=utf-8",
        headers=_cabecalho_download(nome),
    )


@router.get("/ocorrencias.pdf")
def exportar_pdf(
    administrador: Administrador,
    servico: Servico,
    de: Annotated[date | None, Query(description="Data inicial (YYYY-MM-DD)")] = None,
    ate: Annotated[date | None, Query(description="Data final (YYYY-MM-DD)")] = None,
    tipo: TipoOcorrencia | None = None,
    status: StatusOcorrencia | None = None,
) -> Response:
    servico.validar_periodo(de, ate)
    nome = servico.nome_arquivo("pdf", de, ate)
    return Response(
        content=servico.gerar_pdf(de=de, ate=ate, tipo=tipo, status=status),
        media_type="application/pdf",
        headers=_cabecalho_download(nome),
    )
