# Padrões de projeto no Uni SOS

Cada padrão abaixo resolve um problema concreto do sistema. Os caminhos são relativos a `backend/app`.

| # | Padrão | Categoria | Onde | Problema que resolve |
|---|---|---|---|---|
| 1 | **Strategy** | Comportamental | `core/email.py` (`EstrategiaEnvioEmail`, `EnvioBrevo`, `EnvioSmtp`, `EnvioSomenteLog`) · `core/exportacao.py` (`Exportador`, `ExportadorCsv`, `ExportadorPdf`) | Trocar o canal de e-mail (Render bloqueia SMTP; local usa Mailpit) e o formato de exportação sem `if` espalhado pelo código |
| 2 | **Factory** (Simple Factory / Factory Method) | Criacional | `core/email.py` (`criar_estrategia_email`) · `core/exportacao.py` (`criar_exportador`) | Um único lugar decide qual estratégia instanciar a partir da configuração ou do formato pedido |
| 3 | **Adapter** | Estrutural | `core/email.py` (`EnvioBrevo` adapta a API HTTP da Brevo; `EnvioSmtp` adapta o `smtplib`) | Duas APIs bem diferentes passam a ter a mesma interface `enviar(destinatario, assunto, texto, html)` |
| 4 | **Observer / Publish-Subscribe** | Comportamental | `core/eventos.py` (`assinar`, `notificar_localmente`, fila `unisos.reacoes`) · `services/boas_vindas_service.py` | Quem ativa a conta não precisa conhecer quem reage (boas-vindas, auditoria, métricas). Novos observadores entram sem mudar o produtor |
| 5 | **Repository** | Arquitetural (DDD) | `repositories/*.py` | Isola as consultas SQLAlchemy; services não montam SQL |
| 6 | **Decorator / Proxy** (via POA) | Estrutural | `core/aspectos.py` (`@auditar`, `@publicar_evento`, `medir_desempenho`) | Acrescenta auditoria, eventos e medição a um método sem alterar seu código |
| 7 | **Singleton** (de módulo) | Criacional | `core/config.py` (`configuracoes`) · `core/tempo_real.py` (`gerenciador_notificacoes`) | Uma única configuração e um único registro de WebSockets por processo |
| 8 | **DTO** (Data Transfer Object) | Arquitetural | `dtos/*.py` | Separa o contrato da API das entidades do banco; valida a entrada |
| 9 | **Dependency Injection** | Arquitetural | `controllers/dependencias.py` (`Depends`) | Controllers recebem services prontos; nos testes, as dependências são trocadas |
| 10 | **Facade / Service Layer** | Estrutural | `services/*Service` | O controller chama uma operação de negócio (`OcorrenciaService.criar`) que orquestra repositórios, notificações, e-mail e eventos |

## Exemplos

### Strategy + Factory + Adapter (e-mail)

```python
class EstrategiaEnvioEmail(Protocol):          # Strategy (contrato)
    def enviar(self, destinatario, assunto, texto, html=None) -> None: ...

class EnvioBrevo:   ...                         # Adapter da API HTTP da Brevo
class EnvioSmtp:    ...                         # Adapter do smtplib

def criar_estrategia_email(config) -> EstrategiaEnvioEmail:   # Factory
    if config.brevo_api_key: return EnvioBrevo(config)
    if config.smtp_host:     return EnvioSmtp(config)
    return EnvioSomenteLog(config)
```

### Strategy + Factory (exportação)

```python
documento = DocumentoTabular(titulo="Usuários", cabecalho=(...), linhas=...)
exportador = criar_exportador("pdf")          # ou "csv"
conteudo = exportador.gerar(documento)
```

Um formato novo (XLSX, por exemplo) é uma classe nova registrada na factory; nenhum service muda.

### Observer (eventos de domínio)

```python
@assinar("usuario.ativado")
def dar_boas_vindas(evento: Evento) -> None: ...
```

O produtor (`VerificacaoEmailService._ativar_conta`) só publica `usuario.ativado`. Com o RabbitMQ
no ar, o observador roda pelo consumidor da fila `unisos.reacoes`; sem broker, roda no próprio
processo. Em ambos os casos o produtor não conhece o observador.

## Testes

- `testes/unidade/test_email.py` — a factory escolhe a estratégia certa; `enviar_email` delega.
- `testes/unidade/test_exportacao.py` — factory e as duas estratégias de exportação.
- `testes/unidade/test_observador.py` — casamento de routing keys e isolamento de falhas entre observadores.
- `testes/unidade/test_verificacao_email.py` — ativação publica o evento e o observador dá as boas-vindas uma única vez.
