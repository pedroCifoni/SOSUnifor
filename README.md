<p align="center">
  <img src="public/unifor-logo-horizontal.svg" alt="UNIFOR" height="56">
</p>

<h1 align="center">Uni SOS</h1>

<p align="center">
  Alertas de emergência, chamados de manutenção e denúncias no campus da Universidade de Fortaleza.
</p>

<p align="center">
  <a href="https://sos-unifor-front-end.vercel.app"><strong>Acessar o sistema</strong></a> ·
  <a href="https://sosunifor.onrender.com/docs">Documentação da API</a> ·
  <a href="docs/uni-sos-documentacao.pdf">Documentação do projeto (PDF)</a>
</p>

---

## Sobre

O Uni SOS reúne em um só lugar três formas de pedir ajuda dentro da UNIFOR:

| | Funcionalidade | Como funciona |
|---|---|---|
| 🚨 | **SOS** | O usuário segura o botão por 2 segundos. A API identifica em qual bloco ou área do campus ele está e alerta o administrador e a Equipe de Segurança na hora. |
| 🔧 | **Manutenção** | Abertura de chamado com local, descrição e foto ou vídeo. |
| 🛡️ | **Denúncia** | Registro de furto, assédio, vandalismo e outros, com opção de denúncia anônima. |

O **administrador** faz a triagem de todas as ocorrências e encaminha cada uma para a equipe responsável (**Segurança** ou **Técnico**), que aceita e conclui o atendimento. Em cada etapa, quem abriu a ocorrência recebe uma notificação em tempo real e pode acompanhar o histórico completo.

### Perfis

| Perfil | O que faz |
|---|---|
| Usuário | Aciona SOS, abre chamados e denúncias e acompanha as próprias ocorrências |
| Administrador | Faz a triagem e o encaminhamento, gerencia usuários e desenha as áreas do campus |
| Segurança | Recebe as ocorrências encaminhadas, aceita e conclui o atendimento |
| Técnico | Recebe os chamados de suporte técnico encaminhados, aceita e conclui o atendimento |

Não existe cadastro público: as contas são criadas pelo administrador no painel.

## Arquitetura

```
┌────────────────────┐   HTTPS / WebSocket   ┌────────────────────┐        ┌──────────────────┐
│  Front-end (SPA)   │ ────────────────────▶ │   API (FastAPI)    │ ─────▶ │ PostgreSQL       │
│  React + Vite      │                       │   JWT + Uvicorn    │        │                  │
│  Vercel            │                       │   Render           │        │ Neon             │
└────────────────────┘                       └────────────────────┘        └──────────────────┘
```

| Camada | Tecnologias | Hospedagem |
|---|---|---|
| Front-end | React 19, TypeScript, Vite, Tailwind CSS, React Router, MapLibre GL, Terra Draw | [Vercel](https://sos-unifor-front-end.vercel.app) |
| API | Python 3.12, FastAPI, SQLAlchemy, Pydantic, PyJWT, Argon2 | [Render](https://sosunifor.onrender.com/docs) |
| Banco | PostgreSQL 17 (serverless) | Neon |

A API cria as tabelas, os índices e os usuários iniciais sozinha na primeira vez que sobe, então não é preciso rodar migração manual.

## Estrutura do repositório

```
├── src/                              # Front-end React
│   ├── api/                          # Cliente HTTP e configuração da URL da API
│   ├── components/                   # Layout, mapa do campus, modais e UI
│   ├── contexts/ hooks/              # Autenticação, notificações e toasts
│   ├── pages/                        # Telas por perfil e funcionalidade
│   ├── routes/                       # Rotas e proteção por perfil
│   └── services/                     # Chamadas à API por recurso
├── backend/                          # API FastAPI
│   ├── app/
│   │   ├── controllers/              # Rotas HTTP e WebSocket: recebem a requisição e chamam o service
│   │   ├── services/                 # Regras de negócio e controle da transação
│   │   ├── repositories/             # Consultas e gravações no banco
│   │   ├── entities/                 # Tabelas (modelos SQLAlchemy)
│   │   ├── dtos/                     # Formatos de entrada e saída da API (Pydantic)
│   │   ├── core/                     # Configuração, banco, segurança/JWT, e-mail, erros e WebSocket
│   │   └── main.py                   # Monta a aplicação
│   ├── scripts/                      # Tarefas manuais (importar áreas do OSM, testar conexão)
│   ├── testes/                       # Testes automatizados
│   │   └── carga/                    # Teste de carga com Locust (locustfile.py e popular_banco.py)
│   ├── requirements.txt              # Dependências Python da API
│   └── .env.example                  # Modelo de variáveis de ambiente da API
├── docker-compose.yml                # PostgreSQL, Mailpit e RabbitMQ para desenvolvimento local
├── vercel.json                       # Rewrite da SPA na Vercel
└── docs/                             # Documentação e diagramas do projeto
```

### Camadas do back-end

```
Requisição → Controller → Service → Repository → Banco
                 │            │
               DTOs      Entities + regras
```

- **Controller:** só lida com HTTP e WebSocket. Valida a entrada pelo DTO, identifica o usuário e devolve o DTO de resposta.
- **Service:** concentra as regras, como quem pode ver ou alterar cada ocorrência, a geração do protocolo, os envios de e-mail, as notificações e a identificação do local do SOS. Lança erros de negócio (`backend/app/core/excecoes.py`), que viram respostas HTTP.
- **Repository:** é o único ponto que monta consultas SQLAlchemy. Não faz commit.

## Rodar localmente

**Pré-requisitos:** Node.js 20 ou mais novo, Python 3.12 ou mais novo e Docker Desktop.

**1. Banco de dados e e-mail local (PostgreSQL + Mailpit)**

```powershell
Copy-Item .env.example .env
docker compose up -d
```

O `docker-compose.yml` sobe o PostgreSQL na porta `5433` e o **Mailpit** (caixa de e-mail falsa para desenvolvimento) com interface web em `http://localhost:8025` e servidor SMTP na porta `1025`.

**2. API**, em `http://127.0.0.1:8000`

```powershell
cd backend
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Para importar do OpenStreetMap os prédios da UNIFOR, ainda na pasta `backend`, rode:

```powershell
.\.venv\Scripts\python.exe -m scripts.importar_areas_unifor_osm
```

**3. Front-end**, em `http://localhost:5173`

Na raiz do repositório:

```powershell
npm install --legacy-peer-deps
npm run dev
```

Para o front local usar a API local, defina `VITE_API_URL=http://127.0.0.1:8000` no `.env` da raiz.

### Testar pelo celular na mesma rede

O script `npm run dev` já roda o Vite com `--host 0.0.0.0`, então o front fica acessível na rede local pelo IP da sua máquina (por exemplo, `http://192.168.0.15:5173`). Para o celular alcançar também a API local, suba o Uvicorn com `--host 0.0.0.0` e aponte `VITE_API_URL` para `http://<IP-DA-MAQUINA>:8000` — em desenvolvimento, a API já aceita CORS vindo de IPs da rede local (`192.168.x.x` e `10.x.x.x`).

> **GPS no celular:** a API de geolocalização do navegador só funciona em **HTTPS** ou `localhost`. Ao abrir pelo IP em HTTP na rede local, o GPS real fica bloqueado pelo navegador; deixe `VITE_SOS_USAR_GPS` desativada para usar o ponto fixo no Bloco C.

### Contas iniciais de desenvolvimento

A API cria estas contas quando elas ainda não existem. A senha inicial de todas é `123456`; **troque-a em qualquer ambiente publicado.**

| Perfil | E-mail |
|---|---|
| Administrador | `admin@unifor.br` |
| Usuário | `eduardo.costa@unifor.br` |
| Segurança | `seguranca@unifor.br` |
| Técnico de Informática | `tecnico@unifor.br` |

## E-mails

A API envia e-mails via SMTP nestas situações:

- **Boas-vindas:** quando o administrador cria uma nova conta, o usuário recebe um e-mail com seu acesso, a senha inicial e o botão **Confirmar e-mail**.
- **Confirmação de e-mail:** contas criadas pelo administrador só entram depois de confirmar o e-mail (link de uso único válido por **48 horas**; o login responde `403` com `"codigo": "email_nao_verificado"`). Um novo link pode ser pedido na tela de login (até 3 por hora) ou pelo administrador; trocar o e-mail de uma conta exige confirmar de novo. Contas que já existiam quando a verificação foi criada continuam entrando normalmente.
- **Esqueci minha senha:** envia um link de redefinição de uso único válido por **30 minutos** (concluir a redefinição também confirma o e-mail).
- **Aviso de senha alterada:** confirma para o usuário que a senha da conta foi modificada.

Em desenvolvimento local, o `docker-compose.yml` sobe o **Mailpit** (`SMTP_HOST=localhost`, `SMTP_PORT=1025`). Tudo o que a API envia aparece em `http://localhost:8025`, sem enviar e-mails reais. Se `SMTP_HOST` ficar vazio em desenvolvimento, o conteúdo do e-mail é registrado apenas no log da API.

### Configurar Gmail em produção (senha de app)

O Gmail não aceita a senha normal da conta em conexões SMTP. Para usar uma conta Google:

1. Ative a **verificação em duas etapas** na conta Google.
2. Acesse [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) e gere uma **senha de app**.
3. Configure as variáveis SMTP no servidor da API:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_STARTTLS=true
SMTP_SSL=false
SMTP_USUARIO=seu-email@gmail.com
SMTP_SENHA=xxxx xxxx xxxx xxxx
SMTP_REMETENTE=Uni SOS <seu-email@gmail.com>
```

## Variáveis de ambiente

### Front-end (`.env` na raiz, ou Environment Variables na Vercel)

| Variável | Descrição |
|---|---|
| `VITE_API_URL` | URL base da API, sem barra no final |
| `VITE_SOS_USAR_GPS` | `true` faz o SOS usar o GPS real. Sem ela, o SOS usa um ponto fixo no Bloco C, para testes fora do campus. |
| `VITE_MAP_STYLE_URL` | Opcional. Estilo de mapa do provedor da instituição. |
| `VITE_CONTATO_DPO` | E-mail do encarregado de dados (LGPD) exibido na Política de Privacidade (`/privacidade`). Sem ela, aparece um endereço provisório marcado como "a definir". |

Variáveis `VITE_*` entram no código no momento do build e ficam públicas. Depois de alterá-las na Vercel, faça um novo deploy.

### API (`backend/.env`, ou Environment no Render)

Veja `backend/.env.example` para os valores padrão de desenvolvimento.

**Aplicação e autenticação**

| Variável | Descrição |
|---|---|
| `AMBIENTE` | `desenvolvimento` ou `producao` |
| `DATABASE_URL` | `postgresql+psycopg://usuario:senha@host:5432/banco` |
| `JWT_SECRET` | Chave de assinatura dos tokens, com pelo menos 32 caracteres |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Validade do token em minutos. Padrão: `60`. |
| `CORS_ORIGINS` | Domínios do front separados por vírgula, sem caminho e sem barra no final |
| `FRONTEND_URL` | Endereço público do front-end, usado para montar os links enviados por e-mail |

**Banco de dados e escalabilidade**

| Variável | Descrição |
|---|---|
| `DB_POOL_SIZE` | Conexões permanentes no pool por processo/worker da API. Padrão: `10`. |
| `DB_MAX_OVERFLOW` | Conexões extras permitidas acima do pool em picos. Padrão: `20`. |
| `DB_POOL_TIMEOUT` | Segundos aguardando uma conexão livre do pool antes de responder erro. Padrão: `10`. |
| `DB_POOL_RECYCLE` | Segundos até reciclar uma conexão (importante no Neon, que encerra conexões ociosas). Padrão: `300`. |
| `DB_PREPARED_STATEMENTS` | Padrão: `true`. Defina como `false` se o pooler em modo transação (PgBouncer/Neon `-pooler`) reclamar de prepared statements. |
| `RABBITMQ_URL` | Broker que distribui os avisos em tempo real entre as instâncias da API. Em dev: o RabbitMQ do docker-compose (`amqp://unisos:uni12345@localhost:5672/`); em produção: URL `amqps://` do CloudAMQP. Sem broker, cada processo avisa só as suas conexões. |

**E-mail (SMTP)**

| Variável | Descrição |
|---|---|
| `BREVO_API_KEY` | Envia os e-mails pela API HTTPS da Brevo em vez de SMTP. **Obrigatória no plano gratuito do Render**, que bloqueia as portas de SMTP. O remetente (`SMTP_REMETENTE`) precisa estar verificado na Brevo. |
| `SMTP_HOST` | Servidor SMTP (em dev: `localhost` para o Mailpit; em produção: ex. `smtp.gmail.com`). Sem ela, nada é enviado. |
| `SMTP_PORT` | Porta SMTP (`1025` no Mailpit; `587` com STARTTLS). |
| `SMTP_USUARIO` | Usuário de autenticação SMTP (vazio no Mailpit). |
| `SMTP_SENHA` | Senha ou senha de app SMTP (vazio no Mailpit). |
| `SMTP_REMETENTE` | Remetente exibido nos e-mails (ex.: `Uni SOS <nao-responda@unifor.br>`). |
| `SMTP_STARTTLS` | `true` para negociar TLS na porta 587 (`false` no Mailpit). |
| `SMTP_SSL` | `true` para SMTP sobre SSL direto (porta 465). Padrão: `false`. |

**Privacidade (LGPD)**: veja [docs/LGPD.md](docs/LGPD.md).

| Variável | Descrição |
|---|---|
| `RETENCAO_NOTIFICACOES_LIDAS_DIAS` | Notificações já lidas são apagadas depois destes dias (rotina executada a cada subida da API). Padrão: `180`. |
| `RETENCAO_TOKENS_VENCIDOS_HORAS` | Links de redefinição de senha vencidos são apagados depois destas horas além do vencimento. Padrão: `24`. |

## Deploy

| Serviço | Configuração |
|---|---|
| **Vercel** | Front-end (Vite) na raiz do repositório · `VITE_API_URL` apontando para a API no Render |
| **Render** | Web Service · Root Directory `backend` · Build `pip install -r requirements.txt` · Start `uvicorn app.main:app --host 0.0.0.0 --port $PORT` · `PYTHON_VERSION=3.12.7` |
| **Neon** | PostgreSQL serverless · `DATABASE_URL` com o prefixo `postgresql+psycopg://` (veja abaixo qual endpoint usar) |

Um push na `main` atualiza o front e a API.

### Neon

- Hoje a produção usa a connection string **sem** connection pooling (conexão direta), com o prefixo trocado para `postgresql+psycopg://`.
- Ao escalar para várias instâncias/workers, cada processo abre até `DB_POOL_SIZE + DB_MAX_OVERFLOW` conexões. Se isso se aproximar do limite de conexões do Neon, troque `DATABASE_URL` pelo endpoint **com** `-pooler` (ex.: `ep-xxx-pooler.sa-east-1.aws.neon.tech`); se aparecerem erros de *prepared statement*, defina `DB_PREPARED_STATEMENTS=false`.

### Tempo real entre instâncias (RabbitMQ)

(O sistema pode funcionar mesmo sem o broker, com as notificações chegando pelo polling de 60 s.)

1. Crie uma instância no [CloudAMQP](https://www.cloudamqp.com/) (plano free).
2. Copie a URL `amqps://...`.
3. No Render, adicione a variável `RABBITMQ_URL` com essa URL.
4. Faça o redeploy.

Se o log da API mostrar `RabbitMQ conectado`, está funcionando.

### Variáveis obrigatórias em produção

Com `AMBIENTE=producao`, a API valida a configuração na subida (`validar_configuracao_de_producao` em `backend/app/core/config.py`) e se recusa a iniciar se algo inseguro for detectado:

- `AMBIENTE=producao`
- `JWT_SECRET` — forte e exclusiva, com pelo menos 32 caracteres e sem a palavra `desenvolvimento`
- `DATABASE_URL` — credencial exclusiva (não pode usar a senha local `uni12345`)
- `CORS_ORIGINS` — apenas domínios HTTPS da aplicação (sem `http://localhost` ou `http://127.*`)
- `FRONTEND_URL` — URL pública do front na Vercel, para que os links nos e-mails apontem para o endereço correto
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USUARIO`, `SMTP_SENHA`, `SMTP_REMETENTE`, `SMTP_STARTTLS` / `SMTP_SSL` — necessárias para envio de boas-vindas e redefinição de senha (em produção, sem `SMTP_HOST` o conteúdo do e-mail nunca vai para o log)

## Teste de carga

O roteiro de carga em `backend/testes/carga/locustfile.py` usa [Locust](https://locust.io/) para simular vários usuários consultando notificações, ocorrências, áreas do campus, identificação de local e login.

Instale o Locust no ambiente virtual do back-end:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install locust
```

Com a API rodando localmente (ex.: `http://127.0.0.1:8000`), execute pelo painel web (`http://localhost:8089`):

```powershell
.\.venv\Scripts\locust -f testes\carga\locustfile.py --host http://127.0.0.1:8000
```

Ou em modo sem interface (`--headless`):

```powershell
.\.venv\Scripts\locust -f testes\carga\locustfile.py --host http://127.0.0.1:8000 --headless -u 20 -r 5 -t 30s
```

Opcionalmente, `CARGA_EMAIL` e `CARGA_SENHA` definem a conta usada pelos usuários simulados (padrão: `admin@unifor.br` / `123456`), e `backend/testes/carga/popular_banco.py` popula um banco local dedicado chamado `unisos_carga` com volume realista de dados.

> **Atenção:** rode testes de carga **apenas contra o ambiente local** — nunca contra a API de produção. O roteiro propositalmente **não chama rotas que enviam e-mail** (nem cria ocorrências), para evitar envios reais de SMTP e não poluir o banco.

## Mapa do campus

O SOS só é aceito dentro do **limite do campus**. Para editar as áreas, o administrador abre **Áreas do Campus** e desenha os polígonos no mapa. Quando um ponto cai em mais de uma área, vale a de maior prioridade. Fora de um bloco, o SOS informa o bloco mais próximo, como "Praça Central · próximo ao Bloco C".

Blocos que não estão mapeados no OpenStreetMap, como A, G, L e O, e as portarias precisam ser desenhados manualmente.

## Limitações conhecidas

- **Plano gratuito do Render:** a API hiberna após uns 15 minutos sem uso, e o primeiro acesso depois disso leva de 30 a 50 segundos.
- **Anexos:** ficam no disco do servidor e se perdem a cada novo deploy no Render. A evolução prevista é usar armazenamento externo.

---

<p align="center">Projeto acadêmico desenvolvido na Universidade de Fortaleza.</p>
