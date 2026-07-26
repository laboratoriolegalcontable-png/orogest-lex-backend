"""
OroGest Lex — Dashboard Endpoints (Fase 14)
Operational metrics, system health, and activity summary.
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RequireRole
from app.core.security import Role
from app.db.session import get_db
from app.models.models import (
    AIConversation,
    AuditLog,
    Case,
    Document,
    Property,
    User,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
async def dashboard_summary(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireRole(Role.ABOGADO)),
):
    """
    Executive summary dashboard.
    Accessible to ABOGADO+ roles.
    """
    now = datetime.now(UTC)
    last_7_days = now - timedelta(days=7)

    # ── Cases ──
    total_cases = (
        await db.execute(select(func.count()).select_from(Case).where(Case.is_deleted == False))
    ).scalar() or 0

    active_cases = (
        await db.execute(
            select(func.count())
            .select_from(Case)
            .where(Case.is_deleted == False, Case.status == "activa")
        )
    ).scalar() or 0

    cases_by_branch = dict(
        (
            await db.execute(
                select(Case.branch, func.count())
                .where(Case.is_deleted == False)
                .group_by(Case.branch)
            )
        ).all()
    )

    cases_by_status = dict(
        (
            await db.execute(
                select(Case.status, func.count())
                .where(Case.is_deleted == False)
                .group_by(Case.status)
            )
        ).all()
    )

    # Upcoming deadlines (next 14 days)
    upcoming_deadlines = (
        await db.execute(
            select(Case.internal_id, Case.caption, Case.next_deadline, Case.branch)
            .where(
                Case.is_deleted == False,
                Case.next_deadline.isnot(None),
                Case.next_deadline <= now + timedelta(days=14),
                Case.next_deadline >= now,
            )
            .order_by(Case.next_deadline.asc())
            .limit(10)
        )
    ).all()

    # High risk cases
    high_risk_cases = (
        await db.execute(
            select(func.count())
            .select_from(Case)
            .where(
                Case.is_deleted == False,
                Case.risk_score.isnot(None),
                Case.risk_score >= 70,
            )
        )
    ).scalar() or 0

    # ── Documents ──
    total_documents = (
        await db.execute(
            select(func.count()).select_from(Document).where(Document.is_deleted == False)
        )
    ).scalar() or 0

    docs_last_7 = (
        await db.execute(
            select(func.count())
            .select_from(Document)
            .where(
                Document.is_deleted == False,
                Document.created_at >= last_7_days,
            )
        )
    ).scalar() or 0

    # ── Properties ──
    total_properties = (
        await db.execute(
            select(func.count()).select_from(Property).where(Property.is_deleted == False)
        )
    ).scalar() or 0

    properties_by_risk = dict(
        (
            await db.execute(
                select(Property.dd_risk_level, func.count())
                .where(Property.is_deleted == False, Property.dd_risk_level.isnot(None))
                .group_by(Property.dd_risk_level)
            )
        ).all()
    )

    # ── AI Usage ──
    total_ai_conversations = (
        await db.execute(select(func.count()).select_from(AIConversation))
    ).scalar() or 0

    total_tokens = (await db.execute(select(func.sum(AIConversation.tokens_used)))).scalar() or 0

    ai_last_7 = (
        await db.execute(
            select(func.count())
            .select_from(AIConversation)
            .where(
                AIConversation.created_at >= last_7_days,
            )
        )
    ).scalar() or 0

    ai_by_workflow = dict(
        (
            await db.execute(
                select(AIConversation.workflow, func.count())
                .where(AIConversation.workflow.isnot(None))
                .group_by(AIConversation.workflow)
            )
        ).all()
    )

    total_verification_flags = (
        await db.execute(select(func.sum(AIConversation.verification_flags_count)))
    ).scalar() or 0

    # ── Users ──
    total_users = (
        await db.execute(
            select(func.count())
            .select_from(User)
            .where(User.is_deleted == False, User.is_active == True)
        )
    ).scalar() or 0

    # ── Audit ──
    audit_last_24h = (
        await db.execute(
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.timestamp >= now - timedelta(hours=24),
            )
        )
    ).scalar() or 0

    # Recent activity (last 10 audit entries)
    recent_activity = (
        await db.execute(
            select(AuditLog.action, AuditLog.resource_type, AuditLog.timestamp, AuditLog.user_id)
            .order_by(AuditLog.timestamp.desc())
            .limit(10)
        )
    ).all()

    return {
        "generated_at": now.isoformat(),
        "cases": {
            "total": total_cases,
            "active": active_cases,
            "high_risk": high_risk_cases,
            "by_branch": cases_by_branch,
            "by_status": cases_by_status,
            "upcoming_deadlines": [
                {
                    "internal_id": d.internal_id,
                    "caption": d.caption[:60],
                    "deadline": d.next_deadline.isoformat() if d.next_deadline else None,
                    "branch": d.branch,
                }
                for d in upcoming_deadlines
            ],
        },
        "documents": {
            "total": total_documents,
            "created_last_7_days": docs_last_7,
        },
        "properties": {
            "total": total_properties,
            "by_risk_level": properties_by_risk,
        },
        "ai": {
            "total_conversations": total_ai_conversations,
            "total_tokens_used": total_tokens,
            "conversations_last_7_days": ai_last_7,
            "by_workflow": ai_by_workflow,
            "total_verification_flags": total_verification_flags,
        },
        "users": {
            "total_active": total_users,
        },
        "audit": {
            "events_last_24h": audit_last_24h,
            "recent_activity": [
                {
                    "action": a.action,
                    "resource_type": a.resource_type,
                    "timestamp": a.timestamp.isoformat(),
                }
                for a in recent_activity
            ],
        },
    }


@router.get("/health")
async def system_health(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireRole(Role.DIRECTOR)),
):
    """
    System health check — DIRECTOR only.
    Verifies DB connectivity, audit chain integrity, and service status.
    """
    health = {
        "status": "ok",
        "checks": {},
    }

    # DB check
    try:
        await db.execute(select(func.now()))
        health["checks"]["database"] = {"status": "ok"}
    except Exception as e:  # noqa: BLE001 — health check: one failing probe must not crash the others
        health["checks"]["database"] = {"status": "error", "detail": str(e)[:100]}
        health["status"] = "degraded"

    # Audit chain integrity (check last 10 entries)
    try:
        result = await db.execute(select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(10))
        entries = list(result.scalars().all())

        chain_valid = True
        for i in range(len(entries) - 1):
            current = entries[i]
            previous = entries[i + 1]
            if current.previous_hash != previous.current_hash:
                chain_valid = False
                break

        health["checks"]["audit_chain"] = {
            "status": "ok" if chain_valid else "warning",
            "entries_checked": len(entries),
            "chain_intact": chain_valid,
        }
    except Exception as e:  # noqa: BLE001 — health check: one failing probe must not crash the others
        health["checks"]["audit_chain"] = {"status": "error", "detail": str(e)[:100]}

    # Claude API check (just verify key is configured)
    from app.core.config import get_settings

    settings = get_settings()
    claude_configured = bool(
        settings.CLAUDE_API_KEY and settings.CLAUDE_API_KEY != "sk-ant-CAMBIAR"
    )
    health["checks"]["claude_api"] = {
        "status": "ok" if claude_configured else "not_configured",
        "model": settings.CLAUDE_MODEL,
    }

    return health
