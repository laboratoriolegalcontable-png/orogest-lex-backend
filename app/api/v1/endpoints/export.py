"""
OroGest Lex — Export Endpoints
Generate downloadable DOCX, CSV, and Markdown files from system data.
"""

import csv
import io
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RequirePermission, get_current_user
from app.core.security import Permission
from app.db.session import get_db
from app.models.models import Case, Document, Property, User
from app.services.audit_service import create_audit_entry
from app.services.export_service import (
    generate_carta_documento_docx,
    generate_due_diligence_report_docx,
    generate_escrito_docx,
)

router = APIRouter(prefix="/export", tags=["export"])


# ── Request Schemas ──
class EscritoExportRequest(BaseModel):
    tribunal: str = Field(min_length=3)
    causa: str = Field(min_length=3)
    caratula: str = Field(min_length=3)
    objeto: str = Field(min_length=10)
    hechos: str = Field(min_length=10)
    derecho: str = Field(min_length=10)
    petitorio: str = Field(min_length=10)


class CartaDocumentoExportRequest(BaseModel):
    destinatario: str = Field(min_length=3)
    domicilio_destinatario: str = Field(min_length=5)
    asunto: str = Field(min_length=5)
    cuerpo: str = Field(min_length=20)


# ── Escrito Judicial → DOCX ──
@router.post("/escrito")
async def export_escrito(
    body: EscritoExportRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.AI_DRAFT)),
):
    """Generate a judicial writing as downloadable DOCX."""
    docx_bytes = generate_escrito_docx(
        tribunal=body.tribunal,
        causa=body.causa,
        caratula=body.caratula,
        objeto=body.objeto,
        hechos=body.hechos,
        derecho=body.derecho,
        petitorio=body.petitorio,
    )

    filename = f"escrito_{body.causa.replace('/', '-')}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.docx"

    await create_audit_entry(
        db, action="export.escrito", user_id=user.id,
        details={"causa": body.causa, "filename": filename},
        ip_address=request.client.host if request.client else None,
    )

    return StreamingResponse(
        io.BytesIO(docx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Carta Documento → DOCX ──
@router.post("/carta-documento")
async def export_carta_documento(
    body: CartaDocumentoExportRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.DOCS_WRITE)),
):
    """Generate a carta documento as downloadable DOCX."""
    docx_bytes = generate_carta_documento_docx(
        destinatario=body.destinatario,
        domicilio_destinatario=body.domicilio_destinatario,
        asunto=body.asunto,
        cuerpo=body.cuerpo,
    )

    filename = f"carta_documento_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.docx"

    await create_audit_entry(
        db, action="export.carta_documento", user_id=user.id,
        details={"destinatario": body.destinatario, "asunto": body.asunto},
        ip_address=request.client.host if request.client else None,
    )

    return StreamingResponse(
        io.BytesIO(docx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Due Diligence Report → DOCX ──
@router.get("/due-diligence/{property_id}")
async def export_due_diligence_report(
    property_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.REALESTATE_READ)),
):
    """Generate a due diligence report for a property as DOCX."""
    prop = await db.get(Property, property_id)
    if not prop or prop.is_deleted:
        raise HTTPException(status_code=404, detail="Propiedad no encontrada")

    property_data = {
        "title": prop.title,
        "address": prop.address,
        "city": prop.city,
        "province": prop.province,
        "country": prop.country,
        "property_type": prop.property_type,
        "folio_real": prop.folio_real or "N/D",
        "owner_name": prop.owner_name or "N/D",
    }

    docx_bytes = generate_due_diligence_report_docx(
        property_data=property_data,
        checklist=prop.dd_checklist or {},
        risk_level=prop.dd_risk_level or "rojo",
    )

    safe_title = prop.title.replace(" ", "_")[:30]
    filename = f"DD_{safe_title}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.docx"

    await create_audit_entry(
        db, action="export.due_diligence", user_id=user.id,
        resource_type="property", resource_id=str(prop.id),
        ip_address=request.client.host if request.client else None,
    )

    return StreamingResponse(
        io.BytesIO(docx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Bulk CSV Export ──
@router.get("/cases/csv")
async def export_cases_csv(
    branch: str | None = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.CASES_READ)),
):
    """Export all cases as CSV for spreadsheet analysis."""
    stmt = select(Case).where(Case.is_deleted == False)
    if branch:
        stmt = stmt.where(Case.branch == branch)
    stmt = stmt.order_by(Case.created_at.desc())

    result = await db.execute(stmt)
    cases = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "ID Interno", "Nro. Causa", "Carátula", "Rama", "Estado",
        "Jurisdicción", "Tribunal", "Cliente", "Rol Cliente",
        "Score Riesgo", "Próximo Vencimiento", "Creada", "Actualizada",
    ])

    for c in cases:
        writer.writerow([
            c.internal_id, c.case_number or "", c.caption, c.branch, c.status,
            c.jurisdiction or "", c.court or "", c.client_name, c.client_role or "",
            c.risk_score if c.risk_score is not None else "",
            c.next_deadline.isoformat() if c.next_deadline else "",
            c.created_at.isoformat(), c.updated_at.isoformat(),
        ])

    if request:
        await create_audit_entry(
            db, action="export.cases_csv", user_id=user.id,
            details={"count": len(cases), "branch_filter": branch},
            ip_address=request.client.host if request.client else None,
        )

    output.seek(0)
    filename = f"causas_estudio_oro_{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),  # BOM for Excel compatibility
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/properties/csv")
async def export_properties_csv(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.REALESTATE_READ)),
):
    """Export all properties as CSV."""
    result = await db.execute(
        select(Property).where(Property.is_deleted == False).order_by(Property.created_at.desc())
    )
    props = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Título", "Dirección", "Ciudad", "Provincia", "País", "Tipo",
        "Estado", "Precio USD", "Precio ARS", "Folio Real",
        "Riesgo DD", "DD Completado", "Propietario", "Creado",
    ])

    for p in props:
        writer.writerow([
            p.title, p.address, p.city, p.province, p.country, p.property_type,
            p.status, p.asking_price_usd or "", p.asking_price_ars or "",
            p.folio_real or "", p.dd_risk_level or "",
            p.dd_completed_at.isoformat() if p.dd_completed_at else "",
            p.owner_name or "", p.created_at.isoformat(),
        ])

    await create_audit_entry(
        db, action="export.properties_csv", user_id=user.id,
        details={"count": len(props)},
        ip_address=request.client.host if request.client else None,
    )

    output.seek(0)
    filename = f"propiedades_estudio_oro_{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
