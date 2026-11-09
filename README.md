# Uni SOS

Aplicação para abertura e acompanhamento de chamados de manutenção, denúncias e alertas SOS no campus. Este repositório contém o front-end e o back-end.

## Executar localmente (PowerShell)

Use três terminais, a partir da raiz do repositório.

1. Configure e inicie o PostgreSQL:

```powershell
Copy-Item .env.example .env
docker compose up -d
```

2. Configure e inicie a API:

```powershell
cd backend\services\auth-service
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

3. Na raiz do repositório, instale e inicie o front-end:

```powershell
npm install --legacy-peer-deps
npm run dev
```

Abra `http://localhost:5173`. O front-end usa `http://127.0.0.1:8000` como API por padrão. Configure `VITE_API_URL` no `.env` da raiz para usar outra URL.

## Contas de desenvolvimento

A API cria estas contas quando ainda não existem, todas com senha `123456`:

| Perfil | E-mail |
| --- | --- |
| Usuário | eduardo.costa@unifor.br |
| Administrador | admin@unifor.br |
| Segurança | seguranca@unifor.br |
| Técnico | tecnico@unifor.br |

## API

A documentação interativa está em `http://127.0.0.1:8000/docs`. A API oferece autenticação JWT, gestão de usuários, ocorrências, notificações, áreas do campus e envio de anexos. O servidor valida as permissões em cada rota.

Não existe cadastro público: um administrador autenticado cria as contas pelo painel administrativo. A segurança acessa os atendimentos encaminhados para sua equipe.

## Estrutura

- `src/`: aplicação React, páginas, componentes, serviços e cliente da API.
- `backend/services/auth-service/`: API FastAPI e configuração do banco.
- `docker-compose.yml`: banco PostgreSQL para desenvolvimento local.
- `docs/`: documentação do projeto.

## Mapa do campus

Entre como administrador e abra **Áreas do Campus** no menu. Cadastre primeiro o polígono do limite geral da Unifor e, em seguida, os polígonos dos blocos, portarias e estacionamentos. O SOS usa o GPS do dispositivo e a API identifica o local pelas áreas cadastradas.
