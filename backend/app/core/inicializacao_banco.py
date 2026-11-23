"""Preparação do banco na subida da API.

Ajusta tabelas de versões antigas sem apagar dados, cria as tabelas que faltam
e cadastra as contas iniciais quando ainda não existem.
"""

from datetime import datetime, timezone

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

# Trava para duas instâncias da API subindo juntas não disputarem os mesmos comandos de estrutura.
CHAVE_TRAVA_INICIALIZACAO = 74_210_901


def inicializar_banco() -> None:
    if engine.dialect.name != "postgresql":
        _executar_etapas()
        return
    # Duas instâncias/workers subindo juntos fazem a preparação um de cada vez. A trava é de transação
    # (pg_advisory_xact_lock) numa conexão que fica com a transação aberta até o fim: assim funciona
    # também pelo pooler do Neon em modo transação, e é liberada sozinha se o processo cair.
    with engine.connect() as conexao_trava, conexao_trava.begin():
        conexao_trava.execute(text("SELECT pg_advisory_xact_lock(:chave)"), {"chave": CHAVE_TRAVA_INICIALIZACAO})
        _executar_etapas()


def _executar_etapas() -> None:
    atualizar_credenciais_legadas()
    adicionar_verificacao_de_email()
    atualizar_ocorrencias_legadas()
    Base.metadata.create_all(bind=engine)
    criar_indices_de_consulta()
    preparar_sequencia_de_protocolo()
    ativar_limite_unifor_revisado()
    criar_usuarios_iniciais()


# create_all não cria índices novos em tabelas que já existem; por isso ficam aqui, idempotentes.
INDICES_DE_CONSULTA = [
    # Listagem do admin (ordem e cursor) e listagens por autor / responsável / status.
    "CREATE INDEX IF NOT EXISTS ix_ocorrencias_criado_em_id ON ocorrencias (criado_em DESC, id DESC)",
    "CREATE INDEX IF NOT EXISTS ix_ocorrencias_autor_criado_em ON ocorrencias (autor_id, criado_em DESC, id DESC)",
    "CREATE INDEX IF NOT EXISTS ix_ocorrencias_responsavel_criado_em ON ocorrencias (responsavel_id, criado_em DESC, id DESC)",
    "CREATE INDEX IF NOT EXISTS ix_ocorrencias_status_criado_em ON ocorrencias (status, criado_em DESC, id DESC)",
    # Notificações do usuário (ordem e cursor) e contagem / marcação das não lidas.
    "CREATE INDEX IF NOT EXISTS ix_notificacoes_destinatario_criada_em ON notificacoes (destinatario_id, criada_em DESC, id DESC)",
    "CREATE INDEX IF NOT EXISTS ix_notificacoes_destinatario_nao_lidas ON notificacoes (destinatario_id) WHERE lida = false",
    # Busca de contas ativas por perfil (admins avisados a cada nova ocorrência, equipes etc.).
    "CREATE INDEX IF NOT EXISTS ix_credentials_tipo_usuario_ativo ON credentials (tipo_usuario, ativo)",
]

def criar_indices_de_consulta() -> None:
    with engine.begin() as conexao:
        for comando in INDICES_DE_CONSULTA:
            conexao.execute(text(comando))


def preparar_sequencia_de_protocolo() -> None:
    """Cria a SEQUENCE dos protocolos e a posiciona depois do maior número já usado.

    Só avança a sequência (nunca volta), então rodar de novo a cada subida é seguro.
    """
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as conexao:
        conexao.execute(text("CREATE SEQUENCE IF NOT EXISTS ocorrencias_protocolo_seq"))
        conexao.execute(
            text(
                """
                SELECT setval('ocorrencias_protocolo_seq', usados.maior)
                FROM (
                    SELECT MAX(CAST(SPLIT_PART(protocolo, '-', 2) AS BIGINT)) AS maior
                    FROM ocorrencias
                    WHERE SPLIT_PART(protocolo, '-', 2) ~ '^[0-9]{1,18}$'
                ) AS usados
                WHERE usados.maior IS NOT NULL
                  AND usados.maior >= (
                      SELECT CASE WHEN is_called THEN last_value + 1 ELSE last_value END
                      FROM ocorrencias_protocolo_seq
                  )
                """
            )
        )


def criar_usuarios_iniciais() -> None:
    """Cria as contas iniciais que ainda não existem (já com o e-mail confirmado)."""
    with Session(engine) as banco:
        emails_existentes = set(banco.scalars(select(Usuario.email)).all())
        agora = datetime.now(timezone.utc)
        for nome, email, perfil in CONTAS_INICIAIS:
            if email not in emails_existentes:
                banco.add(
                    Usuario(
                        nome=nome,
                        email=email,
                        senha_hash=gerar_hash_senha(SENHA_INICIAL),
                        tipo_usuario=perfil,
                        email_verificado_em=agora,
                    )
                )
        banco.commit()


def adicionar_verificacao_de_email() -> None:
    """Cria a coluna `email_verificado_em` sem trancar ninguém do lado de fora.

    Só na primeira vez (quando a coluna ainda não existe), todas as contas que já existem são
    marcadas como confirmadas: elas foram criadas antes da verificação existir. Daí em diante,
    contas novas nascem sem confirmação. Coluna e marcação vão na mesma transação.
    """
    inspecao = inspect(engine)
    if not inspecao.has_table("credentials"):
        return  # banco novo: create_all cria a tabela já com a coluna
    if "email_verificado_em" in {coluna["name"] for coluna in inspecao.get_columns("credentials")}:
        return

    with engine.begin() as conexao:
        if engine.dialect.name == "postgresql":
            conexao.execute(text("ALTER TABLE credentials ADD COLUMN IF NOT EXISTS email_verificado_em TIMESTAMP WITH TIME ZONE"))
            conexao.execute(text("UPDATE credentials SET email_verificado_em = now() WHERE email_verificado_em IS NULL"))
        else:
            conexao.execute(text("ALTER TABLE credentials ADD COLUMN email_verificado_em DATETIME"))
            conexao.execute(text("UPDATE credentials SET email_verificado_em = CURRENT_TIMESTAMP WHERE email_verificado_em IS NULL"))


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
