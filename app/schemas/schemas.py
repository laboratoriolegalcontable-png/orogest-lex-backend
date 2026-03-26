"""
OroGest Lex — Pydantic Schemas
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


# ═══════════════════════════════════════════
# AUTH
# ═══════════════════════════════════════════
class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


# ═══════════════════════════════════════════
# USER
# ═══════════════════════════════════════════
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=2, max_length=255)
    role: str = "pasante"


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: str | None = None
    is_active: bool | None = None


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    last_login: datetime | None = None

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════
# CASE
# ═══════════════════════════════════════════
class CaseCreate(BaseModel):
    case_number: str | None = None
    caption: str = Field(min_length=5, max_length=500)
    branch: str
    jurisdiction: str | None = None
    court: str | None = None
    judge: str | None = None
    prosecutor: str | None = None
    client_name: str = Field(min_length=2, max_length=255)
    client_role: str | None = None
    filing_date: datetime | None = None
    next_deadline: datetime | None = None
    notes: str | None = None


class CaseUpdate(BaseModel):
    caption: str | None = None
    status: str | None = None
    court: str | None = None
    judge: str | None = None
    prosecutor: str | None = None
    risk_score: float | None = None
    risk_details: dict | None = None
    next_deadline: datetime | None = None
    notes: str | None = None
    assigned_to: uuid.UUID | None = None


class CaseResponse(BaseModel):
    id: uuid.UUID
    internal_id: str
    case_number: str | None
    caption: str
    branch: str
    status: str
    jurisdiction: str | None
    court: str | None
    client_name: str
    client_role: str | None
    risk_score: float | None
    next_deadline: datetime | None
    assigned_to: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CaseListResponse(BaseModel):
    cases: list[CaseResponse]
    total: int
    page: int
    per_page: int


# ═══════════════════════════════════════════
# DOCUMENT
# ═══════════════════════════════════════════
class DocumentCreate(BaseModel):
    title: str = Field(min_length=3, max_length=500)
    doc_type: str
    content: str | None = None
    case_id: uuid.UUID | None = None


class DocumentResponse(BaseModel):
    id: uuid.UUID
    title: str
    doc_type: str
    content: str | None
    verification_flags: dict | None
    case_id: uuid.UUID | None
    created_by: uuid.UUID
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════
# AI PROXY
# ═══════════════════════════════════════════
class AIQueryRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)
    case_id: uuid.UUID | None = None
    workflow: str | None = None  # escrito_blindado / due_diligence / estrategia_procesal / escudo_patrimonial
    system_prompt_override: str | None = None


class AIQueryResponse(BaseModel):
    response: str
    conversation_id: uuid.UUID
    tokens_used: int
    verification_flags: dict | None = None
    model: str


# ═══════════════════════════════════════════
# PROPERTY
# ═══════════════════════════════════════════
class PropertyCreate(BaseModel):
    title: str = Field(min_length=3, max_length=500)
    address: str
    city: str
    province: str
    country: str = "ARG"
    property_type: str
    asking_price_usd: float | None = None
    asking_price_ars: float | None = None
    folio_real: str | None = None
    matricula: str | None = None
    owner_name: str | None = None
    notes: str | None = None


class PropertyResponse(BaseModel):
    id: uuid.UUID
    title: str
    address: str
    city: str
    province: str
    country: str
    property_type: str
    status: str
    asking_price_usd: float | None
    dd_risk_level: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════
# AUDIT
# ═══════════════════════════════════════════
class AuditLogResponse(BaseModel):
    id: uuid.UUID
    timestamp: datetime
    user_id: uuid.UUID | None
    action: str
    resource_type: str | None
    resource_id: str | None
    details: dict | None
    current_hash: str

    model_config = {"from_attributes": True}
