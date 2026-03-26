"""
OroGest Lex — Auth Endpoints
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    Role,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.api.deps import get_current_user, RequireRole
from app.models.models import User
from app.schemas.schemas import (
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
)
from app.services.audit_service import create_audit_entry

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(User.email == body.email, User.is_deleted == False)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Cuenta desactivada")

    # Update last login
    user.last_login = datetime.now(timezone.utc)

    # Create tokens
    token_data = {"sub": str(user.id), "role": user.role, "email": user.email}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    # Audit
    await create_audit_entry(
        db,
        action="user.login",
        user_id=user.id,
        ip_address=request.client.host if request.client else None,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Token no es refresh")

        user_id = payload.get("sub")
        result = await db.execute(
            select(User).where(User.id == user_id, User.is_deleted == False)
        )
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="Usuario inválido")

        token_data = {"sub": str(user.id), "role": user.role, "email": user.email}
        new_access = create_access_token(token_data)
        new_refresh = create_refresh_token(token_data)

        return TokenResponse(
            access_token=new_access,
            refresh_token=new_refresh,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Refresh token inválido")


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_user(
    body: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RequireRole(Role.DIRECTOR)),
):
    """Only DIRECTOR can create new users."""
    # Check duplicate
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email ya registrado")

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        role=body.role,
    )
    db.add(user)
    await db.flush()

    await create_audit_entry(
        db,
        action="user.create",
        user_id=current_user.id,
        resource_type="user",
        resource_id=str(user.id),
        details={"email": user.email, "role": user.role},
        ip_address=request.client.host if request.client else None,
    )

    return user


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=8)
    new_password: str = Field(min_length=8)


@router.post("/change-password")
async def change_password(
    body: PasswordChangeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Change own password. Requires current password for verification."""
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Contraseña actual incorrecta")

    if body.current_password == body.new_password:
        raise HTTPException(status_code=400, detail="La nueva contraseña debe ser diferente")

    current_user.hashed_password = hash_password(body.new_password)

    await create_audit_entry(
        db, action="user.password_change", user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
    )

    return {"status": "ok", "message": "Contraseña actualizada"}


@router.post("/reset-password/{user_id}")
async def reset_password(
    user_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RequireRole(Role.DIRECTOR)),
):
    """DIRECTOR can reset any user's password to a temporary one."""
    user = await db.get(User, user_id)
    if not user or user.is_deleted:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    import secrets
    temp_password = secrets.token_urlsafe(12)
    user.hashed_password = hash_password(temp_password)

    await create_audit_entry(
        db, action="user.password_reset", user_id=current_user.id,
        resource_type="user", resource_id=str(user.id),
        ip_address=request.client.host if request.client else None,
    )

    return {
        "status": "ok",
        "user_email": user.email,
        "temporary_password": temp_password,
        "message": "El usuario debe cambiar la contraseña en su próximo login.",
    }
