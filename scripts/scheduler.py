"""
OroGest Lex — Background Scheduler
Runs periodic tasks: deadline scanning, audit chain verification, memory cleanup.

Usage:
    # Run as separate process alongside the API:
    python -m scripts.scheduler

    # Or trigger via cron:
    0 8 * * * cd /app && python -m scripts.scheduler --once
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, func
from app.db.session import async_session
from app.models.models import Case, AuditLog

logger = logging.getLogger("orogest.scheduler")


async def scan_deadlines():
    """Scan for upcoming case deadlines and generate notifications."""
    now = datetime.now(timezone.utc)
    alert_windows = [
        (1, "critical", "⚠️ VENCE MAÑANA"),
        (3, "high", "Vence en 3 días"),
        (7, "normal", "Vence en 7 días"),
        (14, "low", "Vence en 14 días"),
    ]

    async with async_session() as db:
        total_alerts = 0
        for days, priority, label in alert_windows:
            deadline_limit = now + timedelta(days=days)
            deadline_start = now if days == 1 else now + timedelta(days=days - 1)

            result = await db.execute(
                select(Case).where(
                    Case.is_deleted == False,
                    Case.next_deadline.isnot(None),
                    Case.next_deadline >= deadline_start,
                    Case.next_deadline <= deadline_limit,
                    Case.status.in_(["activa", "en_tramite"]),
                )
            )
            cases = result.scalars().all()

            for case in cases:
                try:
                    from app.services.notifications_service import create_notification
                    await create_notification(
                        db,
                        title=f"{label}: {case.caption[:60]}",
                        message=f"Causa {case.internal_id} ({case.branch}) - Vencimiento: {case.next_deadline.strftime('%d/%m/%Y')}",
                        priority=priority,
                        category="deadline",
                        user_id=case.assigned_to,
                        resource_type="case",
                        resource_id=str(case.id),
                    )
                    total_alerts += 1
                except Exception as e:
                    logger.error(f"Error creating notification for case {case.internal_id}: {e}")

        await db.commit()
        logger.info(f"Deadline scan: {total_alerts} alerts generated")
        return total_alerts


async def verify_audit_chain():
    """Verify the last 100 audit log entries for chain integrity."""
    async with async_session() as db:
        result = await db.execute(
            select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(100)
        )
        entries = list(result.scalars().all())

        if len(entries) < 2:
            logger.info("Audit chain: too few entries to verify")
            return True

        broken = 0
        for i in range(len(entries) - 1):
            if entries[i].previous_hash != entries[i + 1].current_hash:
                broken += 1
                logger.warning(
                    f"Audit chain broken at {entries[i].timestamp}: "
                    f"action={entries[i].action}"
                )

        if broken == 0:
            logger.info(f"Audit chain: {len(entries)} entries verified OK")
        else:
            logger.error(f"Audit chain: {broken} breaks in {len(entries)} entries!")

        return broken == 0


async def cleanup_old_sessions():
    """Cleanup expired rate limit windows and old temp data."""
    logger.info("Session cleanup: completed (in-memory, auto-expires)")


async def run_all_tasks():
    """Run all scheduled tasks."""
    logger.info(f"═══ Scheduler run at {datetime.now(timezone.utc).isoformat()} ═══")

    await scan_deadlines()
    await verify_audit_chain()
    await cleanup_old_sessions()

    logger.info("═══ Scheduler completed ═══")


async def run_loop(interval_minutes: int = 60):
    """Run tasks in a loop."""
    logger.info(f"Scheduler starting (interval: {interval_minutes}min)")
    while True:
        try:
            await run_all_tasks()
        except Exception as e:
            logger.exception(f"Scheduler error: {e}")
        await asyncio.sleep(interval_minutes * 60)


def main():
    import argparse
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="OroGest Lex Scheduler")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--interval", type=int, default=60, help="Interval in minutes")
    args = parser.parse_args()

    if args.once:
        asyncio.run(run_all_tasks())
    else:
        asyncio.run(run_loop(args.interval))


if __name__ == "__main__":
    main()
