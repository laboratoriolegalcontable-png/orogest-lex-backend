"""
OroGest Lex — Global Search Endpoint
Unified search across cases, documents, and properties using trigram similarity.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.models import Case, Document, Property, User

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/")
async def global_search(
    q: str = Query(min_length=2, max_length=200),
    scope: str = Query("all", pattern="^(all|cases|documents|properties)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Search across all entity types with a single query.
    Uses ILIKE for portability; upgrade to pg_trgm for production fuzzy search.
    """
    pattern = f"%{q}%"
    results = []

    # ── Cases ──
    if scope in ("all", "cases"):
        stmt = (
            select(
                Case.id,
                Case.internal_id,
                Case.caption,
                Case.branch,
                Case.status,
                Case.client_name,
                Case.case_number,
                Case.updated_at,
            )
            .where(
                Case.is_deleted == False,
                or_(
                    Case.caption.ilike(pattern),
                    Case.client_name.ilike(pattern),
                    Case.case_number.ilike(pattern),
                    Case.notes.ilike(pattern),
                    Case.internal_id.ilike(pattern),
                ),
            )
            .order_by(Case.updated_at.desc())
            .limit(per_page if scope == "cases" else 10)
        )
        for row in (await db.execute(stmt)).all():
            results.append(
                {
                    "type": "case",
                    "id": str(row.id),
                    "title": row.caption,
                    "subtitle": f"{row.branch} — {row.client_name}",
                    "status": row.status,
                    "internal_id": row.internal_id,
                    "case_number": row.case_number,
                    "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                }
            )

    # ── Documents ──
    if scope in ("all", "documents"):
        stmt = (
            select(
                Document.id,
                Document.title,
                Document.doc_type,
                Document.version,
                Document.updated_at,
            )
            .where(
                Document.is_deleted == False,
                or_(
                    Document.title.ilike(pattern),
                    Document.content.ilike(pattern),
                ),
            )
            .order_by(Document.updated_at.desc())
            .limit(per_page if scope == "documents" else 10)
        )
        for row in (await db.execute(stmt)).all():
            results.append(
                {
                    "type": "document",
                    "id": str(row.id),
                    "title": row.title,
                    "subtitle": f"{row.doc_type} — v{row.version}",
                    "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                }
            )

    # ── Properties ──
    if scope in ("all", "properties"):
        stmt = (
            select(
                Property.id,
                Property.title,
                Property.address,
                Property.city,
                Property.status,
                Property.dd_risk_level,
                Property.updated_at,
            )
            .where(
                Property.is_deleted == False,
                or_(
                    Property.title.ilike(pattern),
                    Property.address.ilike(pattern),
                    Property.owner_name.ilike(pattern),
                    Property.folio_real.ilike(pattern),
                ),
            )
            .order_by(Property.updated_at.desc())
            .limit(per_page if scope == "properties" else 10)
        )
        for row in (await db.execute(stmt)).all():
            results.append(
                {
                    "type": "property",
                    "id": str(row.id),
                    "title": row.title,
                    "subtitle": f"{row.address}, {row.city}",
                    "status": row.status,
                    "risk_level": row.dd_risk_level,
                    "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                }
            )

    # Sort all by updated_at descending
    results.sort(key=lambda x: x.get("updated_at", ""), reverse=True)

    return {
        "query": q,
        "scope": scope,
        "total_results": len(results),
        "results": results[:per_page],
    }
