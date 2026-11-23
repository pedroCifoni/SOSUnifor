from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PASTA_SERVICO = Path(__file__).resolve().parents[2]
ARQUIVO_ENV = PASTA_SERVICO / ".env"
PASTA_ARQUIVOS = PASTA_SERVICO / "uploads"


class Configuracoes(BaseSettings):
    app_name: str = "Auth Service"
    ambiente: str = "desenvolvimento"
    database_url: str = "postgresql+psycopg://unisos:uni12345@localhost:5433/unisos"
    jwt_secret: str = "chave-exclusiva-para-desenvolvimento-local-nao-publicar"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    rabbitmq_url: str = "amqp://unisos:uni12345@localhost:5672/"

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
