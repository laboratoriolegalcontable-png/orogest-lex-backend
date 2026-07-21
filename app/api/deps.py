"""
OroGest Lex — API Dependencies
"""

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Permission, Role, decode_token, role_has_permission
from app.db.session import get_db
from app.models.models import User

security_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate JWT, return the active User."""
    token = credentials.credentials
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Token inválido: no es access token")
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Token inválido: sin subject")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    result = await db.execute(select(User).where(User.id == user_id, User.is_deleted == False))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Usuario desactivado")

    return user


class RequirePermission:
    """
    Dependency that checks if the current user has a specific permission.
    Usage: Depends(RequirePermission(Permission.CASES_WRITE))
    """

    def __init__(self, permission: Permission):
        self.permission = permission

    async def __call__(self, user: User = Depends(get_current_user)) -> User:
        user_role = Role(user.role)
        if not role_has_permission(user_role, self.permission):
            raise HTTPException(
                status_code=403,
                detail=f"Permiso insuficiente: se requiere {self.permission.value}",
            )
        return user


class RequireRole:
    """
    Dependency that checks if the current user has a minimum role.
    Usage: Depends(RequireRole(Role.ABOGADO))
    """

    _hierarchy = {Role.DIRECTOR: 4, Role.ABOGADO: 3, Role.ASISTENTE: 2, Role.PASANTE: 1}

    def __init__(self, min_role: Role):
        self.min_role = min_role

    async def __call__(self, user: User = Depends(get_current_user)) -> User:
        user_level = self._hierarchy.get(Role(user.role), 0)
        required_level = self._hierarchy.get(self.min_role, 99)
        if user_level < required_level:
            raise HTTPException(
                status_code=403,
                detail=f"Rol insuficiente: se requiere {self.min_role.value} o superior",
            )
        return user
