"""
OroGest Lex — Audit Service
SHA-256 chained log for tamper-evident audit trail.
"""

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import compute_audit_hash
from app.models.models import AuditLog


async def create_audit_entry(
    db: AsyncSession,
    action: str,
    user_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    """Create a new audit log entry with SHA-256 chain link."""

    # Get the last hash in the chain
    result = await db.execute(
        select(AuditLog.current_hash).order_by(AuditLog.timestamp.desc()).limit(1)
    )
    last_hash = result.scalar_one_or_none() or "GENESIS"

    # Build the event data string for hashing
    event_data = json.dumps(
        {
            "action": action,
            "user_id": str(user_id) if user_id else None,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        sort_keys=True,
    )

    current_hash = compute_audit_hash(last_hash, event_data)

    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id else None,
        details=details,
        ip_address=ip_address,
        previous_hash=last_hash,
        current_hash=current_hash,
    )
    db.add(entry)
    # Note: commit happens in the session context manager
    return entry
