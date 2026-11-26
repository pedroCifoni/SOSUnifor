import unicodedata
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.entities.usuario import Usuario


def normalizar_termo_busca(texto: str) -> str:
    """Remove acentos e converte para minúsculas para casar com `unisos_normalizar_busca`."""
    decomposto = unicodedata.normalize("NFKD", texto.strip())
    sem_acentos = "".join(caractere for caractere in decomposto if unicodedata.category(caractere) != "Mn")
    return sem_acentos.lower()


def escapar_like(texto: str) -> str:
    """Trata `%`, `_` e `\\` digitados na busca como caracteres literais no LIKE."""
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class UsuarioRepository:
    def __init__(self, sessao: Session) -> None:
        self.sessao = sessao

    def buscar_por_id(self, usuario_id: UUID) -> Usuario | None:
        return self.sessao.get(Usuario, usuario_id)

    def buscar_por_email(self, email: str) -> Usuario | None:
        return self.sessao.scalar(select(Usuario).where(Usuario.email == email.lower().strip()))

    def _aplicar_filtros(
        self, consulta, *, desativados: bool = False, busca: str | None = None, perfil: str | None = None
    ):
        if desativados:
            # Contas anonimizadas (LGPD) também ficam inativas, mas não voltam: não aparecem aqui.
            consulta = consulta.where(Usuario.ativo.is_(False), Usuario.anonimizado_em.is_(None))
        else:
            consulta = consulta.where(Usuario.ativo)
        if perfil is not None:
            consulta = consulta.where(Usuario.tipo_usuario == perfil)
        if busca is not None:
            termo = normalizar_termo_busca(busca)
            if termo:
                padrao = f"%{escapar_like(termo)}%"
                if self.sessao.get_bind().dialect.name == "postgresql":
                    consulta = consulta.where(
                        or_(
                            func.unisos_normalizar_busca(Usuario.nome).like(padrao, escape="\\"),
                            func.unisos_normalizar_busca(Usuario.email).like(padrao, escape="\\"),
                        )
                    )
                else:
                    consulta = consulta.where(
                        or_(
                            func.lower(Usuario.nome).like(padrao, escape="\\"),
                            func.lower(Usuario.email).like(padrao, escape="\\"),
                        )
                    )
        return consulta

    def listar(
        self,
        *,
        desativados: bool = False,
        busca: str | None = None,
        perfil: str | None = None,
        limite: int = 50,
        pagina: int = 1,
    ) -> list[Usuario]:
        """Contas ativas (padrão) ou desativadas que ainda podem ser reativadas, em ordem de nome."""
        deslocamento = (max(1, pagina) - 1) * limite
        consulta = self._aplicar_filtros(select(Usuario), desativados=desativados, busca=busca, perfil=perfil)
        consulta = consulta.order_by(Usuario.nome, Usuario.id).offset(deslocamento).limit(limite)
        return list(self.sessao.scalars(consulta))

    def iterar_para_exportacao(
        self, *, desativados: bool = False, busca: str | None = None, perfil: str | None = None
    ):
        """Todas as contas do filtro, em ordem de nome, lidas em lotes (sem carregar as fotos)."""
        consulta = self._aplicar_filtros(select(Usuario), desativados=desativados, busca=busca, perfil=perfil)
        consulta = consulta.order_by(Usuario.nome, Usuario.id).execution_options(yield_per=500)
        yield from self.sessao.scalars(consulta)

    def contar(self, *, desativados: bool = False, busca: str | None = None, perfil: str | None = None) -> int:
        consulta = self._aplicar_filtros(
            select(func.count()).select_from(Usuario), desativados=desativados, busca=busca, perfil=perfil
        )
        return int(self.sessao.scalar(consulta) or 0)

    def listar_ativos_por_perfil(self, perfil: str) -> list[Usuario]:
        consulta = select(Usuario).where(Usuario.ativo, Usuario.tipo_usuario == perfil).order_by(Usuario.nome)
        return list(self.sessao.scalars(consulta))

    def ids_ativos_por_perfil(self, perfil: str) -> list[UUID]:
        return list(self.sessao.scalars(select(Usuario.id).where(Usuario.ativo, Usuario.tipo_usuario == perfil)))

    def contar_ativos_por_perfil(self, perfil: str) -> int:
        consulta = select(func.count()).select_from(Usuario).where(Usuario.tipo_usuario == perfil, Usuario.ativo)
        return self.sessao.scalar(consulta) or 0

    def travar(self, usuario_id: UUID) -> None:
        """Trava a linha da conta até o fim da transação (SELECT ... FOR UPDATE).

        Serializa pedidos simultâneos da mesma conta, como contar e gravar links enviados por e-mail.
        """
        self.sessao.execute(select(Usuario.id).where(Usuario.id == usuario_id).with_for_update())

    def travar_e_contar_ativos_por_perfil(self, perfil: str) -> int:
        """Conta as contas ativas do perfil travando as linhas (SELECT ... FOR UPDATE) até o fim da transação.

        Duas transações que alteram contas deste perfil ao mesmo tempo passam a contar uma de cada vez:
        a segunda espera a primeira terminar e já enxerga o resultado dela.
        """
        consulta = select(Usuario.id).where(Usuario.tipo_usuario == perfil, Usuario.ativo).with_for_update()
        return len(list(self.sessao.scalars(consulta)))

    def existe_outro_com_nome(self, nome: str, exceto_id: UUID) -> bool:
        consulta = select(Usuario.id).where(Usuario.nome == nome, Usuario.id != exceto_id).limit(1)
        return self.sessao.scalar(consulta) is not None

    def ids_de_usuarios_online(self, desde: datetime) -> list[UUID]:
        """Usuários comuns que fizeram alguma requisição autenticada a partir de `desde`."""
        consulta = select(Usuario.id).where(
            Usuario.ativo,
            Usuario.tipo_usuario == "usuario",
            Usuario.ultimo_acesso.is_not(None),
            Usuario.ultimo_acesso >= desde,
        )
        return list(self.sessao.scalars(consulta))

    def listar_com_exclusao_pendente(self) -> list[Usuario]:
        """Titulares que pediram a eliminação dos dados e ainda não foram anonimizados."""
        consulta = (
            select(Usuario)
            .where(Usuario.exclusao_solicitada_em.is_not(None), Usuario.anonimizado_em.is_(None))
            .order_by(Usuario.exclusao_solicitada_em)
        )
        return list(self.sessao.scalars(consulta))

    def adicionar(self, usuario: Usuario) -> Usuario:
        self.sessao.add(usuario)
        return usuario
