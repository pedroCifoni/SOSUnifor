from datetime import datetime
from uuid import UUID

from sqlalchemy import Text, cast, func, select, tuple_
from sqlalchemy.orm import Session

from app.entities.ocorrencia import Ocorrencia
from app.entities.usuario import Usuario


SEQUENCIA_PROTOCOLO = "ocorrencias_protocolo_seq"


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
