"""
OroGest Lex — Notifications Endpoints
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RequireRole, get_current_user
from app.core.security import Role
from app.db.session import get_db
from app.models.models import User
from app.services.notifications_service import (
    get_unread_count,
    get_user_notifications,
    mark_all_read,
    mark_as_read,
    scan_upcoming_deadlines,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/")
async def list_notifications(
    unread_only: bool = False,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    notifs = await get_user_notifications(db, user.id, unread_only=unread_only, limit=limit)
    unread = await get_unread_count(db, user.id)

    return {
        "unread_count": unread,
        "notifications": [
            {
                "id": str(n.id),
                "title": n.title,
                "message": n.message,
                "priority": n.priority,
                "category": n.category,
                "resource_type": n.resource_type,
                "resource_id": n.resource_id,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat(),
            }
            for n in notifs
        ],
    }


@router.get("/count")
async def unread_count(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    count = await get_unread_count(db, user.id)
    return {"unread_count": count}


@router.post("/{notification_id}/read")
async def read_notification(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    success = await mark_as_read(db, notification_id, user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")
    return {"status": "read"}


@router.post("/read-all")
async def read_all_notifications(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    count = await mark_all_read(db, user.id)
    return {"marked_read": count}


@router.post("/scan-deadlines")
async def trigger_deadline_scan(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireRole(Role.DIRECTOR)),
):
    """
    Manually trigger deadline scan. In production, run via cron/scheduler.
    """
    generated = await scan_upcoming_deadlines(db)
    return {
        "status": "completed",
        "notifications_generated": len(generated),
        "details": generated,
    }
