"""
OroGest Lex — Configuración Central
Estudio Oro S.A.S. | CUIT 30-71933033-5
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── App ──
    APP_NAME: str = "OroGest Lex API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"  # development | staging | production

    # ── Server ──
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3000",
        "https://estudiooroapp.netlify.app",
        "https://estudiooro.com",
    ]

    # ── Database (PostgreSQL + pgvector) ──
    DATABASE_URL: str = "postgresql+asyncpg://orogest:orogest@localhost:5432/orogest_lex"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_ECHO: bool = False

    # ── Redis ──
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── JWT Auth ──
    SECRET_KEY: str = "CAMBIAR-EN-PRODUCCION-generar-con-openssl-rand-hex-64"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Claude API Proxy ──
    CLAUDE_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"
    CLAUDE_MAX_TOKENS: int = 4096
    CLAUDE_PROXY_RATE_LIMIT: int = 30  # requests per minute per user

    # ── Encryption (AES-256-GCM for sensitive data at rest) ──
    ENCRYPTION_KEY: str = "CAMBIAR-EN-PRODUCCION-32-bytes-base64"

    # ── Audit ──
    AUDIT_LOG_ENABLED: bool = True
    AUDIT_HASH_CHAIN: bool = True  # SHA-256 chained audit logs

    # ── Data Residency ──
    AWS_REGION: str = "sa-east-1"  # São Paulo


@lru_cache
def get_settings() -> Settings:
    return Settings()
