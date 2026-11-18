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

O **administrador** faz a triagem de todas as ocorrências e encaminha cada uma para a **Equipe de Segurança**, que aceita e conclui o atendimento. Em cada etapa, quem abriu a ocorrência recebe uma notificação em tempo real e pode acompanhar o histórico completo.

### Perfis

| Perfil | O que faz |
|---|---|
| Usuário | Aciona SOS, abre chamados e denúncias e acompanha as próprias ocorrências |
| Administrador | Faz a triagem e o encaminhamento, gerencia usuários e desenha as áreas do campus |
| Segurança | Recebe as ocorrências encaminhadas, aceita e conclui o atendimento |

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
| Banco | PostgreSQL 17 | Neon |

A API cria as tabelas e os usuários iniciais sozinha na primeira vez que sobe, então não é preciso rodar migração manual.

## Estrutura do repositório

```
├── src/                              # Front-end React
│   ├── api/                          # Cliente HTTP e configuração da URL da API
│   ├── components/                   # Layout, mapa do campus, modais e UI
│   ├── contexts/ hooks/              # Autenticação, notificações e toasts
│   ├── pages/                        # Telas por perfil e funcionalidade
│   ├── routes/                       # Rotas e proteção por perfil
│   └── services/                     # Chamadas à API por recurso
├── backend/services/auth-service/    # API FastAPI
│   ├── app/
│   │   ├── controllers/              # Rotas HTTP e WebSocket: recebem a requisição e chamam o service
│   │   ├── services/                 # Regras de negócio e controle da transação
│   │   ├── repositories/             # Consultas e gravações no banco
│   │   ├── entities/                 # Tabelas (modelos SQLAlchemy)
│   │   ├── dtos/                     # Formatos de entrada e saída da API (Pydantic)
│   │   ├── core/                     # Configuração, banco, segurança/JWT, erros e WebSocket
│   │   └── main.py                   # Monta a aplicação
│   ├── scripts/                      # Tarefas manuais (importar áreas do OSM, testar conexão)
│   ├── testes/                       # Testes HTTP de ponta a ponta
│   └── alembic/                      # Migrações
├── docker-compose.yml                # PostgreSQL para desenvolvimento local
├── vercel.json                       # Rewrite da SPA na Vercel
└── docs/                             # Documentação do projeto
```

### Camadas do back-end

```
Requisição → Controller → Service → Repository → Banco
                 │            │
               DTOs      Entities + regras
```

- **Controller:** só lida com HTTP. Valida a entrada pelo DTO, identifica o usuário e devolve o DTO de resposta.
- **Service:** concentra as regras, como quem pode ver ou alterar cada ocorrência, a geração do protocolo, as notificações e a identificação do local do SOS. Lança erros de negócio (`core/excecoes.py`), que viram respostas HTTP.
- **Repository:** é o único ponto que monta consultas SQLAlchemy. Não faz commit.

## Rodar localmente

**Pré-requisitos:** Node.js 20 ou mais novo, Python 3.12 ou mais novo e Docker Desktop.

**1. Banco de dados**

```powershell
Copy-Item .env.example .env
docker compose up -d
```

**2. API**, em `http://127.0.0.1:8000`

```powershell
cd backend\services\auth-service
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Para importar do OpenStreetMap os prédios da UNIFOR, ainda na pasta da API, rode:

```powershell
.\.venv\Scripts\python.exe -m scripts.importar_areas_unifor_osm
```

**3. Front-end**, em `http://localhost:5173`

```powershell
npm install --legacy-peer-deps
npm run dev
```

Para o front local usar a API local, defina `VITE_API_URL=http://127.0.0.1:8000` no `.env` da raiz.

### Contas iniciais

A API cria estas contas quando elas ainda não existem. A senha inicial é `123456`; **troque-a em qualquer ambiente publicado.**

| Perfil | E-mail |
|---|---|
| Administrador | `admin@unifor.br` |
| Segurança | `seguranca@unifor.br` |
| Usuário | `eduardo.costa@unifor.br` |

## Variáveis de ambiente

**Front-end** (`.env` na raiz, ou Environment Variables na Vercel)

| Variável | Descrição |
|---|---|
| `VITE_API_URL` | URL base da API, sem barra no final |
| `VITE_SOS_USAR_GPS` | `true` faz o SOS usar o GPS real. Sem ela, o SOS usa um ponto fixo no Bloco C, para testes fora do campus. |
| `VITE_MAP_STYLE_URL` | Opcional. Estilo de mapa do provedor da instituição. |

Variáveis `VITE_*` entram no código no momento do build e ficam públicas. Depois de alterá-las na Vercel, faça um novo deploy.

**API** (`backend/services/auth-service/.env`, ou Environment no Render)

| Variável | Descrição |
|---|---|
| `AMBIENTE` | `desenvolvimento` ou `producao` |
| `DATABASE_URL` | `postgresql+psycopg://usuario:senha@host:5432/banco` |
| `JWT_SECRET` | Chave de assinatura dos tokens, com pelo menos 32 caracteres |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Validade do token. O padrão é `60`. |
| `CORS_ORIGINS` | Domínios do front separados por vírgula, sem caminho e sem barra no final |

Com `AMBIENTE=producao`, a API se recusa a iniciar se a `JWT_SECRET` for fraca, se a senha do banco for a de desenvolvimento ou se o CORS apontar para `localhost`.

## Deploy

| Serviço | Configuração |
|---|---|
| **Neon** | Use a connection string *sem* connection pooling e troque o prefixo por `postgresql+psycopg://` |
| **Render** | Web Service · Root Directory `backend/services/auth-service` · Build `pip install -r requirements.txt` · Start `uvicorn app.main:app --host 0.0.0.0 --port $PORT` · `PYTHON_VERSION=3.12.7` |
| **Vercel** | Framework Vite na raiz do repositório · `VITE_API_URL` apontando para o Render |

Um push na `main` atualiza o front e a API.

### Carga inicial do banco

Depois que a API subir pela primeira vez, rode [`seed_unifor.sql`](backend/services/auth-service/seed_unifor.sql) no SQL Editor do Neon. O script insere:

- **73 áreas do campus** tiradas do OpenStreetMap: o limite da UNIFOR, 19 blocos, a biblioteca, a reitoria, os estacionamentos, as praças e as quadras.
- **8 ocorrências de exemplo**, com histórico e notificações.

Pode rodar mais de uma vez sem duplicar dados.

## Mapa do campus

O SOS só é aceito dentro do **limite do campus**. Para editar as áreas, o administrador abre **Áreas do Campus** e desenha os polígonos no mapa. Quando um ponto cai em mais de uma área, vale a de maior prioridade. Fora de um bloco, o SOS informa o bloco mais próximo, como "Praça Central · próximo ao Bloco C".

Blocos que não estão mapeados no OpenStreetMap, como A, G, L e O, e as portarias precisam ser desenhados manualmente.

## Limitações conhecidas

- **Plano gratuito do Render:** a API hiberna após uns 15 minutos sem uso, e o primeiro acesso depois disso leva de 30 a 50 segundos.
- **Anexos:** ficam no disco do servidor e se perdem a cada novo deploy no Render. A evolução prevista é usar armazenamento externo.

---

<p align="center">Projeto acadêmico desenvolvido na Universidade de Fortaleza.</p>
