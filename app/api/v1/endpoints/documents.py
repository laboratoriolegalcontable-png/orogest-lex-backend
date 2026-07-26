"""
OroGest Lex — Documents Endpoints (Fase 10)
CRUD for legal documents with versioning and memory integration.
"""

import hashlib
import logging
import uuid
from datetime import UTC

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RequirePermission
from app.core.security import Permission
from app.db.session import get_db
from app.models.models import Document, User
from app.schemas.schemas import DocumentCreate, DocumentResponse
from app.services.audit_service import create_audit_entry

logger = logging.getLogger("orogest.documents")

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/", response_model=list[DocumentResponse])
async def list_documents(
    case_id: uuid.UUID | None = None,
    doc_type: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.DOCS_READ)),
):
    stmt = select(Document).where(Document.is_deleted == False)

    if case_id:
        stmt = stmt.where(Document.case_id == case_id)
    if doc_type:
        stmt = stmt.where(Document.doc_type == doc_type)

    stmt = stmt.order_by(Document.updated_at.desc()).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.DOCS_READ)),
):
    doc = await db.get(Document, doc_id)
    if not doc or doc.is_deleted:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return doc


@router.post("/", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    body: DocumentCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.DOCS_WRITE)),
):
    # Compute content hash for integrity
    content_hash = None
    if body.content:
        content_hash = hashlib.sha256(body.content.encode("utf-8")).hexdigest()

    doc = Document(
        title=body.title,
        doc_type=body.doc_type,
        content=body.content,
        case_id=body.case_id,
        created_by=user.id,
        file_hash=content_hash,
        version=1,
    )
    db.add(doc)
    await db.flush()

    # Store in memory for RAG if content exists
    if body.content:
        try:
            from app.memory.memory_service import store_memory

            await store_memory(
                db=db,
                content=body.content,
                source_type="document",
                source_id=str(doc.id),
                branch=None,  # Could infer from case
                user_id=user.id,
                tags=body.doc_type,
            )
        except Exception as e:  # noqa: BLE001 — memory storage is non-critical, must not fail the document write
            logger.warning(f"store_memory failed for document {doc.id}: {e}")

    await create_audit_entry(
        db,
        action="document.create",
        user_id=user.id,
        resource_type="document",
        resource_id=str(doc.id),
        details={"title": doc.title, "doc_type": doc.doc_type, "has_content": bool(body.content)},
        ip_address=request.client.host if request.client else None,
    )

    return doc


@router.put("/{doc_id}", response_model=DocumentResponse)
async def update_document(
    doc_id: uuid.UUID,
    body: DocumentCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.DOCS_WRITE)),
):
    """
    Update document — creates a new version.
    The old version is kept linked via parent_version_id.
    """
    old_doc = await db.get(Document, doc_id)
    if not old_doc or old_doc.is_deleted:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    content_hash = None
    if body.content:
        content_hash = hashlib.sha256(body.content.encode("utf-8")).hexdigest()

    # Create new version
    new_doc = Document(
        title=body.title,
        doc_type=body.doc_type,
        content=body.content,
        case_id=body.case_id or old_doc.case_id,
        created_by=user.id,
        file_hash=content_hash,
        version=old_doc.version + 1,
        parent_version_id=old_doc.id,
    )
    db.add(new_doc)

    # Soft-delete old version
    from datetime import datetime

    old_doc.is_deleted = True
    old_doc.deleted_at = datetime.now(UTC)

    await db.flush()

    # Update memory
    if body.content:
        try:
            from app.memory.memory_service import delete_memory_by_source, store_memory

            await delete_memory_by_source(db, "document", str(old_doc.id))
            await store_memory(
                db=db,
                content=body.content,
                source_type="document",
                source_id=str(new_doc.id),
                user_id=user.id,
                tags=body.doc_type,
            )
        except Exception as e:  # noqa: BLE001 — memory storage is non-critical, must not fail the document write
            logger.warning(f"memory sync failed for document {new_doc.id}: {e}")

    await create_audit_entry(
        db,
        action="document.update",
        user_id=user.id,
        resource_type="document",
        resource_id=str(new_doc.id),
        details={
            "old_version": old_doc.version,
            "new_version": new_doc.version,
            "parent_id": str(old_doc.id),
        },
        ip_address=request.client.host if request.client else None,
    )

    return new_doc


@router.get("/{doc_id}/history", response_model=list[DocumentResponse])
async def document_history(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.DOCS_READ)),
):
    """Get version history for a document by tracing parent_version_id chain."""
    versions = []
    current_id = doc_id

    for _ in range(50):  # safety limit
        doc = await db.get(Document, current_id)
        if not doc:
            break
        versions.append(doc)
        if not doc.parent_version_id:
            break
        current_id = doc.parent_version_id

    return versions


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    doc_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.DOCS_DELETE)),
):
    doc = await db.get(Document, doc_id)
    if not doc or doc.is_deleted:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    from datetime import datetime

    doc.is_deleted = True
    doc.deleted_at = datetime.now(UTC)

    # Clean memory
    try:
        from app.memory.memory_service import delete_memory_by_source

        await delete_memory_by_source(db, "document", str(doc.id))
    except Exception as e:  # noqa: BLE001 — memory cleanup is non-critical, must not block the delete
        logger.warning(f"delete_memory_by_source failed for document {doc.id}: {e}")

    await create_audit_entry(
        db,
        action="document.delete",
        user_id=user.id,
        resource_type="document",
        resource_id=str(doc.id),
        ip_address=request.client.host if request.client else None,
    )
