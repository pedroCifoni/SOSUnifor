from contextlib import asynccontextmanager

import jwt
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import configuracoes, obter_origens_cors, validar_configuracao_de_producao
from app.core.database import Base, engine
from app.core.security import gerar_hash_senha
from app.core.schema_legado import ativar_limite_unifor_revisado, atualizar_credenciais_legadas, atualizar_ocorrencias_legadas
from app.models.credential import Usuario
from app.core.notificacoes_tempo_real import gerenciador_notificacoes
from app.models.sistema import Notificacao, Ocorrencia
from app.routes.api import PASTA_ARQUIVOS, rotas_api
from sqlalchemy import select
from sqlalchemy.orm import Session


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    validar_configuracao_de_producao()
    atualizar_credenciais_legadas()
    atualizar_ocorrencias_legadas()
    Base.metadata.create_all(bind=engine)
    ativar_limite_unifor_revisado()
    criar_usuarios_iniciais()
    yield


app = FastAPI(title="UniSOS API", version="1.0.0", lifespan=ciclo_de_vida)
app.add_middleware(
    CORSMiddleware,
    allow_origins=obter_origens_cors(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(rotas_api)


@app.websocket("/ws/notificacoes")
async def acompanhar_notificacoes(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return
    try:
        dados = jwt.decode(token, configuracoes.jwt_secret, algorithms=[configuracoes.jwt_algorithm])
        usuario_id = dados["sub"]
        with Session(engine) as banco:
            usuario = banco.get(Usuario, usuario_id)
            if usuario is None or not usuario.ativo:
                await websocket.close(code=1008)
                return
    except (jwt.InvalidTokenError, KeyError, ValueError):
        await websocket.close(code=1008)
        return
    await gerenciador_notificacoes.conectar(usuario.id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        gerenciador_notificacoes.desconectar(usuario.id, websocket)


def criar_usuarios_iniciais() -> None:
    """Cria contas de desenvolvimento somente quando o banco está vazio."""
    contas = [
        ("Eduardo Costa", "eduardo.costa@unifor.br", "usuario"),
        ("Administrador", "admin@unifor.br", "admin"),
        ("Equipe Segurança", "seguranca@unifor.br", "seguranca"),
        ("Técnico de Informática", "tecnico@unifor.br", "tecnico"),
    ]
    with Session(engine) as banco:
        emails_existentes = set(banco.scalars(select(Usuario.email)).all())
        for nome, email, perfil in contas:
            if email not in emails_existentes:
                banco.add(Usuario(nome=nome, email=email, senha_hash=gerar_hash_senha("123456"), tipo_usuario=perfil))
        banco.commit()


@app.get("/health")
def verificar_saude() -> dict[str, str]:
    return {"service": "auth-service", "status": "healthy"}
