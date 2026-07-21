"""
OroGest Lex — Cases Endpoints (Causas judiciales)
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RequirePermission
from app.core.security import Permission
from app.db.session import get_db
from app.models.models import Case, User
from app.schemas.schemas import CaseCreate, CaseListResponse, CaseResponse, CaseUpdate
from app.services.audit_service import create_audit_entry

router = APIRouter(prefix="/cases", tags=["cases"])


@router.get("/", response_model=CaseListResponse)
async def list_cases(
    branch: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.CASES_READ)),
):
    query = select(Case).where(Case.is_deleted == False)
    count_query = select(func.count()).select_from(Case).where(Case.is_deleted == False)

    if branch:
        query = query.where(Case.branch == branch)
        count_query = count_query.where(Case.branch == branch)
    if status_filter:
        query = query.where(Case.status == status_filter)
        count_query = count_query.where(Case.status == status_filter)

    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(Case.updated_at.desc()).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    cases = result.scalars().all()

    return CaseListResponse(
        cases=[CaseResponse.model_validate(c) for c in cases],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.CASES_READ)),
):
    case = await db.get(Case, case_id)
    if not case or case.is_deleted:
        raise HTTPException(status_code=404, detail="Causa no encontrada")
    return case


@router.post("/", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
async def create_case(
    body: CaseCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.CASES_WRITE)),
):
    case = Case(
        case_number=body.case_number,
        caption=body.caption,
        branch=body.branch,
        jurisdiction=body.jurisdiction,
        court=body.court,
        judge=body.judge,
        prosecutor=body.prosecutor,
        client_name=body.client_name,
        client_role=body.client_role,
        filing_date=body.filing_date,
        next_deadline=body.next_deadline,
        notes=body.notes,
        assigned_to=user.id,
    )
    db.add(case)
    await db.flush()

    await create_audit_entry(
        db,
        action="case.create",
        user_id=user.id,
        resource_type="case",
        resource_id=str(case.id),
        details={"branch": case.branch, "caption": case.caption},
        ip_address=request.client.host if request.client else None,
    )

    return case


@router.patch("/{case_id}", response_model=CaseResponse)
async def update_case(
    case_id: uuid.UUID,
    body: CaseUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.CASES_WRITE)),
):
    case = await db.get(Case, case_id)
    if not case or case.is_deleted:
        raise HTTPException(status_code=404, detail="Causa no encontrada")

    update_data = body.model_dump(exclude_unset=True)
    changes = {}
    for field, value in update_data.items():
        old_value = getattr(case, field)
        if old_value != value:
            changes[field] = {"old": str(old_value), "new": str(value)}
            setattr(case, field, value)

    if changes:
        await create_audit_entry(
            db,
            action="case.update",
            user_id=user.id,
            resource_type="case",
            resource_id=str(case.id),
            details={"changes": changes},
            ip_address=request.client.host if request.client else None,
        )

    return case


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case(
    case_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.CASES_DELETE)),
):
    case = await db.get(Case, case_id)
    if not case or case.is_deleted:
        raise HTTPException(status_code=404, detail="Causa no encontrada")

    # Soft delete
    from datetime import datetime, timezone

    case.is_deleted = True
    case.deleted_at = datetime.now(timezone.utc)

    await create_audit_entry(
        db,
        action="case.delete",
        user_id=user.id,
        resource_type="case",
        resource_id=str(case.id),
        ip_address=request.client.host if request.client else None,
    )
