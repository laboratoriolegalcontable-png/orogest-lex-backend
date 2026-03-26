"""
OroGest Lex — Properties Endpoints (Fase 11)
CRUD for real estate properties with due diligence workflow integration.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RequirePermission, get_current_user
from app.core.security import Permission
from app.db.session import get_db
from app.models.models import Property, User
from app.schemas.schemas import PropertyCreate, PropertyResponse
from app.services.audit_service import create_audit_entry

router = APIRouter(prefix="/properties", tags=["properties"])


# ── Due Diligence Checklist Templates ──
DD_CHECKLIST_ARG = {
    "dominio_folio_real": {"label": "Dominio — Folio Real / Matrícula RPI", "status": "pendiente"},
    "inhibiciones": {"label": "Inhibiciones RENAPER / RNI sobre vendedor", "status": "pendiente"},
    "deudas_abl": {"label": "Deudas ABL", "status": "pendiente"},
    "deudas_expensas": {"label": "Deudas Expensas", "status": "pendiente"},
    "hipotecas_embargos": {"label": "Hipotecas / Embargos", "status": "pendiente"},
    "planos_municipales": {"label": "Planos municipales + subdivisión", "status": "pendiente"},
    "certificado_agip_arba": {"label": "Certificados no deuda AGIP / ARBA", "status": "pendiente"},
    "uif_pep_check": {"label": "UIF: PEP check vendedor/comprador (Res. UIF 21/2023)", "status": "pendiente"},
    "cadena_dominio": {"label": "Boleto → Escritura → Posesión: cadena completa", "status": "pendiente"},
    "indice_aplicable": {"label": "Índice aplicable: UVA / CER / libre", "status": "pendiente"},
}

DD_CHECKLIST_ESP = {
    "nota_simple": {"label": "Nota Simple Registro de la Propiedad", "status": "pendiente"},
    "catastro": {"label": "Catastro: superficie real vs. registral", "status": "pendiente"},
    "cargas": {"label": "Cargas: hipotecas, servidumbres, usufructos", "status": "pendiente"},
    "ibi": {"label": "IBI al día / Comunidad de propietarios", "status": "pendiente"},
    "cedula_habitabilidad": {"label": "Cédula de habitabilidad vigente", "status": "pendiente"},
    "plusvalia": {"label": "Plusvalía municipal: quién absorbe", "status": "pendiente"},
}

DD_CHECKLIST_URY = {
    "certificado_dominio": {"label": "Certificado de dominio Registro de la Propiedad", "status": "pendiente"},
    "bps_dgi": {"label": "BPS / DGI: deudas del vendedor", "status": "pendiente"},
    "plano_mensura": {"label": "Plano mensura aprobado", "status": "pendiente"},
    "promesa_compraventa": {"label": "Promesa de compraventa con fecha cierta", "status": "pendiente"},
}


def get_dd_template(country: str) -> dict:
    templates = {"ARG": DD_CHECKLIST_ARG, "ESP": DD_CHECKLIST_ESP, "URY": DD_CHECKLIST_URY}
    return templates.get(country, DD_CHECKLIST_ARG)


def compute_risk_level(checklist: dict) -> str:
    """Compute due diligence risk: verde / amarillo / rojo."""
    if not checklist:
        return "rojo"

    statuses = [item.get("status", "pendiente") for item in checklist.values()]
    pendiente_count = statuses.count("pendiente")
    problema_count = statuses.count("problema")
    total = len(statuses)

    if problema_count > 0:
        return "rojo"
    if pendiente_count == total:
        return "rojo"  # Nothing reviewed yet
    if pendiente_count > 0:
        return "amarillo"
    return "verde"


# ── Schemas ──
class DDItemUpdate(BaseModel):
    status: str  # "ok" | "problema" | "pendiente" | "no_aplica"
    notes: str | None = None


class DDUpdateRequest(BaseModel):
    items: dict[str, DDItemUpdate]


# ── Endpoints ──
@router.get("/", response_model=list[PropertyResponse])
async def list_properties(
    status_filter: str | None = Query(None, alias="status"),
    country: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.REALESTATE_READ)),
):
    stmt = select(Property).where(Property.is_deleted == False)

    if status_filter:
        stmt = stmt.where(Property.status == status_filter)
    if country:
        stmt = stmt.where(Property.country == country)

    stmt = stmt.order_by(Property.updated_at.desc()).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{prop_id}", response_model=PropertyResponse)
async def get_property(
    prop_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.REALESTATE_READ)),
):
    prop = await db.get(Property, prop_id)
    if not prop or prop.is_deleted:
        raise HTTPException(status_code=404, detail="Propiedad no encontrada")
    return prop


@router.post("/", response_model=PropertyResponse, status_code=status.HTTP_201_CREATED)
async def create_property(
    body: PropertyCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.REALESTATE_WRITE)),
):
    # Auto-generate DD checklist based on country
    dd_checklist = get_dd_template(body.country)

    prop = Property(
        title=body.title,
        address=body.address,
        city=body.city,
        province=body.province,
        country=body.country,
        property_type=body.property_type,
        asking_price_usd=body.asking_price_usd,
        asking_price_ars=body.asking_price_ars,
        folio_real=body.folio_real,
        matricula=body.matricula,
        owner_name=body.owner_name,
        notes=body.notes,
        dd_checklist=dd_checklist,
        dd_risk_level="rojo",  # starts as rojo until DD is done
        status="captado",
    )
    db.add(prop)
    await db.flush()

    await create_audit_entry(
        db,
        action="property.create",
        user_id=user.id,
        resource_type="property",
        resource_id=str(prop.id),
        details={"title": prop.title, "country": prop.country},
        ip_address=request.client.host if request.client else None,
    )

    return prop


@router.post("/{prop_id}/due-diligence")
async def update_due_diligence(
    prop_id: uuid.UUID,
    body: DDUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.REALESTATE_WRITE)),
):
    """
    Update individual items in the due diligence checklist.
    Automatically recalculates risk level.
    """
    prop = await db.get(Property, prop_id)
    if not prop or prop.is_deleted:
        raise HTTPException(status_code=404, detail="Propiedad no encontrada")

    checklist = prop.dd_checklist or {}
    changes = {}

    for key, update in body.items.items():
        if key in checklist:
            old_status = checklist[key].get("status")
            checklist[key]["status"] = update.status
            if update.notes:
                checklist[key]["notes"] = update.notes
            changes[key] = {"old": old_status, "new": update.status}

    prop.dd_checklist = checklist
    prop.dd_risk_level = compute_risk_level(checklist)

    # Check if DD is complete
    all_resolved = all(
        item.get("status") in ("ok", "no_aplica")
        for item in checklist.values()
    )
    if all_resolved:
        prop.dd_completed_at = datetime.now(timezone.utc)
        prop.status = "en_due_diligence"  # could transition to "publicado"

    await create_audit_entry(
        db,
        action="property.due_diligence.update",
        user_id=user.id,
        resource_type="property",
        resource_id=str(prop.id),
        details={"changes": changes, "risk_level": prop.dd_risk_level},
        ip_address=request.client.host if request.client else None,
    )

    return {
        "property_id": str(prop.id),
        "dd_risk_level": prop.dd_risk_level,
        "dd_checklist": prop.dd_checklist,
        "dd_completed": prop.dd_completed_at is not None,
    }


@router.get("/{prop_id}/due-diligence")
async def get_due_diligence(
    prop_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.REALESTATE_READ)),
):
    """Get the current due diligence checklist and risk level."""
    prop = await db.get(Property, prop_id)
    if not prop or prop.is_deleted:
        raise HTTPException(status_code=404, detail="Propiedad no encontrada")

    return {
        "property_id": str(prop.id),
        "title": prop.title,
        "country": prop.country,
        "dd_risk_level": prop.dd_risk_level,
        "dd_checklist": prop.dd_checklist,
        "dd_completed_at": prop.dd_completed_at,
    }


@router.delete("/{prop_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_property(
    prop_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.REALESTATE_WRITE)),
):
    prop = await db.get(Property, prop_id)
    if not prop or prop.is_deleted:
        raise HTTPException(status_code=404, detail="Propiedad no encontrada")

    prop.is_deleted = True
    prop.deleted_at = datetime.now(timezone.utc)

    await create_audit_entry(
        db,
        action="property.delete",
        user_id=user.id,
        resource_type="property",
        resource_id=str(prop.id),
        ip_address=request.client.host if request.client else None,
    )
