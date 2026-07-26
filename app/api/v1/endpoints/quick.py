"""
OroGest Lex — Quick Status API
Mobile-optimized endpoints for fast consultation on the go.
Returns minimal payloads, cached where possible.
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.models import AIConversation, Case, User

router = APIRouter(prefix="/quick", tags=["quick"])


@router.get("/status")
async def quick_status(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    One-call status for mobile dashboard.
    Returns everything needed in a single request.
    """
    now = datetime.now(UTC)

    # Active cases count
    active = (
        await db.execute(
            select(func.count())
            .select_from(Case)
            .where(Case.is_deleted == False, Case.status == "activa")
        )
    ).scalar() or 0

    # Urgent deadlines (next 3 days)
    urgent_deadline_count = (
        await db.execute(
            select(func.count())
            .select_from(Case)
            .where(
                Case.is_deleted == False,
                Case.next_deadline.isnot(None),
                Case.next_deadline <= now + timedelta(days=3),
                Case.next_deadline >= now,
            )
        )
    ).scalar() or 0

    # Next deadline
    next_dl = (
        await db.execute(
            select(Case.internal_id, Case.caption, Case.next_deadline, Case.branch)
            .where(
                Case.is_deleted == False,
                Case.next_deadline.isnot(None),
                Case.next_deadline >= now,
            )
            .order_by(Case.next_deadline.asc())
            .limit(1)
        )
    ).first()

    # High risk cases
    high_risk = (
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

    # Today's AI usage
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    ai_today = (
        await db.execute(
            select(func.count())
            .select_from(AIConversation)
            .where(AIConversation.created_at >= today_start)
        )
    ).scalar() or 0

    return {
        "timestamp": now.isoformat(),
        "cases_active": active,
        "deadlines_urgent": urgent_deadline_count,
        "cases_high_risk": high_risk,
        "ai_queries_today": ai_today,
        "next_deadline": {
            "case": next_dl.internal_id,
            "caption": next_dl.caption[:50],
            "date": next_dl.next_deadline.isoformat(),
            "branch": next_dl.branch,
        }
        if next_dl
        else None,
        "greeting": _greeting(user.full_name),
    }


@router.get("/my-cases")
async def my_active_cases(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Quick list of my active cases with deadlines."""
    result = await db.execute(
        select(
            Case.id,
            Case.internal_id,
            Case.caption,
            Case.branch,
            Case.status,
            Case.risk_score,
            Case.next_deadline,
        )
        .where(
            Case.is_deleted == False,
            Case.assigned_to == user.id,
            Case.status.in_(["activa", "en_tramite", "en_recurso"]),
        )
        .order_by(Case.next_deadline.asc().nullslast(), Case.updated_at.desc())
        .limit(limit)
    )

    return [
        {
            "id": str(row.id),
            "internal_id": row.internal_id,
            "caption": row.caption[:60],
            "branch": row.branch,
            "status": row.status,
            "risk": row.risk_score,
            "deadline": row.next_deadline.isoformat() if row.next_deadline else None,
        }
        for row in result.all()
    ]


def _greeting(name: str) -> str:
    hour = datetime.now(UTC).hour - 3  # Argentina UTC-3
    if hour < 0:
        hour += 24
    first = name.split()[0] if name else "Dr."
    if hour < 12:
        return f"Buen día, {first}"
    elif hour < 19:
        return f"Buenas tardes, {first}"
    else:
        return f"Buenas noches, {first}"
