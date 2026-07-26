"""
OroGest Lex — Configuración Central
Estudio Oro S.A.S. | CUIT 30-71933033-5
"""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER_SECRET_KEY = "CAMBIAR-EN-PRODUCCION-generar-con-openssl-rand-hex-64"
_PLACEHOLDER_ENCRYPTION_KEY = "CAMBIAR-EN-PRODUCCION-32-bytes-base64"


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

    @model_validator(mode="after")
    def _reject_placeholder_secrets_in_production(self) -> "Settings":
        if self.ENVIRONMENT != "production":
            return self
        if self.SECRET_KEY == _PLACEHOLDER_SECRET_KEY:
            raise ValueError(
                "SECRET_KEY sigue en su valor placeholder por defecto. "
                "Generar uno real con `openssl rand -hex 64` y setearlo antes de arrancar en produccion."
            )
        if self.ENCRYPTION_KEY == _PLACEHOLDER_ENCRYPTION_KEY:
            raise ValueError(
                "ENCRYPTION_KEY sigue en su valor placeholder por defecto. "
                "Generar una clave real de 32 bytes en base64 antes de arrancar en produccion."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
