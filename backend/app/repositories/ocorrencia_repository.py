from collections.abc import Iterator
from datetime import date, datetime, time, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import Text, cast, func, select, tuple_
from sqlalchemy.orm import aliased
from sqlalchemy.orm import Session

from app.entities.ocorrencia import Ocorrencia
from app.entities.usuario import Usuario


SEQUENCIA_PROTOCOLO = "ocorrencias_protocolo_seq"
_FUSO_FORTALEZA = ZoneInfo("America/Fortaleza")


class OcorrenciaRepository:
    def __init__(self, sessao: Session) -> None:
        self.sessao = sessao

    def buscar_por_id(self, ocorrencia_id: UUID) -> Ocorrencia | None:
        return self.sessao.get(Ocorrencia, ocorrencia_id)

    def listar_com_nome_do_autor(
        self,
        autor_id: UUID | None = None,
        responsavel_id: UUID | None = None,
        status: str | None = None,
        tipo: str | None = None,
        antes_de: datetime | None = None,
        antes_id: UUID | None = None,
        limite: int = 50,
    ) -> list[tuple[Ocorrencia, str | None]]:
        """Uma página das mais recentes primeiro, já com o nome do autor (JOIN só com os autores da página).

        Paginação por cursor: com `antes_de`/`antes_id`, devolve só as estritamente anteriores
        à tupla (criado_em, id) do último item da página anterior.
        """
        consulta = (
            select(Ocorrencia, Usuario.nome)
            .outerjoin(Usuario, Usuario.id == Ocorrencia.autor_id)
            .order_by(Ocorrencia.criado_em.desc(), Ocorrencia.id.desc())
            .limit(limite)
        )
        if autor_id is not None:
            consulta = consulta.where(Ocorrencia.autor_id == autor_id)
        if responsavel_id is not None:
            consulta = consulta.where(Ocorrencia.responsavel_id == responsavel_id)
        if status is not None:
            consulta = consulta.where(Ocorrencia.status == status)
        if tipo is not None:
            consulta = consulta.where(Ocorrencia.tipo == tipo)
        if antes_de is not None and antes_id is not None:
            consulta = consulta.where(tuple_(Ocorrencia.criado_em, Ocorrencia.id) < tuple_(antes_de, antes_id))
        return [(ocorrencia, nome) for ocorrencia, nome in self.sessao.execute(consulta)]

    def contar_por_status_e_tipo(
        self, autor_id: UUID | None = None, responsavel_id: UUID | None = None
    ) -> list[tuple[str, str, int]]:
        """Contagens agrupadas no banco: (status, tipo, quantidade)."""
        consulta = select(Ocorrencia.status, Ocorrencia.tipo, func.count()).group_by(Ocorrencia.status, Ocorrencia.tipo)
        if autor_id is not None:
            consulta = consulta.where(Ocorrencia.autor_id == autor_id)
        if responsavel_id is not None:
            consulta = consulta.where(Ocorrencia.responsavel_id == responsavel_id)
        return [(status, tipo, quantidade) for status, tipo, quantidade in self.sessao.execute(consulta)]

    def iterar_para_relatorio(
        self,
        *,
        de: date | None = None,
        ate: date | None = None,
        tipo: str | None = None,
        status: str | None = None,
        tamanho_lote: int = 500,
    ) -> Iterator[tuple[Ocorrencia, str | None, str | None]]:
        """Percorre as ocorrências do relatório sem materializar o resultado inteiro."""
        consulta = self._consulta_relatorio(de=de, ate=ate, tipo=tipo, status=status)
        resultado = self.sessao.execute(consulta.execution_options(stream_results=True)).yield_per(tamanho_lote)
        yield from resultado

    def contar_para_relatorio(
        self, *, de: date | None = None, ate: date | None = None, tipo: str | None = None, status: str | None = None
    ) -> list[tuple[str, str, int]]:
        consulta = self._filtros_relatorio(select(Ocorrencia.tipo, Ocorrencia.status, func.count()), de, ate, tipo, status)
        consulta = consulta.group_by(Ocorrencia.tipo, Ocorrencia.status)
        return [(tipo_linha, status_linha, quantidade) for tipo_linha, status_linha, quantidade in self.sessao.execute(consulta)]

    @staticmethod
    def _filtros_relatorio(consulta, de: date | None, ate: date | None, tipo: str | None, status: str | None):
        # As datas recebidas representam dias locais em Fortaleza; o banco armazena instantes com fuso.
        if de is not None:
            inicio = datetime.combine(de, time.min, tzinfo=_FUSO_FORTALEZA).astimezone(timezone.utc)
            consulta = consulta.where(Ocorrencia.criado_em >= inicio)
        if ate is not None:
            fim = datetime.combine(ate, time.max, tzinfo=_FUSO_FORTALEZA).astimezone(timezone.utc)
            consulta = consulta.where(Ocorrencia.criado_em <= fim)
        if tipo is not None:
            consulta = consulta.where(Ocorrencia.tipo == tipo)
        if status is not None:
            consulta = consulta.where(Ocorrencia.status == status)
        return consulta

    def _consulta_relatorio(self, *, de: date | None, ate: date | None, tipo: str | None, status: str | None):
        autor = aliased(Usuario)
        responsavel = aliased(Usuario)
        consulta = (
            select(Ocorrencia, autor.nome, responsavel.nome)
            .outerjoin(autor, autor.id == Ocorrencia.autor_id)
            .outerjoin(responsavel, responsavel.id == Ocorrencia.responsavel_id)
            .order_by(Ocorrencia.criado_em.desc(), Ocorrencia.id.desc())
        )
        return self._filtros_relatorio(consulta, de, ate, tipo, status)

    def listar_que_citam_arquivo(self, nome_armazenado: str) -> list[Ocorrencia]:
        """Candidatas cujo JSON de anexos contém o nome do arquivo; o filtro é feito no banco.

        É um pré-filtro: quem chama ainda confere a URL exata de cada anexo.
        """
        nome_escapado = nome_armazenado.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        consulta = select(Ocorrencia).where(
            cast(Ocorrencia.anexos, Text).like(f"%{nome_escapado}%", escape="\\")
        )
        return list(self.sessao.scalars(consulta))

    def proximo_numero_protocolo(self) -> int:
        """Número sequencial sem condição de corrida (SEQUENCE no Postgres)."""
        if self.sessao.get_bind().dialect.name == "postgresql":
            return int(self.sessao.scalar(select(func.nextval(SEQUENCIA_PROTOCOLO))))
        # Fora do Postgres (testes locais), usa o maior número já gravado.
        numeros = self.sessao.scalars(select(Ocorrencia.protocolo))
        maior = max((int(p.rsplit("-", 1)[-1]) for p in numeros if p.rsplit("-", 1)[-1].isdigit()), default=0)
        return maior + 1

    def protocolo_existe(self, protocolo: str) -> bool:
        return self.sessao.scalar(select(Ocorrencia.id).where(Ocorrencia.protocolo == protocolo).limit(1)) is not None

    def adicionar(self, ocorrencia: Ocorrencia) -> Ocorrencia:
        self.sessao.add(ocorrencia)
        self.sessao.flush()
        return ocorrencia
