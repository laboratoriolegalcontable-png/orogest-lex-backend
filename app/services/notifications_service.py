"""
OroGest Lex — Notifications Service
Deadline monitoring, case status alerts, and activity notifications.

This is an in-app notification system stored in DB.
For push notifications (WhatsApp, email), integrate with N8n workflows.
"""

import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, Boolean, select, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin, TimestampMixin


class NotificationPriority(str, Enum):
    CRITICAL = "critical"  # 🚨 vence hoy / detenido
    HIGH = "high"  # ⚠️ vence en 3 días
    NORMAL = "normal"
    LOW = "low"


class Notification(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # "deadline" | "case_update" | "document" | "ai" | "system"

    # Link to related resource
    resource_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_notif_user_unread", "user_id", "is_read"),)


# ═══════════════════════════════════════════
# NOTIFICATION CREATION
# ═══════════════════════════════════════════
async def create_notification(
    db: AsyncSession,
    user_id: uuid.UUID,
    title: str,
    message: str,
    category: str,
    priority: str = "normal",
    resource_type: str | None = None,
    resource_id: str | None = None,
) -> Notification:
    notif = Notification(
        user_id=user_id,
        title=title,
        message=message,
        priority=priority,
        category=category,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    db.add(notif)
    await db.flush()
    return notif


# ═══════════════════════════════════════════
# DEADLINE SCANNER
# ═══════════════════════════════════════════
async def scan_upcoming_deadlines(db: AsyncSession) -> list[dict]:
    """
    Scan for cases with upcoming deadlines and generate notifications.
    Run this periodically (cron job / scheduled task).

    Rules:
    - Vence hoy → CRITICAL
    - Vence en 1-3 días → HIGH
    - Vence en 4-7 días → NORMAL
    - Vence en 8-14 días → LOW
    """
    from app.models.models import Case

    now = datetime.now(timezone.utc)
    in_14_days = now + timedelta(days=14)

    result = await db.execute(
        select(Case)
        .where(
            Case.is_deleted == False,
            Case.next_deadline.isnot(None),
            Case.next_deadline >= now,
            Case.next_deadline <= in_14_days,
        )
        .order_by(Case.next_deadline.asc())
    )
    cases = result.scalars().all()

    generated = []
    for case in cases:
        days_until = (case.next_deadline - now).days

        if days_until == 0:
            priority = "critical"
            title = f"🚨 VENCE HOY: {case.caption[:60]}"
        elif days_until <= 3:
            priority = "high"
            title = (
                f"⚠️ Vence en {days_until} día{'s' if days_until > 1 else ''}: {case.caption[:60]}"
            )
        elif days_until <= 7:
            priority = "normal"
            title = f"Plazo próximo ({days_until} días): {case.caption[:60]}"
        else:
            priority = "low"
            title = f"Plazo en {days_until} días: {case.caption[:60]}"

        # Check if notification already exists for this deadline
        existing = await db.execute(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.resource_type == "case",
                Notification.resource_id == str(case.id),
                Notification.category == "deadline",
                Notification.created_at >= now - timedelta(hours=24),
            )
        )
        if (existing.scalar() or 0) > 0:
            continue  # Already notified today

        if case.assigned_to:
            await create_notification(
                db=db,
                user_id=case.assigned_to,
                title=title,
                message=f"Causa {case.internal_id} — {case.caption}\n"
                f"Tribunal: {case.court or 'N/D'}\n"
                f"Vencimiento: {case.next_deadline.strftime('%d/%m/%Y %H:%M')}",
                category="deadline",
                priority=priority,
                resource_type="case",
                resource_id=str(case.id),
            )
            generated.append(
                {
                    "case_id": str(case.id),
                    "internal_id": case.internal_id,
                    "priority": priority,
                    "days_until": days_until,
                }
            )

    return generated


# ═══════════════════════════════════════════
# READ/MANAGE NOTIFICATIONS
# ═══════════════════════════════════════════
async def get_user_notifications(
    db: AsyncSession,
    user_id: uuid.UUID,
    unread_only: bool = False,
    limit: int = 50,
) -> list[Notification]:
    stmt = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        stmt = stmt.where(Notification.is_read == False)
    stmt = stmt.order_by(Notification.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def mark_as_read(
    db: AsyncSession,
    notification_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    notif = await db.get(Notification, notification_id)
    if not notif or notif.user_id != user_id:
        return False
    notif.is_read = True
    notif.read_at = datetime.now(timezone.utc)
    return True


async def mark_all_read(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.is_read == False,
        )
    )
    notifs = result.scalars().all()
    now = datetime.now(timezone.utc)
    for n in notifs:
        n.is_read = True
        n.read_at = now
    return len(notifs)


async def get_unread_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.is_read == False,
        )
    )
    return result.scalar() or 0
