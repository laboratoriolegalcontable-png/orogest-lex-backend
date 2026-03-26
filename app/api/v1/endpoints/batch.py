"""
OroGest Lex — Batch Operations Endpoints
Bulk operations for managing multiple cases/documents at once.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RequirePermission, RequireRole
from app.core.security import Permission, Role
from app.db.session import get_db
from app.models.models import Case, Document, User
from app.services.audit_service import create_audit_entry

router = APIRouter(prefix="/batch", tags=["batch"])


class BatchStatusUpdate(BaseModel):
    case_ids: list[uuid.UUID] = Field(min_length=1, max_length=50)
    new_status: str


class BatchAssign(BaseModel):
    case_ids: list[uuid.UUID] = Field(min_length=1, max_length=50)
    assign_to: uuid.UUID


class BatchResult(BaseModel):
    total: int
    updated: int
    failed: int
    errors: list[str]


@router.post("/cases/update-status", response_model=BatchResult)
async def batch_update_case_status(
    body: BatchStatusUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.CASES_WRITE)),
):
    """Update status for multiple cases at once."""
    updated = 0
    failed = 0
    errors = []

    for case_id in body.case_ids:
        case = await db.get(Case, case_id)
        if not case or case.is_deleted:
            failed += 1
            errors.append(f"Causa {case_id}: no encontrada")
            continue

        old_status = case.status
        case.status = body.new_status
        updated += 1

        await create_audit_entry(
            db, action="case.batch_update", user_id=user.id,
            resource_type="case", resource_id=str(case_id),
            details={"old_status": old_status, "new_status": body.new_status, "batch": True},
            ip_address=request.client.host if request.client else None,
        )

    return BatchResult(
        total=len(body.case_ids),
        updated=updated,
        failed=failed,
        errors=errors,
    )


@router.post("/cases/assign", response_model=BatchResult)
async def batch_assign_cases(
    body: BatchAssign,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireRole(Role.DIRECTOR)),
):
    """Assign multiple cases to a user. DIRECTOR only."""
    # Verify target user exists
    target = await db.get(User, body.assign_to)
    if not target or target.is_deleted or not target.is_active:
        raise HTTPException(status_code=404, detail="Usuario destino no encontrado o inactivo")

    updated = 0
    failed = 0
    errors = []

    for case_id in body.case_ids:
        case = await db.get(Case, case_id)
        if not case or case.is_deleted:
            failed += 1
            errors.append(f"Causa {case_id}: no encontrada")
            continue

        old_assigned = str(case.assigned_to) if case.assigned_to else None
        case.assigned_to = body.assign_to
        updated += 1

        await create_audit_entry(
            db, action="case.batch_assign", user_id=user.id,
            resource_type="case", resource_id=str(case_id),
            details={
                "old_assigned": old_assigned,
                "new_assigned": str(body.assign_to),
                "batch": True,
            },
            ip_address=request.client.host if request.client else None,
        )

    return BatchResult(
        total=len(body.case_ids),
        updated=updated,
        failed=failed,
        errors=errors,
    )


class BatchTagRequest(BaseModel):
    case_ids: list[uuid.UUID] = Field(min_length=1, max_length=50)
    tag_key: str = Field(min_length=1, max_length=50)
    tag_value: str = Field(min_length=1, max_length=200)


@router.post("/cases/tag", response_model=BatchResult)
async def batch_tag_cases(
    body: BatchTagRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.CASES_WRITE)),
):
    """Add a metadata tag to multiple cases."""
    updated = 0
    failed = 0
    errors = []

    for case_id in body.case_ids:
        case = await db.get(Case, case_id)
        if not case or case.is_deleted:
            failed += 1
            errors.append(f"Causa {case_id}: no encontrada")
            continue

        metadata = case.metadata_json or {}
        if "tags" not in metadata:
            metadata["tags"] = {}
        metadata["tags"][body.tag_key] = body.tag_value
        case.metadata_json = metadata
        updated += 1

    if updated > 0:
        await create_audit_entry(
            db, action="case.batch_tag", user_id=user.id,
            details={
                "tag": f"{body.tag_key}={body.tag_value}",
                "count": updated,
                "batch": True,
            },
            ip_address=request.client.host if request.client else None,
        )

    return BatchResult(
        total=len(body.case_ids),
        updated=updated,
        failed=failed,
        errors=errors,
    )
