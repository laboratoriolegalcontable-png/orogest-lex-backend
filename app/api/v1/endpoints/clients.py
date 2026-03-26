"""
OroGest Lex — Clients Endpoints
CRUD for client management with UIF/KYC compliance tracking.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RequirePermission, get_current_user
from app.core.security import Permission
from app.db.session import get_db
from app.models.models import CaseClient, Client, User
from app.services.audit_service import create_audit_entry

router = APIRouter(prefix="/clients", tags=["clients"])


# ── Schemas ──
class ClientCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    document_type: str | None = None
    document_number: str | None = None
    nationality: str = "argentina"
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    province: str | None = None
    country: str = "ARG"
    client_type: str = "persona_fisica"
    client_category: str | None = None
    is_pep: bool = False
    notes: str | None = None


class ClientUpdate(BaseModel):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    province: str | None = None
    is_pep: bool | None = None
    pep_details: str | None = None
    kyc_completed: bool | None = None
    client_category: str | None = None
    notes: str | None = None


class ClientResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    document_type: str | None
    document_number: str | None
    nationality: str
    email: str | None
    phone: str | None
    address: str | None
    city: str | None
    province: str | None
    country: str
    client_type: str
    client_category: str | None
    is_pep: bool
    kyc_completed: bool
    kyc_date: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class LinkClientRequest(BaseModel):
    client_id: uuid.UUID
    case_id: uuid.UUID
    role: str = Field(min_length=3)
    is_primary: bool = True


# ── Endpoints ──
@router.get("/", response_model=list[ClientResponse])
async def list_clients(
    q: str | None = None,
    client_type: str | None = None,
    pep_only: bool = False,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.CASES_READ)),
):
    stmt = select(Client).where(Client.is_deleted == False)

    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(or_(
            Client.full_name.ilike(pattern),
            Client.document_number.ilike(pattern),
            Client.email.ilike(pattern),
        ))
    if client_type:
        stmt = stmt.where(Client.client_type == client_type)
    if pep_only:
        stmt = stmt.where(Client.is_pep == True)

    stmt = stmt.order_by(Client.full_name.asc()).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.CASES_READ)),
):
    client = await db.get(Client, client_id)
    if not client or client.is_deleted:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return client


@router.post("/", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(
    body: ClientCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.CASES_WRITE)),
):
    # Check duplicate by document
    if body.document_number:
        existing = await db.execute(
            select(Client).where(
                Client.document_number == body.document_number,
                Client.is_deleted == False,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Ya existe un cliente con ese documento")

    client = Client(**body.model_dump())
    db.add(client)
    await db.flush()

    await create_audit_entry(
        db, action="client.create", user_id=user.id,
        resource_type="client", resource_id=str(client.id),
        details={"name": client.full_name, "type": client.client_type, "pep": client.is_pep},
        ip_address=request.client.host if request.client else None,
    )

    return client


@router.patch("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: uuid.UUID,
    body: ClientUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.CASES_WRITE)),
):
    client = await db.get(Client, client_id)
    if not client or client.is_deleted:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    changes = {}
    update_data = body.model_dump(exclude_unset=True)

    # Track KYC completion timestamp
    if "kyc_completed" in update_data and update_data["kyc_completed"] and not client.kyc_completed:
        client.kyc_date = datetime.now(timezone.utc)

    for field, value in update_data.items():
        old = getattr(client, field)
        if old != value:
            changes[field] = {"old": str(old), "new": str(value)}
            setattr(client, field, value)

    if changes:
        await create_audit_entry(
            db, action="client.update", user_id=user.id,
            resource_type="client", resource_id=str(client.id),
            details={"changes": changes},
            ip_address=request.client.host if request.client else None,
        )

    return client


@router.post("/link-case")
async def link_client_to_case(
    body: LinkClientRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.CASES_WRITE)),
):
    """Link a client to a case with a specific role (imputado, actor, etc.)."""
    link = CaseClient(
        case_id=body.case_id,
        client_id=body.client_id,
        role=body.role,
        is_primary=body.is_primary,
    )
    db.add(link)

    try:
        await db.flush()
    except Exception:
        raise HTTPException(status_code=409, detail="Este cliente ya está vinculado a la causa con ese rol")

    await create_audit_entry(
        db, action="client.link_case", user_id=user.id,
        resource_type="case_client",
        details={"case_id": str(body.case_id), "client_id": str(body.client_id), "role": body.role},
        ip_address=request.client.host if request.client else None,
    )

    return {"status": "linked", "role": body.role}


@router.get("/{client_id}/cases")
async def get_client_cases(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.CASES_READ)),
):
    """Get all cases for a specific client."""
    result = await db.execute(
        select(CaseClient).where(CaseClient.client_id == client_id)
    )
    links = result.scalars().all()

    return [
        {
            "case_id": str(link.case_id),
            "role": link.role,
            "is_primary": link.is_primary,
            "case_caption": link.case.caption if link.case else None,
            "case_branch": link.case.branch if link.case else None,
            "case_status": link.case.status if link.case else None,
        }
        for link in links
    ]
