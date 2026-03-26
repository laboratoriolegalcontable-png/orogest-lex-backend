"""
OroGest Lex — Seguridad: JWT, hashing, RBAC
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()

# ── Password Hashing ──
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT ──
def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(data: dict[str, Any]) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh", "jti": secrets.token_hex(16)})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate JWT. Raises JWTError on failure."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


# ── RBAC ──
class Role(str, Enum):
    """
    Roles para Estudio Oro S.A.S.
    DIRECTOR = Diego Orosa (acceso total)
    ABOGADO = abogados del estudio
    ASISTENTE = asistentes administrativos
    PASANTE = acceso solo lectura limitado
    """
    DIRECTOR = "director"
    ABOGADO = "abogado"
    ASISTENTE = "asistente"
    PASANTE = "pasante"


class Permission(str, Enum):
    # Cases
    CASES_READ = "cases:read"
    CASES_WRITE = "cases:write"
    CASES_DELETE = "cases:delete"
    # Documents
    DOCS_READ = "docs:read"
    DOCS_WRITE = "docs:write"
    DOCS_DELETE = "docs:delete"
    # AI / Claude proxy
    AI_CHAT = "ai:chat"
    AI_ANALYZE = "ai:analyze"
    AI_DRAFT = "ai:draft"
    # Real Estate
    REALESTATE_READ = "realestate:read"
    REALESTATE_WRITE = "realestate:write"
    # Admin
    USERS_MANAGE = "users:manage"
    AUDIT_READ = "audit:read"
    SETTINGS_MANAGE = "settings:manage"
    # Accounting (SmartLedgerPro integration)
    ACCOUNTING_READ = "accounting:read"
    ACCOUNTING_WRITE = "accounting:write"


# Permission matrix: role → set of permissions
ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.DIRECTOR: set(Permission),  # All permissions
    Role.ABOGADO: {
        Permission.CASES_READ,
        Permission.CASES_WRITE,
        Permission.DOCS_READ,
        Permission.DOCS_WRITE,
        Permission.AI_CHAT,
        Permission.AI_ANALYZE,
        Permission.AI_DRAFT,
        Permission.REALESTATE_READ,
        Permission.REALESTATE_WRITE,
        Permission.ACCOUNTING_READ,
    },
    Role.ASISTENTE: {
        Permission.CASES_READ,
        Permission.DOCS_READ,
        Permission.DOCS_WRITE,
        Permission.AI_CHAT,
        Permission.REALESTATE_READ,
        Permission.ACCOUNTING_READ,
    },
    Role.PASANTE: {
        Permission.CASES_READ,
        Permission.DOCS_READ,
        Permission.REALESTATE_READ,
    },
}


def role_has_permission(role: Role, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())


# ── Audit Hash Chain (SHA-256) ──
def compute_audit_hash(previous_hash: str, event_data: str) -> str:
    """SHA-256 chained hash for tamper-evident audit log."""
    payload = f"{previous_hash}|{event_data}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
