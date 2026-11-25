# Programação Orientada a Aspectos (POA) e eventos no RabbitMQ

Este documento explica como o Uni SOS separa os **interesses transversais** (auditoria,
medição de desempenho, publicação de eventos, rastreio de requisições e proteção dos logs)
do código de negócio, e como os eventos trafegam pelo RabbitMQ até a trilha de auditoria.

Arquivos principais:

| Arquivo | Papel |
| --- | --- |
| `backend/app/core/aspectos.py` | Aspectos dos services: `@auditar`, `@publicar_evento`, `@medir_desempenho`, `PontoDeJuncao`, `PontoDeCorte`, `tecer` |
| `backend/app/core/aspecto_http.py` | Aspecto da camada HTTP (middleware `AspectoHttp`) e filtro que mascara dados sensíveis nos logs |
| `backend/app/core/contexto_requisicao.py` | Contexto da requisição (request id e usuário autenticado) lido pelos aspectos |
| `backend/app/core/eventos.py` | Formato do evento, produção com *publisher confirms*, consumidores com *ack* manual |
| `backend/app/services/auditoria_service.py` | Gravação idempotente na tabela `auditoria` e listagem de `GET /auditoria` |
| `src/pages/Admin/AuditoriaPage.tsx` | Tela `/admin/auditoria` |

---

## 1. Por que POA

Sem POA, cada método sensível teria linhas como "grave na auditoria", "meça o tempo",
"publique o evento". Esse código se repete, se mistura com a regra de negócio e é fácil
esquecer em um método novo. Na POA, cada interesse transversal é escrito **uma vez**, num
**aspecto**, e aplicado de fora aos pontos onde deve agir.

Regra do projeto: **os services de negócio não chamam auditoria, log nem eventos**. Isso é
verificado por um teste (`test_services_de_negocio_nao_chamam_auditoria_log_nem_eventos_diretamente`).

## 2. Os conceitos, com exemplos do código

### Aspecto

O módulo que encapsula um interesse transversal. No Uni SOS:

- `auditar(...)`: registra quem fez, o quê, quando, sobre qual entidade e o resultado;
- `publicar_evento(...)`: publica um evento de domínio depois que a operação deu certo;
- `medir_desempenho(limite_ms)`: registra no log as chamadas de service mais lentas que o limite;
- `AspectoHttp`: request id, tempo e status de cada requisição;
- `FiltroDadosSensiveis`: mascara `token=...`, `Bearer ...` e `senha` em todos os logs.

### Ponto de junção (join point)

Um momento da execução em que um aspecto pode agir. Aqui é sempre a **execução de um
método de service** (ex.: `OcorrenciaService.criar`) ou o **processamento de uma requisição
HTTP**. No código, o ponto de junção é um objeto:

```python
@dataclass(frozen=True)
class PontoDeJuncao:
    alvo: str                   # "OcorrenciaService.criar"
    argumentos: dict[str, Any]  # {"self": ..., "dados": OcorrenciaEntrada, "autor": Usuario}
```

`ponto.resolver("autor.id")` ou `ponto.resolver("resultado.protocolo")` leem valores do
ponto de junção sem que o aspecto conheça o service.

### Advice

O código que o aspecto executa no ponto de junção. Todos aqui são **around**: recebem o
ponto de junção e a função `prosseguir`, e controlam o antes, o depois e o erro. O advice
de `auditar`, simplificado:

```python
def advice(ponto, prosseguir):
    try:
        resultado = prosseguir()               # executa o método original
    except Exception as erro:
        registrar(ponto, None, "erro", ...)    # "depois, com erro"
        raise                                  # o erro continua o caminho normal
    registrar(ponto, resultado, "sucesso", ...)  # "depois, com sucesso"
    return resultado
```

Um aspecto nunca derruba a operação: falhas dentro do advice são registradas no log e
ignoradas (`_seguro(...)`).

### Ponto de corte (pointcut)

A regra que **escolhe** os pontos de junção. Há duas formas no projeto:

1. **Nominal**, escrita como decorator acima do método. É a forma usada para auditoria e
   eventos, porque cada ação precisa dizer qual entidade e quais detalhes registrar:

   ```python
   # backend/app/services/ocorrencia_service.py
   @auditar(
       "ocorrencia.criar",
       entidade="ocorrencia",
       entidade_id="resultado.id",
       ator="autor.id",
       anonimo_se="dados.anonima",          # denúncia anônima: a trilha não revela o autor
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
       ...  # só regra de negócio
   ```

   Repare que `detalhes` é uma **lista branca**: só o que foi declarado vai para o registro.
   O título, a descrição e os anexos da denúncia nunca são lidos pelo aspecto. Ainda assim,
   `sanitizar(...)` descarta qualquer chave com `senha`, `token`, `descricao`, `email` etc.

2. **Por padrão**, com `PontoDeCorte` (equivalente a `execution(public * app.services.*Service.*(..))` do AspectJ):

   ```python
   SERVICOS_DA_APLICACAO = PontoDeCorte(
       descricao="qualquer método público de qualquer classe *Service em app.services",
       modulo=r"^app\.services\.",
       classe=r"Service$",
   )
   ```

Pontos de corte aplicados hoje:

| Aspecto | Pontos de junção |
| --- | --- |
| `@auditar` | `OcorrenciaService.criar`, `.encaminhar`, `.atualizar_status`; `UsuarioService.criar`, `.atualizar`, `.excluir`, `.salvar_em_lote`; `AuthService.redefinir_senha` |
| `@publicar_evento` | `OcorrenciaService.criar` (`ocorrencia.criada`), `.encaminhar` (`ocorrencia.encaminhada`), `.atualizar_status` (`ocorrencia.status_alterado`) |
| `medir_desempenho` | todos os métodos públicos dos services (`SERVICOS_DA_APLICACAO`, limite `DESEMPENHO_LIMITE_MS`, padrão 500 ms) e, explicitamente, `OcorrenciaService.listar` com `@medir_desempenho(limite_ms=300)` |
| `AspectoHttp` | toda requisição HTTP e WebSocket |
| `FiltroDadosSensiveis` | loggers raiz, `uvicorn`, `uvicorn.access`, `uvicorn.error`, `app`, `httpx` |

Dois parâmetros do `@auditar` cobrem casos especiais:

- `itens` (operações em lote): o painel de usuários salva tudo por `POST /usuarios/lote`.
  Além do registro `auditoria.usuario.salvar_em_lote` (com as contagens), cada conta afetada
  gera o seu próprio `auditoria.usuario.editar` / `.excluir`, com o id da conta em
  `entidade_id` e, na edição, os NOMES dos campos alterados (nunca os valores). Todos têm o
  mesmo `request_id`. Lote que falha não gravou nada (tudo ou nada): fica só o registro do lote.
- `registrar_se`: `POST /auth/redefinir-senha` é pública; tentativa com um link que nem existe
  não é registrada (ator e entidade seriam nulos e um script anônimo encheria a trilha).
  Link existente mas usado/expirado continua registrado como erro, com o dono do link.
  O dono do link é consultado uma vez só por chamada (`PontoDeJuncao.lembrar`).

### Weaving (tecelagem)

O momento em que o advice é "costurado" ao ponto de junção. Python não tem um compilador
de aspectos como o AspectJ; a tecelagem é feita de três jeitos:

- **Por decorator, ao carregar a classe**: `@auditar(...)` troca o método por um envoltório
  (`_aplicar_advice`) que monta o `PontoDeJuncao` e chama o advice.
- **Por padrão, na subida da API**: `app/main.py` chama
  `tecer_aspectos_transversais(configuracoes.desempenho_limite_ms)`, que percorre as classes
  de `app.services`, aplica o `PontoDeCorte` e envolve cada método escolhido. É idempotente
  e pula métodos estáticos e os que já têm o aspecto (por isso `listar` mantém o limite de 300 ms).
  Cada envoltório guarda os aspectos aplicados em `__aspectos__`; por exemplo,
  `OcorrenciaService.criar.__aspectos__ == ("publicar_evento", "auditar", "medir_desempenho")`.
- **Por middleware, na camada HTTP**: `app.add_middleware(AspectoHttp)` envolve a aplicação
  inteira. É o último middleware registrado, portanto o mais externo.

### O aspecto HTTP e o mascaramento

Para cada requisição, `AspectoHttp`:

1. usa o `X-Request-ID` recebido (se for curto e seguro) ou gera um novo, e o devolve no
   cabeçalho da resposta (o CORS o expõe ao front);
2. abre o contexto da requisição (`contexto_requisicao`), onde a dependência de autenticação
   anota o usuário: é assim que `@auditar("usuario.criar")` sabe qual administrador agiu sem
   receber esse argumento;
3. registra `METODO /caminho -> status em X ms [request_id=...]` no logger `app.http`
   (só o caminho; a query string nunca vai para esse log).

O log de acesso do uvicorn gravava o JWT inteiro do WebSocket (`/ws/notificacoes?token=eyJ...`).
`instalar_mascaramento_de_logs()` (chamado na importação de `app.main` e no lifespan) põe o
`FiltroDadosSensiveis` nos loggers e nos handlers. A linha passa a ser:

```
INFO:     127.0.0.1:49161 - "WebSocket /ws/notificacoes?token=***" [accepted]
```

## 3. Eventos no RabbitMQ

### Formato (versionado)

```jsonc
{
  "id": "6f1c...",                 // também é o message_id e a chave de idempotência
  "tipo": "ocorrencia.criada",     // também é a routing key
  "versao": 1,
  "ocorrido_em": "2026-11-23T14:02:11.123+00:00",
  "ator_id": "a3b2..." ,           // null em denúncia anônima ou ação sem usuário
  "dados": {"entidade": "ocorrencia", "entidade_id": "...", "resultado": "sucesso",
            "request_id": "...", "tipo_ocorrencia": "denuncia", "protocolo": "#2026-0042", "status": "pendente"}
}
```

Os eventos de auditoria têm o tipo `auditoria.<acao>` (ex.: `auditoria.usuario.excluir`) e,
em `dados`, `acao`, `alvo`, `resultado` (`sucesso`/`erro`), `erro` (só o nome da exceção ou
a mensagem de negócio), `duracao_ms` e `detalhes`.

### Exchanges e filas

| Nome | Tipo | Para quê |
| --- | --- | --- |
| `unisos.eventos` | exchange **topic**, durável | Recebe todos os eventos |
| `unisos.auditoria` | fila durável, binding `#` | Grava todo evento na tabela `auditoria` |
| `unisos.metricas` | fila durável, binding `ocorrencia.*` | Conta ocorrências por tipo e registra indicadores no log (por processo, ver abaixo) |
| `unisos.eventos.dlx` | exchange fanout, durável | *Dead-letter exchange* das duas filas |
| `unisos.eventos.mortos` | fila durável | Mensagens rejeitadas, para análise |
| `notificacoes` | exchange fanout (já existia) | Aviso dos WebSockets entre instâncias; não mudou |

`auditoria.ocorrencia.criar` não casa com `ocorrencia.*` (o `*` vale uma palavra só), então
a fila de métricas recebe apenas os eventos de domínio.

### Fluxo de um evento, do produtor ao consumidor

```
POST /ocorrencias
  └─ AspectoHttp: request_id, contexto da requisição
      └─ OcorrenciaController.criar → OcorrenciaService.criar (envolvido pelos aspectos)
          1. regra de negócio + commit no PostgreSQL
          2. advice de @publicar_evento monta Evento(tipo="ocorrencia.criada")
          3. aspectos.entregar(evento)
               ├─ eventos.publicar(evento): agenda no event loop e ESPERA o "ack" do broker
               │     (publisher confirms, mensagem persistente, até 1,5 s)
               └─ sem broker / sem confirmação → gravar_evento(evento, "direto") no banco
          4. advice de @auditar faz o mesmo com "auditoria.ocorrencia.criar"
  RabbitMQ: unisos.eventos ──"#"──────────► unisos.auditoria ─► consumir_auditoria (um dos workers)
                           └─"ocorrencia.*"► unisos.metricas  ─► consumir_metricas
  consumir_auditoria: valida o JSON → INSERT ... ON CONFLICT (id) DO NOTHING → ack
```

Garantias:

- **Publisher confirms**: o canal de publicação é aberto com `publisher_confirms=True`; o
  aspecto só considera publicado depois do "ack" do broker. Sem ack, cai no fallback.
- **Fallback sem broker** (obrigatório): se o CloudAMQP cair, o aspecto grava a auditoria
  direto no banco, numa sessão própria (`origem = "direto"`). A operação nunca para.
- **Ack manual e prefetch**: cada consumidor recebe no máximo 10 mensagens sem ack
  (`PREFETCH`); o ack só sai depois do INSERT.
- **Broker degradado**: se uma confirmação não chega (TCP vivo, broker lento), o broker fica
  marcado como degradado por 30 s (`PAUSA_BROKER_DEGRADADO_SEGUNDOS`) e as publicações desse
  intervalo vão direto ao fallback, sem cada requisição esperar o timeout de novo.
- **Mensagem com erro não trava a fila**: JSON inválido vai direto para
  `unisos.eventos.mortos` (`reject(requeue=False)`). Falha ao gravar (ex.: queda curta do
  Neon) ganha novas tentativas no próprio consumidor, com espera crescente (1, 3, 10 e 30 s,
  `ESPERAS_NOVA_TENTATIVA_SEGUNDOS`); só se todas falharem a mensagem vai para a fila de mortos.
- **Reprocessamento da fila de mortos**: cada instância roda `reprocessar_mortos` 30 s depois
  de subir e a cada 10 min. Todo evento da fila de mortos também passou pela fila de auditoria
  (binding `#`), então ele é regravado na trilha (idempotente). Se o banco ainda falhar, a
  mensagem volta para o fim da fila (cabeçalho `x-unisos-reprocessamentos`) e a rodada para.
  Para rodar na hora: `cd backend; python -m scripts.reprocessar_eventos_mortos`
  (com `RABBITMQ_URL` e `DATABASE_URL` do ambiente).
- **Indicadores por processo**: a fila `unisos.metricas` é compartilhada, então com vários
  workers cada processo conta só a parte que recebeu, desde a sua subida (o log diz
  "Indicadores do processo <pid> (parciais ...)"). O total do sistema é a tabela `auditoria`
  (`GET /auditoria?tipo=ocorrencia.criada`).
- **Idempotência**: o id do evento é a chave primária da tabela `auditoria`. Reentrega,
  publicação duplicada ou dois workers recebendo o mesmo evento geram um único registro.
- **Vários workers/instâncias**: todos consomem da mesma fila durável; o RabbitMQ entrega
  cada mensagem a um só consumidor.

Os eventos reaproveitam a conexão aberta por `app/core/mensageria.py` (uma conexão AMQP
por processo, com canais separados para publicar e consumir).

## 4. Trilha de auditoria

- Tabela `auditoria` (`app/entities/registro_auditoria.py`), criada pelo `create_all`, com o
  índice `ix_auditoria_ocorrido_em_id` criado em `inicializacao_banco.py`.
- `GET /auditoria` (só admin): paginação por cursor como as outras listas (`limite`,
  `antes_de`, `antes_id`), filtro `tipo` por prefixo (`auditoria.usuario`,
  `auditoria.ocorrencia.criar`, `ocorrencia.`) e período (`desde`, `ate`, ISO 8601).
- Tela `/admin/auditoria` (menu "Auditoria"): data, ator, ação, entidade, resultado e "Carregar mais".

O que **nunca** é registrado: senhas (nem a nova, nem a inicial), tokens (JWT ou link de
redefinição), e-mails, título/descrição/anexos de ocorrências e o autor de denúncia anônima.

## 5. Como ver tudo no painel do RabbitMQ

1. Suba o broker: `docker compose up -d rabbitmq`.
2. Suba a API apontando para ele (`RABBITMQ_URL=amqp://unisos:uni12345@localhost:5672/`).
   No log deve aparecer: `Eventos: exchange 'unisos.eventos' pronta; consumindo 'unisos.auditoria' e 'unisos.metricas'.`
3. Abra <http://localhost:15672> (usuário `unisos`, senha `uni12345`):
   - **Exchanges → unisos.eventos → Bindings**: as filas `unisos.auditoria` (`#`) e `unisos.metricas` (`ocorrencia.*`);
   - **Queues → unisos.auditoria**: em *Consumers*, um por processo da API; o gráfico
     *Message rates* mostra *Publish*, *Deliver* e *Ack* quando alguém cria uma ocorrência;
   - **Queues → unisos.eventos.mortos**: mensagens rejeitadas; use *Get messages* para inspecionar;
   - para publicar um evento manualmente: **Exchanges → unisos.eventos → Publish message**,
     routing key `ocorrencia.criada`, payload no formato acima (com um `id` UUID novo). Ele
     aparece em `/admin/auditoria`; publicar de novo o mesmo `id` não duplica.
4. No CloudAMQP (produção), o mesmo painel fica em *RabbitMQ Manager* na página da instância.

Teste de ponta a ponta com broker real: `backend/testes/testar_eventos_rabbitmq.py`
(instruções no próprio arquivo).

## 6. Configuração

| Variável | Padrão | Efeito |
| --- | --- | --- |
| `RABBITMQ_URL` | `amqp://unisos:uni12345@localhost:5672/` | Broker (já existia). Sem ele, auditoria vai direto ao banco |
| `DESEMPENHO_LIMITE_MS` | `500` | Limite do `medir_desempenho` tecido em todos os services |
