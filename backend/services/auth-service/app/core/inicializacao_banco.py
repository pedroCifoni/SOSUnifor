"""Preparação do banco na subida da API.

Ajusta tabelas de versões antigas sem apagar dados, cria as tabelas que faltam
e cadastra as contas iniciais quando ainda não existem.
"""

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

import app.entities  # noqa: F401  (registra as tabelas em Base.metadata)
from app.core.database import Base, engine
from app.core.seguranca import gerar_hash_senha
from app.entities.usuario import Usuario


CONTAS_INICIAIS = [
    ("Eduardo Costa", "eduardo.costa@unifor.br", "usuario"),
    ("Administrador", "admin@unifor.br", "admin"),
    ("Equipe Segurança", "seguranca@unifor.br", "seguranca"),
    ("Técnico de Informática", "tecnico@unifor.br", "tecnico"),
]
SENHA_INICIAL = "123456"


def inicializar_banco() -> None:
    atualizar_credenciais_legadas()
    atualizar_ocorrencias_legadas()
    Base.metadata.create_all(bind=engine)
    ativar_limite_unifor_revisado()
    criar_usuarios_iniciais()


def criar_usuarios_iniciais() -> None:
    """Cria as contas iniciais que ainda não existem."""
    with Session(engine) as banco:
        emails_existentes = set(banco.scalars(select(Usuario.email)).all())
        for nome, email, perfil in CONTAS_INICIAIS:
            if email not in emails_existentes:
                banco.add(Usuario(nome=nome, email=email, senha_hash=gerar_hash_senha(SENHA_INICIAL), tipo_usuario=perfil))
        banco.commit()


def atualizar_credenciais_legadas() -> None:
    """Adapta a tabela antiga de credenciais sem apagar contas existentes."""
    inspecao = inspect(engine)
    if not inspecao.has_table("credentials"):
        return

    detalhes_colunas = {coluna["name"]: coluna for coluna in inspecao.get_columns("credentials")}
    precisa_adicionar_nome = "nome" not in detalhes_colunas
    matricula_obrigatoria = detalhes_colunas.get("matricula", {}).get("nullable") is False
    precisa_adicionar_ultimo_acesso = "ultimo_acesso" not in detalhes_colunas
    precisa_normalizar_perfil = True
    if not precisa_adicionar_nome and not matricula_obrigatoria and not precisa_adicionar_ultimo_acesso and not precisa_normalizar_perfil:
        return

    with engine.begin() as conexao:
        if engine.dialect.name == "postgresql":
            if precisa_adicionar_nome:
                conexao.execute(text("ALTER TABLE credentials ADD COLUMN IF NOT EXISTS nome VARCHAR(150)"))
                conexao.execute(
                    text(
                        """
                        UPDATE credentials
                        SET nome = INITCAP(REPLACE(SPLIT_PART(email, '@', 1), '.', ' '))
                        WHERE nome IS NULL
                        """
                    )
                )
                conexao.execute(text("ALTER TABLE credentials ALTER COLUMN nome SET NOT NULL"))
            if matricula_obrigatoria:
                conexao.execute(text("ALTER TABLE credentials ALTER COLUMN matricula DROP NOT NULL"))
            if precisa_adicionar_ultimo_acesso:
                conexao.execute(text("ALTER TABLE credentials ADD COLUMN IF NOT EXISTS ultimo_acesso TIMESTAMP WITH TIME ZONE"))
            conexao.execute(text("UPDATE credentials SET tipo_usuario = 'usuario' WHERE LOWER(tipo_usuario) IN ('aluno', 'aluna', 'student')"))
        else:
            if precisa_adicionar_nome:
                conexao.execute(text("ALTER TABLE credentials ADD COLUMN nome VARCHAR(150)"))
                conexao.execute(text("UPDATE credentials SET nome = email WHERE nome IS NULL"))
            if precisa_adicionar_ultimo_acesso:
                conexao.execute(text("ALTER TABLE credentials ADD COLUMN ultimo_acesso DATETIME"))
            conexao.execute(text("UPDATE credentials SET tipo_usuario = 'usuario' WHERE LOWER(tipo_usuario) IN ('aluno', 'aluna', 'student')"))


def atualizar_ocorrencias_legadas() -> None:
    """Inclui os campos de GPS sem apagar as ocorrências que já existem."""
    inspecao = inspect(engine)
    if not inspecao.has_table("ocorrencias"):
        return

    colunas = {coluna["name"] for coluna in inspecao.get_columns("ocorrencias")}
    colunas_ausentes = {"latitude", "longitude", "precisao_metros"} - colunas
    if not colunas_ausentes:
        return

    with engine.begin() as conexao:
        for coluna in sorted(colunas_ausentes):
            conexao.execute(text(f"ALTER TABLE ocorrencias ADD COLUMN {coluna} DOUBLE PRECISION"))


def ativar_limite_unifor_revisado() -> None:
    """Ativa apenas o rascunho de perímetro que já foi revisado neste projeto."""
    inspecao = inspect(engine)
    if not inspecao.has_table("areas_campus"):
        return
    with engine.begin() as conexao:
        conexao.execute(
            text(
                """
                UPDATE areas_campus
                SET nome = 'Limite do Campus UNIFOR', tipo = 'limite', limite_campus = TRUE, prioridade = 1000
                WHERE nome = 'UNIFOR - rascunho para ajuste' AND ativo = TRUE
                """
            )
        )
