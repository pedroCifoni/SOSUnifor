"""Programação Orientada a Aspectos (POA) do Uni SOS.

Interesses transversais (auditoria, medição de desempenho, publicação de eventos) não
ficam espalhados pelo código de negócio: cada um é um ASPECTO escrito uma vez aqui e
aplicado aos services por decorators. Vocabulário usado no código e em docs/POA-e-eventos.md:

- Aspecto: o módulo que encapsula um interesse transversal (``auditar``, ``medir_desempenho``,
  ``publicar_evento`` e, na camada HTTP, ``AspectoHttp`` em app/core/aspecto_http.py).
- Ponto de junção (join point): um momento da execução onde um aspecto pode agir. Aqui é
  sempre a EXECUÇÃO de um método de service (ex.: ``OcorrenciaService.criar``), representada
  por ``PontoDeJuncao`` (alvo + argumentos já nomeados).
- Advice: o código do aspecto que roda no ponto de junção. Todos aqui são "around": recebem
  o ponto de junção e a função ``prosseguir``, e decidem o que fazer antes, depois e em caso
  de erro.
- Ponto de corte (pointcut): a regra que escolhe os pontos de junção. Pode ser nominal (o
  decorator escrito acima do método: ``@auditar("usuario.criar", ...)``) ou por padrão
  (``PontoDeCorte``: módulo/classe/método por expressão regular, como ``SERVICOS_DA_APLICACAO``).
- Weaving (tecelagem): o momento em que o advice é "costurado" ao ponto de junção. Com
  decorators, acontece ao carregar a classe; com ``tecer(...)``, na subida da API (main.py).
"""

import functools
import inspect
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.core import contexto_requisicao, eventos
from app.core.eventos import Evento
from app.core.excecoes import ErroAplicacao


logger = logging.getLogger(__name__)
logger_desempenho = logging.getLogger("app.desempenho")

PREFIXO_AUDITORIA = "auditoria."
# Chaves que nunca podem ir para a trilha de auditoria nem para os eventos, mesmo que um
# extrator as devolva por engano (defesa em profundidade).
CHAVES_SENSIVEIS = re.compile(r"senha|password|token|segredo|secret|descricao|conteudo|anexo|email", re.IGNORECASE)

Extrator = Callable[["PontoDeJuncao", Any], Any]


# ---------- ponto de junção ----------
@dataclass(frozen=True)
class PontoDeJuncao:
    """Uma execução concreta de um método interceptado."""

    alvo: str  # "Classe.metodo"
    argumentos: dict[str, Any]  # inclui "self"
    # Valores já calculados pelos extratores deste ponto de junção (evita repetir consultas ao banco).
    memoria: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    @property
    def instancia(self) -> Any:
        return self.argumentos.get("self")

    def lembrar(self, chave: str, calcular: Callable[[], Any]) -> Any:
        """Calcula uma vez por ponto de junção; as chamadas seguintes reaproveitam o valor."""
        if chave not in self.memoria:
            self.memoria[chave] = calcular()
        return self.memoria[chave]

    def resolver(self, caminho: str, resultado: Any = None) -> Any:
        """Lê um valor pelo caminho pontuado: "dados.tipo", "administrador.id" ou "resultado.id"."""
        nome, *atributos = caminho.split(".")
        valor = resultado if nome == "resultado" else self.argumentos.get(nome)
        for atributo in atributos:
            if valor is None:
                return None
            valor = valor.get(atributo) if isinstance(valor, dict) else getattr(valor, atributo, None)
        return valor


def _aplicar_advice(nome_do_aspecto: str, advice: Callable[[PontoDeJuncao, Callable[[], Any]], Any]):
    """Transforma um advice "around" em decorator (é aqui que a tecelagem acontece)."""

    def decorador(funcao: Callable) -> Callable:
        assinatura = inspect.signature(funcao)
        alvo = funcao.__qualname__

        @functools.wraps(funcao)
        def envoltorio(*args: Any, **kwargs: Any) -> Any:
            ligacao = assinatura.bind_partial(*args, **kwargs)
            ponto = PontoDeJuncao(alvo=alvo, argumentos=dict(ligacao.arguments))
            return advice(ponto, lambda: funcao(*args, **kwargs))

        envoltorio.__aspectos__ = (*getattr(funcao, "__aspectos__", ()), nome_do_aspecto)  # type: ignore[attr-defined]
        return envoltorio

    return decorador


# ---------- utilidades dos extratores ----------
def _resolver(extrator: str | Extrator | None, ponto: PontoDeJuncao, resultado: Any) -> Any:
    if extrator is None:
        return None
    if callable(extrator):
        return extrator(ponto, resultado)
    return ponto.resolver(extrator, resultado)


def campos(**caminhos: str) -> Extrator:
    """Extrator declarativo de detalhes: ``campos(status="dados.status")``. Só o que for listado vai para o registro."""

    def extrair(ponto: PontoDeJuncao, resultado: Any) -> dict[str, Any]:
        return {chave: ponto.resolver(caminho, resultado) for chave, caminho in caminhos.items()}

    return extrair


def nomes_dos_campos_enviados(caminho: str) -> Extrator:
    """Extrator que registra QUAIS campos de um DTO foram enviados (nunca os valores)."""

    def extrair(ponto: PontoDeJuncao, resultado: Any) -> dict[str, Any]:
        dto = ponto.resolver(caminho, resultado)
        enviados = dto.model_dump(exclude_unset=True) if dto is not None else {}
        return {"campos_alterados": ",".join(sorted(enviados))}

    return extrair


def _valor_simples(valor: Any) -> Any:
    if valor is None or isinstance(valor, (bool, int, float, str)):
        return valor
    return str(valor)


def sanitizar(detalhes: dict[str, Any] | None) -> dict[str, Any]:
    """Remove chaves sensíveis e reduz os valores a tipos simples (texto curto)."""
    limpos: dict[str, Any] = {}
    for chave, valor in (detalhes or {}).items():
        if CHAVES_SENSIVEIS.search(chave):
            continue
        valor = _valor_simples(valor)
        limpos[chave] = valor[:120] if isinstance(valor, str) else valor
    return limpos


def _id_texto(valor: Any) -> str | None:
    return None if valor is None else str(valor)[:64]


def _como_uuid(valor: Any) -> UUID | None:
    if valor is None or isinstance(valor, UUID):
        return valor
    try:
        return UUID(str(valor))
    except ValueError:
        return None


def _descrever_erro(erro: BaseException) -> str:
    """Mensagens de negócio (ErroAplicacao) são textos de interface; de resto, só o nome da exceção."""
    if isinstance(erro, ErroAplicacao):
        return f"{type(erro).__name__}: {erro.mensagem}"[:200]
    return type(erro).__name__


def _quem(ator: str | Extrator | None, anonimo_se: str | None, ponto: PontoDeJuncao, resultado: Any) -> UUID | None:
    """Quem fez: o extrator do ponto de corte ou, sem ele, o usuário autenticado da requisição."""
    if anonimo_se and ponto.resolver(anonimo_se, resultado):
        return None  # denúncia anônima: a trilha não pode revelar o autor
    if ator is None:
        return contexto_requisicao.atual().ator_id
    return _como_uuid(_resolver(ator, ponto, resultado))


def _seguro(descricao: str, funcao: Callable[[], Any]) -> Any:
    """Um aspecto nunca pode derrubar a operação de negócio."""
    try:
        return funcao()
    except Exception:
        logger.exception("Falha no aspecto ao %s.", descricao)
        return None


def entregar(evento: Evento) -> None:
    """Publica no RabbitMQ (com confirmação). Sem broker, grava a auditoria direto no banco.

    O fallback é obrigatório: se o CloudAMQP cair, a operação continua e a trilha também.
    """
    if eventos.publicar(evento):
        return
    from app.services.auditoria_service import gravar_evento  # import tardio: evita ciclo core -> services

    gravar_evento(evento, "direto")
    # Sem broker, os observadores (eventos.assinar) recebem o evento no próprio processo.
    eventos.notificar_localmente(evento)


# ---------- aspecto: auditoria ----------
def auditar(
    acao: str,
    *,
    entidade: str,
    entidade_id: str | Extrator | None = None,
    ator: str | Extrator | None = None,
    anonimo_se: str | None = None,
    detalhes: Extrator | None = None,
    itens: Extrator | None = None,
    registrar_se: Extrator | None = None,
):
    """Advice "around" que registra quem fez, o quê, quando, sobre qual entidade e o resultado.

    O registro vira o evento "auditoria.<acao>" no RabbitMQ (consumido pela fila
    "unisos.auditoria") ou, sem broker, é gravado direto na tabela ``auditoria``.
    Nunca grava os argumentos inteiros: só o que o ponto de corte declarar em ``detalhes``.

    - ``itens``: para operações em lote. Devolve uma lista de
      ``{"acao": ..., "entidade_id": ..., "detalhes": {...}}``; depois do sucesso, cada item vira
      um registro próprio ("auditoria.<acao do item>"), além do registro do lote. Assim a trilha
      diz sobre qual entidade cada criação, edição ou exclusão foi feita.
    - ``registrar_se``: quando devolve False, nada é registrado (ex.: tentativa anônima com um
      link de redefinição que nem existe, que só encheria a trilha).
    """

    def advice(ponto: PontoDeJuncao, prosseguir: Callable[[], Any]) -> Any:
        inicio = time.perf_counter()
        try:
            resultado = prosseguir()
        except Exception as erro:
            descricao = _descrever_erro(erro)
            _seguro("auditar o erro", lambda: _registrar(ponto, None, "erro", inicio, descricao))
            raise
        _seguro("auditar o sucesso", lambda: _registrar(ponto, resultado, "sucesso", inicio, None))
        return resultado

    def _registrar(ponto: PontoDeJuncao, resultado: Any, situacao: str, inicio: float, erro: str | None) -> None:
        if registrar_se is not None and _seguro("avaliar se registra", lambda: registrar_se(ponto, resultado)) is False:
            return
        duracao_ms = round((time.perf_counter() - inicio) * 1000, 1)
        request_id = contexto_requisicao.atual().request_id
        ator_id = _seguro("identificar o ator", lambda: _quem(ator, anonimo_se, ponto, resultado))

        def registro(acao_registrada: str, id_da_entidade: Any, detalhes_registrados: Any) -> Evento:
            dados = {
                "acao": acao_registrada,
                "alvo": ponto.alvo,
                "entidade": entidade,
                "entidade_id": _id_texto(id_da_entidade),
                "resultado": situacao,
                "duracao_ms": duracao_ms,
                "request_id": request_id,
                "detalhes": sanitizar(detalhes_registrados),
            }
            if erro:
                dados["erro"] = erro
            return Evento(tipo=f"{PREFIXO_AUDITORIA}{acao_registrada}", ator_id=ator_id, dados=dados)

        entregar(
            registro(
                acao,
                _seguro("ler o id da entidade", lambda: _resolver(entidade_id, ponto, resultado)),
                _seguro("ler os detalhes", lambda: _resolver(detalhes, ponto, resultado)),
            )
        )
        if itens is None or situacao != "sucesso":
            return  # lote que falhou não gravou nada (tudo ou nada): basta o registro do lote
        for item in _seguro("ler os itens", lambda: _resolver(itens, ponto, resultado)) or []:
            _seguro(
                f"auditar o item {item.get('acao')}",
                lambda item=item: entregar(registro(item["acao"], item.get("entidade_id"), item.get("detalhes"))),
            )

    return _aplicar_advice("auditar", advice)


# ---------- aspecto: eventos de domínio ----------
def publicar_evento(
    tipo: str,
    *,
    entidade: str,
    entidade_id: str | Extrator | None = None,
    ator: str | Extrator | None = None,
    anonimo_se: str | None = None,
    dados: Extrator | None = None,
    publicar_se: Extrator | None = None,
):
    """Advice "around" que publica um evento de domínio DEPOIS que a operação deu certo.

    Os services fazem commit antes de retornar; então, quando o advice roda, o fato já
    está gravado. Se a operação lançar exceção, nenhum evento é publicado.
    """

    def advice(ponto: PontoDeJuncao, prosseguir: Callable[[], Any]) -> Any:
        resultado = prosseguir()
        if publicar_se is None or publicar_se(ponto, resultado):
            _seguro(f"publicar o evento {tipo}", lambda: _publicar(ponto, resultado))
        return resultado

    def _publicar(ponto: PontoDeJuncao, resultado: Any) -> None:
        conteudo = {
            "entidade": entidade,
            "entidade_id": _id_texto(_resolver(entidade_id, ponto, resultado)),
            "resultado": "sucesso",
            "request_id": contexto_requisicao.atual().request_id,
            **sanitizar(_resolver(dados, ponto, resultado)),
        }
        entregar(Evento(tipo=tipo, ator_id=_quem(ator, anonimo_se, ponto, resultado), dados=conteudo))

    return _aplicar_advice("publicar_evento", advice)


# ---------- aspecto: desempenho ----------
def medir_desempenho(limite_ms: float):
    """Advice "around" que mede o tempo do ponto de junção e registra no log as chamadas lentas."""

    def advice(ponto: PontoDeJuncao, prosseguir: Callable[[], Any]) -> Any:
        inicio = time.perf_counter()
        try:
            return prosseguir()
        finally:
            gasto_ms = (time.perf_counter() - inicio) * 1000
            if gasto_ms > limite_ms:
                logger_desempenho.warning(
                    "Chamada lenta: %s levou %.0f ms (limite %.0f ms) [request_id=%s]",
                    ponto.alvo,
                    gasto_ms,
                    limite_ms,
                    contexto_requisicao.atual().request_id or "-",
                )

    return _aplicar_advice("medir_desempenho", advice)


# ---------- pontos de corte por padrão e tecelagem ----------
@dataclass(frozen=True)
class PontoDeCorte:
    """Pointcut por padrão: escolhe métodos pelo módulo, pela classe e pelo nome (expressões regulares)."""

    descricao: str
    modulo: str = r".*"
    classe: str = r".*"
    metodo: str = r"^[a-z]\w*$"  # públicos (não começam com "_")

    def seleciona(self, classe: type, nome_do_metodo: str) -> bool:
        return (
            re.search(self.modulo, classe.__module__) is not None
            and re.search(self.classe, classe.__name__) is not None
            and re.search(self.metodo, nome_do_metodo) is not None
        )


# "execution(public * app.services.*Service.*(..))", em notação AspectJ.
SERVICOS_DA_APLICACAO = PontoDeCorte(
    descricao="qualquer método público de qualquer classe *Service em app.services",
    modulo=r"^app\.services\.",
    classe=r"Service$",
)


def tecer(ponto_de_corte: PontoDeCorte, nome_do_aspecto: str, aspecto: Callable[[Callable], Callable], classes: list[type]) -> list[str]:
    """Aplica o aspecto a todos os métodos selecionados pelo ponto de corte. Idempotente.

    Métodos estáticos e de classe ficam de fora (não são execuções sobre uma instância de service).
    Devolve os pontos de junção costurados, para log e testes.
    """
    costurados: list[str] = []
    for classe in classes:
        for nome, membro in list(vars(classe).items()):
            if not inspect.isfunction(membro) or not ponto_de_corte.seleciona(classe, nome):
                continue
            if nome_do_aspecto in getattr(membro, "__aspectos__", ()):
                continue
            setattr(classe, nome, aspecto(membro))
            costurados.append(f"{classe.__name__}.{nome}")
    return costurados


def classes_de_service() -> list[type]:
    """Todas as classes definidas nos módulos de app.services."""
    import importlib
    import pkgutil

    import app.services as pacote

    classes: list[type] = []
    for modulo_info in pkgutil.iter_modules(pacote.__path__):
        modulo = importlib.import_module(f"{pacote.__name__}.{modulo_info.name}")
        classes.extend(
            membro for _, membro in inspect.getmembers(modulo, inspect.isclass) if membro.__module__ == modulo.__name__
        )
    return classes


def tecer_aspectos_transversais(limite_lento_ms: float) -> list[str]:
    """Tecelagem na subida da API: mede o desempenho de todos os services da aplicação."""
    costurados = tecer(SERVICOS_DA_APLICACAO, "medir_desempenho", medir_desempenho(limite_lento_ms), classes_de_service())
    logger.debug("medir_desempenho(%s ms) costurado em %d pontos de junção.", limite_lento_ms, len(costurados))
    return costurados
