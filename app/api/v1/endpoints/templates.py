"""
OroGest Lex — Writing Templates Endpoints
Create, manage, and use reusable legal document templates.

Templates use {{variable}} placeholders that get replaced with actual values.
"""

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RequirePermission, RequireRole
from app.core.security import Permission, Role
from app.db.session import get_db
from app.models.models import WritingTemplate, User
from app.services.audit_service import create_audit_entry

router = APIRouter(prefix="/templates", tags=["templates"])

# ── System templates (pre-loaded) ──
SYSTEM_TEMPLATES = [
    {
        "name": "Nulidad por prueba digital ilegal",
        "description": "Planteo de nulidad por extracción de datos sin protocolo forense (Cellebrite/WhatsApp). Casación-ready.",
        "branch": "penal",
        "doc_type": "nulidad",
        "template_content": """{{ciudad}}, {{fecha}}

Señor Juez del {{tribunal}}:

{{abogado}}, Abogado (CPACF T° 145 F° 433), en representación de {{cliente}}, en la causa N° {{numero_causa}}, caratulada "{{caratula}}", a V.S. respetuosamente digo:

I. OBJETO

Vengo por la presente a plantear la NULIDAD ABSOLUTA de la extracción y/o volcado de datos del dispositivo móvil obrante a fs. {{fojas}}, por haberse obtenido en violación a las garantías constitucionales (art. 18 CN) y procesales (arts. 166, 167 inc. 2° y 3°, y 168 CPPN [VERIFICAR]).

II. HECHOS

{{hechos}}

III. DERECHO

{{derecho}}

La cadena de custodia digital exige: a) uso de herramientas forenses certificadas; b) generación de hash verificable; c) intervención de perito informático oficial; d) documentación del procedimiento completo.

En el caso, ninguno de estos requisitos fue cumplido [VERIFICAR CON CONSTANCIAS].

IV. PETITORIO

1) Se declare la nulidad absoluta de la extracción de datos del dispositivo.
2) Se excluya toda evidencia derivada (doctrina del fruto del árbol venenoso).
3) Se ordene la destrucción de las copias no autorizadas.

PROVEER DE CONFORMIDAD, SERÁ JUSTICIA.

{{firma}}""",
        "variables_schema": {
            "ciudad": {"type": "string", "default": "Buenos Aires"},
            "fecha": {"type": "date"},
            "tribunal": {"type": "string", "required": True},
            "abogado": {"type": "string", "default": "Dr. Diego Orosa"},
            "cliente": {"type": "string", "required": True},
            "numero_causa": {"type": "string", "required": True},
            "caratula": {"type": "string", "required": True},
            "fojas": {"type": "string"},
            "hechos": {"type": "text", "required": True},
            "derecho": {"type": "text", "required": True},
            "firma": {
                "type": "string",
                "default": "Dr. Diego Orosa\nAbogado — CPACF T° 145 F° 433\nEstudio Oro S.A.S.",
            },
        },
    },
    {
        "name": "Carta documento — Intimación por incumplimiento",
        "description": "Intimación fehaciente por incumplimiento contractual. Plazo 48hs.",
        "branch": "civil",
        "doc_type": "carta_documento",
        "template_content": """Buenos Aires, {{fecha}}

Señor/a: {{destinatario}}
Domicilio: {{domicilio}}

REF: {{asunto}}

De mi mayor consideración:

Por medio de la presente, en mi carácter de apoderado/a de {{mandante}}, lo/la intimo fehacientemente a que en el plazo perentorio e improrrogable de CUARENTA Y OCHO (48) HORAS de recibida la presente, proceda a {{obligacion}}.

{{cuerpo_adicional}}

Caso contrario, me veré en la obligación de iniciar las acciones legales que correspondan, con más los daños y perjuicios que su incumplimiento irrogue, todo ello con costas a su exclusivo cargo.

Queda Ud. debidamente notificado/a.

{{firma}}""",
        "variables_schema": {
            "fecha": {"type": "date"},
            "destinatario": {"type": "string", "required": True},
            "domicilio": {"type": "string", "required": True},
            "asunto": {"type": "string", "required": True},
            "mandante": {"type": "string", "required": True},
            "obligacion": {"type": "text", "required": True},
            "cuerpo_adicional": {"type": "text", "default": ""},
            "firma": {
                "type": "string",
                "default": "Dr. Diego Orosa\nAbogado — CPACF T° 145 F° 433\nEstudio Oro S.A.S.",
            },
        },
    },
    {
        "name": "Morigeración de prisión preventiva",
        "description": "Solicitud de morigeración o domiciliaria. Arts. 210/283 CPPN y Ley 24.660.",
        "branch": "penal",
        "doc_type": "escrito_judicial",
        "template_content": """{{ciudad}}, {{fecha}}

Señor Juez del {{tribunal}}:

{{abogado}}, Abogado, en la causa N° {{numero_causa}}, caratulada "{{caratula}}", me presento y digo:

I. OBJETO

Solicito la MORIGERACIÓN de la medida cautelar que pesa sobre mi asistido/a {{cliente}}, disponiendo su ARRESTO DOMICILIARIO, conforme los arts. 210 y 283 CPPN [VERIFICAR] y art. 10 del Código Penal, y concordantes de la Ley 24.660 [VERIFICAR].

II. FUNDAMENTOS

{{fundamentos}}

III. ARRAIGO Y CONDICIONES

Mi asistido/a ofrece:
- Domicilio fijo: {{domicilio_cliente}}
- {{condiciones_adicionales}}

IV. PETITORIO

Solicito se haga lugar a la morigeración peticionada, disponiendo arresto domiciliario con las condiciones que V.S. estime corresponder.

PROVEER DE CONFORMIDAD, SERÁ JUSTICIA.

{{firma}}""",
        "variables_schema": {
            "ciudad": {"type": "string", "default": "Buenos Aires"},
            "fecha": {"type": "date"},
            "tribunal": {"type": "string", "required": True},
            "abogado": {"type": "string", "default": "Dr. Diego Orosa"},
            "numero_causa": {"type": "string", "required": True},
            "caratula": {"type": "string", "required": True},
            "cliente": {"type": "string", "required": True},
            "fundamentos": {"type": "text", "required": True},
            "domicilio_cliente": {"type": "string", "required": True},
            "condiciones_adicionales": {
                "type": "text",
                "default": "Dispositivo de geolocalización electrónica",
            },
            "firma": {
                "type": "string",
                "default": "Dr. Diego Orosa\nAbogado — CPACF T° 145 F° 433\nEstudio Oro S.A.S.",
            },
        },
    },
]


# ── Schemas ──
class TemplateCreate(BaseModel):
    name: str = Field(min_length=3, max_length=255)
    description: str | None = None
    branch: str
    doc_type: str
    template_content: str = Field(min_length=50)
    variables_schema: dict | None = None


class TemplateResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    branch: str
    doc_type: str
    template_content: str
    variables_schema: dict | None
    usage_count: int
    is_system: bool
    created_at: str

    model_config = {"from_attributes": True}


class RenderTemplateRequest(BaseModel):
    variables: dict[str, str]


# ── Endpoints ──
@router.get("/")
async def list_templates(
    branch: str | None = None,
    doc_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.DOCS_READ)),
):
    stmt = select(WritingTemplate).where(WritingTemplate.is_deleted == False)
    if branch:
        stmt = stmt.where(WritingTemplate.branch == branch)
    if doc_type:
        stmt = stmt.where(WritingTemplate.doc_type == doc_type)
    stmt = stmt.order_by(WritingTemplate.usage_count.desc())

    result = await db.execute(stmt)
    templates = result.scalars().all()

    return [
        {
            "id": str(t.id),
            "name": t.name,
            "description": t.description,
            "branch": t.branch,
            "doc_type": t.doc_type,
            "usage_count": t.usage_count,
            "is_system": t.is_system,
            "variable_count": len(t.variables_schema) if t.variables_schema else 0,
        }
        for t in templates
    ]


@router.get("/{template_id}")
async def get_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.DOCS_READ)),
):
    template = await db.get(WritingTemplate, template_id)
    if not template or template.is_deleted:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    return template


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_template(
    body: TemplateCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.DOCS_WRITE)),
):
    template = WritingTemplate(
        name=body.name,
        description=body.description,
        branch=body.branch,
        doc_type=body.doc_type,
        template_content=body.template_content,
        variables_schema=body.variables_schema,
        created_by=user.id,
    )
    db.add(template)
    await db.flush()

    await create_audit_entry(
        db,
        action="template.create",
        user_id=user.id,
        resource_type="template",
        resource_id=str(template.id),
        details={"name": template.name, "branch": template.branch},
        ip_address=request.client.host if request.client else None,
    )

    return template


@router.post("/{template_id}/render")
async def render_template(
    template_id: uuid.UUID,
    body: RenderTemplateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.DOCS_WRITE)),
):
    """Render a template with the given variables. Returns the filled text."""
    template = await db.get(WritingTemplate, template_id)
    if not template or template.is_deleted:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")

    # Replace {{variable}} placeholders
    rendered = template.template_content
    for key, value in body.variables.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)

    # Check for unfilled required variables
    unfilled = re.findall(r"\{\{(\w+)\}\}", rendered)

    # Increment usage counter
    template.usage_count += 1

    return {
        "rendered_content": rendered,
        "template_name": template.name,
        "variables_used": list(body.variables.keys()),
        "unfilled_variables": unfilled,
    }


@router.post("/seed-system")
async def seed_system_templates(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireRole(Role.DIRECTOR)),
):
    """Load built-in system templates. DIRECTOR only."""
    created = []
    for tpl_data in SYSTEM_TEMPLATES:
        # Check if already exists
        existing = await db.execute(
            select(WritingTemplate).where(
                WritingTemplate.name == tpl_data["name"],
                WritingTemplate.is_system == True,
            )
        )
        if existing.scalar_one_or_none():
            continue

        template = WritingTemplate(
            name=tpl_data["name"],
            description=tpl_data["description"],
            branch=tpl_data["branch"],
            doc_type=tpl_data["doc_type"],
            template_content=tpl_data["template_content"],
            variables_schema=tpl_data["variables_schema"],
            created_by=user.id,
            is_system=True,
        )
        db.add(template)
        created.append(tpl_data["name"])

    await db.flush()

    await create_audit_entry(
        db,
        action="template.seed_system",
        user_id=user.id,
        details={"created": created},
        ip_address=request.client.host if request.client else None,
    )

    return {"status": "ok", "created": len(created), "templates": created}
