"""
OroGest Lex — Case Timeline Endpoint
Complete activity feed for a case, aggregated from audit log.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RequirePermission
from app.core.security import Permission
from app.db.session import get_db
from app.models.models import AuditLog, Case, Document, User

router = APIRouter(prefix="/timeline", tags=["timeline"])

# Action labels for human-readable timeline
ACTION_LABELS = {
    "case.create": "Causa creada",
    "case.update": "Causa actualizada",
    "case.delete": "Causa eliminada",
    "document.create": "Documento creado",
    "document.update": "Documento actualizado (nueva versión)",
    "document.delete": "Documento eliminado",
    "ai.query": "Consulta al asistente IA",
    "ai.draft": "Escrito generado por IA",
    "orchestrator.execute": "Ejecución del orquestador",
    "export.escrito": "Escrito exportado a DOCX",
    "export.carta_documento": "Carta documento exportada",
    "file.upload": "Archivo adjuntado",
    "client.link_case": "Cliente vinculado a la causa",
    "property.due_diligence.update": "Due diligence actualizado",
}


@router.get("/case/{case_id}")
async def case_timeline(
    case_id: uuid.UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.CASES_READ)),
):
    """
    Get complete activity timeline for a case.
    Aggregates from audit log + documents + AI conversations.
    """
    case = await db.get(Case, case_id)
    if not case or case.is_deleted:
        raise HTTPException(status_code=404, detail="Causa no encontrada")

    case_id_str = str(case_id)

    # Get all audit entries related to this case
    stmt = (
        select(AuditLog)
        .where(
            or_(
                # Direct case actions
                (AuditLog.resource_type == "case") & (AuditLog.resource_id == case_id_str),
                # Documents of this case (we check details JSON)
                (AuditLog.resource_type == "document")
                & (AuditLog.details["case_id"].astext == case_id_str),
                # AI conversations linked to this case
                (AuditLog.resource_type == "ai_conversation")
                & (AuditLog.details["case_id"].astext == case_id_str),
            )
        )
        .order_by(AuditLog.timestamp.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )

    result = await db.execute(stmt)
    entries = result.scalars().all()

    # Also get documents for this case (for richer timeline)
    docs_result = await db.execute(
        select(Document)
        .where(Document.case_id == case_id)
        .order_by(Document.created_at.desc())
        .limit(10)
    )
    docs = {str(d.id): d for d in docs_result.scalars().all()}

    timeline = []
    for entry in entries:
        event = {
            "id": str(entry.id),
            "timestamp": entry.timestamp.isoformat(),
            "action": entry.action,
            "label": ACTION_LABELS.get(entry.action, entry.action),
            "user_id": str(entry.user_id) if entry.user_id else None,
            "resource_type": entry.resource_type,
            "resource_id": entry.resource_id,
        }

        # Enrich with details
        details = entry.details or {}
        if "changes" in details:
            event["changes"] = details["changes"]
        if "tokens" in details:
            event["ai_tokens"] = details["tokens"]
        if "workflow" in details:
            event["workflow"] = details["workflow"]
        if "filename" in details:
            event["filename"] = details["filename"]

        # If it's a document action, add doc title
        if entry.resource_type == "document" and entry.resource_id in docs:
            event["document_title"] = docs[entry.resource_id].title

        timeline.append(event)

    return {
        "case_id": case_id_str,
        "case_caption": case.caption,
        "case_branch": case.branch,
        "total_events": len(timeline),
        "page": page,
        "timeline": timeline,
    }


@router.get("/user/{user_id}")
async def user_activity(
    user_id: uuid.UUID,
    days: int = Query(7, ge=1, le=90),
    page: int = Query(1, ge=1),
    per_page: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.AUDIT_READ)),
):
    """Get activity timeline for a specific user."""
    from datetime import timedelta

    since = datetime.now(UTC) - timedelta(days=days)

    stmt = (
        select(AuditLog)
        .where(
            AuditLog.user_id == user_id,
            AuditLog.timestamp >= since,
        )
        .order_by(AuditLog.timestamp.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )

    result = await db.execute(stmt)
    entries = result.scalars().all()

    return {
        "user_id": str(user_id),
        "days": days,
        "total_events": len(entries),
        "timeline": [
            {
                "timestamp": e.timestamp.isoformat(),
                "action": e.action,
                "label": ACTION_LABELS.get(e.action, e.action),
                "resource_type": e.resource_type,
                "resource_id": e.resource_id,
            }
            for e in entries
        ],
    }
