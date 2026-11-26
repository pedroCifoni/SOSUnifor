from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PASTA_SERVICO = Path(__file__).resolve().parents[2]
ARQUIVO_ENV = PASTA_SERVICO / ".env"
PASTA_ARQUIVOS = PASTA_SERVICO / "uploads"


class Configuracoes(BaseSettings):
    app_name: str = "Uni SOS API"
    ambiente: str = "desenvolvimento"
    database_url: str = "postgresql+psycopg://unisos:uni12345@localhost:5433/unisos"

    # Pool de conexões por processo da API. No Neon, use em DATABASE_URL o endpoint com "-pooler".
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 10
    db_pool_recycle: int = 300
    # Desligue (false) se o pooler em modo transação reclamar de prepared statements.
    db_prepared_statements: bool = True
    jwt_secret: str = "chave-exclusiva-para-desenvolvimento-local-nao-publicar"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    # Refresh token (POST /auth/renovar): renova o access token sem pedir a senha de novo.
    refresh_token_expire_dias: int = 7
    # Força bruta no login: falhas permitidas por e-mail e por IP dentro da janela.
    login_max_falhas_por_email: int = 5
    login_max_falhas_por_ip: int = 30
    login_janela_falhas_minutos: int = 15
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    rabbitmq_url: str = "amqp://unisos:uni12345@localhost:5672/"
    # Aspecto medir_desempenho: chamadas de service acima deste tempo são registradas no log.
    desempenho_limite_ms: int = 500

    # Endereço público do front-end, usado para montar os links enviados por e-mail.
    frontend_url: str = "http://localhost:5173"
    redefinicao_senha_expira_minutos: int = 30
    verificacao_email_expira_horas: int = 48

    # Retenção (LGPD): rotina executada a cada subida da API (app/services/retencao_service.py).
    # Notificações já lidas são apagadas depois deste número de dias.
    retencao_notificacoes_lidas_dias: int = 180
    # Tokens de redefinição de senha vencidos são apagados depois destas horas além do vencimento.
    # A folga mantém os pedidos recentes, que contam no limite de "esqueci minha senha" por hora.
    retencao_tokens_vencidos_horas: int = 24

    # E-mail (SMTP). Sem SMTP_HOST, os e-mails são apenas registrados no log da API.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_usuario: str = ""
    smtp_senha: str = ""
    smtp_remetente: str = "Uni SOS <nao-responda@unisos.local>"
    smtp_starttls: bool = True
    smtp_ssl: bool = False

    # E-mail por API HTTP (porta 443). Com BREVO_API_KEY preenchida, ela é usada no lugar do SMTP.
    # Necessário no plano gratuito do Render, que bloqueia as portas de SMTP (25, 465 e 587).
    # O remetente continua vindo de SMTP_REMETENTE e precisa estar verificado na Brevo.
    brevo_api_key: str = ""

    model_config = SettingsConfigDict(
        env_file=ARQUIVO_ENV,
        env_file_encoding="utf-8",
        extra="ignore",
    )


configuracoes = Configuracoes()


def obter_origens_cors() -> list[str]:
    return [origem.strip() for origem in configuracoes.cors_origins.split(",") if origem.strip()]


def validar_configuracao_de_producao() -> None:
    if configuracoes.ambiente.lower() not in {"producao", "production"}:
        return
    if len(configuracoes.jwt_secret) < 32 or "desenvolvimento" in configuracoes.jwt_secret.lower():
        raise RuntimeError("JWT_SECRET forte e exclusivo é obrigatório em produção.")
    if "uni12345" in configuracoes.database_url:
        raise RuntimeError("DATABASE_URL com credencial exclusiva é obrigatória em produção.")
    if any(origem.startswith("http://localhost") or origem.startswith("http://127.") for origem in obter_origens_cors()):
        raise RuntimeError("CORS_ORIGINS deve conter apenas domínios HTTPS da aplicação em produção.")
