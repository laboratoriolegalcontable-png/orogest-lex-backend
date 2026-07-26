"""
OroGest Lex — Audit Log Endpoints
Read-only access to the tamper-evident audit trail.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RequirePermission
from app.core.security import Permission
from app.db.session import get_db
from app.models.models import AuditLog, User
from app.schemas.schemas import AuditLogResponse

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs", response_model=list[AuditLogResponse])
async def list_audit_logs(
    action: str | None = None,
    resource_type: str | None = None,
    user_id: uuid.UUID | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RequirePermission(Permission.AUDIT_READ)),
):
    stmt = select(AuditLog)

    if action:
        stmt = stmt.where(AuditLog.action.ilike(f"%{action}%"))
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if since:
        stmt = stmt.where(AuditLog.timestamp >= since)
    if until:
        stmt = stmt.where(AuditLog.timestamp <= until)

    stmt = stmt.order_by(AuditLog.timestamp.desc()).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/logs/count")
async def audit_log_count(
    action: str | None = None,
    since: datetime | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RequirePermission(Permission.AUDIT_READ)),
):
    stmt = select(func.count()).select_from(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action.ilike(f"%{action}%"))
    if since:
        stmt = stmt.where(AuditLog.timestamp >= since)
    total = (await db.execute(stmt)).scalar() or 0
    return {"total": total}


@router.get("/verify-chain")
async def verify_audit_chain(
    last_n: int = Query(100, ge=10, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RequirePermission(Permission.AUDIT_READ)),
):
    """
    Verify SHA-256 hash chain integrity over the last N audit entries.
    Detects tampering if any entry's previous_hash doesn't match the
    prior entry's current_hash.
    """
    result = await db.execute(select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(last_n))
    entries = list(result.scalars().all())

    if not entries:
        return {"status": "empty", "entries_checked": 0, "breaks": []}

    breaks = []
    for i in range(len(entries) - 1):
        current = entries[i]
        previous = entries[i + 1]
        if current.previous_hash != previous.current_hash:
            breaks.append(
                {
                    "position": i,
                    "current_id": str(current.id),
                    "expected_previous_hash": previous.current_hash,
                    "actual_previous_hash": current.previous_hash,
                    "timestamp": current.timestamp.isoformat(),
                }
            )

    return {
        "status": "intact" if not breaks else "BROKEN",
        "entries_checked": len(entries),
        "chain_links_verified": len(entries) - 1,
        "breaks": breaks,
    }


@router.get("/actions")
async def list_audit_actions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RequirePermission(Permission.AUDIT_READ)),
):
    """List all distinct audit actions for filtering."""
    result = await db.execute(
        select(AuditLog.action, func.count())
        .group_by(AuditLog.action)
        .order_by(func.count().desc())
    )
    return [{"action": row[0], "count": row[1]} for row in result.all()]
