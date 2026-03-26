"""
OroGest Lex — Users Management Endpoints
DIRECTOR-only: list, update roles, deactivate users.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RequireRole
from app.core.security import Role
from app.db.session import get_db
from app.models.models import User
from app.schemas.schemas import UserResponse, UserUpdate
from app.services.audit_service import create_audit_entry

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=list[UserResponse])
async def list_users(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RequireRole(Role.DIRECTOR)),
):
    stmt = select(User).where(User.is_deleted == False)
    if not include_inactive:
        stmt = stmt.where(User.is_active == True)
    stmt = stmt.order_by(User.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RequireRole(Role.DIRECTOR)),
):
    user = await db.get(User, user_id)
    if not user or user.is_deleted:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return user


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RequireRole(Role.DIRECTOR)),
):
    user = await db.get(User, user_id)
    if not user or user.is_deleted:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Cannot demote yourself
    if user.id == current_user.id and body.role and body.role != current_user.role:
        raise HTTPException(status_code=400, detail="No podés cambiar tu propio rol")

    changes = {}
    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        old = getattr(user, field)
        if old != value:
            changes[field] = {"old": str(old), "new": str(value)}
            setattr(user, field, value)

    if changes:
        await create_audit_entry(
            db, action="user.update", user_id=current_user.id,
            resource_type="user", resource_id=str(user.id),
            details={"changes": changes},
            ip_address=request.client.host if request.client else None,
        )

    return user


@router.post("/{user_id}/deactivate", response_model=UserResponse)
async def deactivate_user(
    user_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RequireRole(Role.DIRECTOR)),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="No podés desactivarte a vos mismo")

    user = await db.get(User, user_id)
    if not user or user.is_deleted:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    user.is_active = False

    await create_audit_entry(
        db, action="user.deactivate", user_id=current_user.id,
        resource_type="user", resource_id=str(user.id),
        ip_address=request.client.host if request.client else None,
    )
    return user


@router.post("/{user_id}/reactivate", response_model=UserResponse)
async def reactivate_user(
    user_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RequireRole(Role.DIRECTOR)),
):
    user = await db.get(User, user_id)
    if not user or user.is_deleted:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    user.is_active = True

    await create_audit_entry(
        db, action="user.reactivate", user_id=current_user.id,
        resource_type="user", resource_id=str(user.id),
        ip_address=request.client.host if request.client else None,
    )
    return user
