"""
OroGest Lex — Document Export Service
Generate professional DOCX files from case data and AI-generated content.

Templates:
1. Escrito judicial (nulidad, recurso, contestación, etc.)
2. Carta documento
3. Informe de due diligence
4. Propuesta Escudo Patrimonial

All docs carry: Estudio Oro S.A.S. header, firma, fecha, anti-hallucination warnings.
"""

import io
from datetime import datetime, timezone

# We use python-docx for DOCX generation
# If not available, fall back to Markdown export
try:
    from docx import Document as DocxDocument
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False


# ── Constants ──
ESTUDIO_HEADER = "Estudio Oro S.A.S."
FIRMA_LINES = [
    "Dr. Diego Orosa",
    "Abogado — CPACF T° 145 F° 433",
    "Corredor Inmobiliario — CASI T° LV F° 206",
    "Estudio Oro S.A.S. — CUIT 30-71933033-5",
    "Tel: +54 11 6877-7777",
    "diego@estudiooro.com",
]
ANTI_HALLUCINATION_WARNING = (
    "⚠ AVISO: Este documento fue generado con asistencia de IA. "
    "Todos los elementos marcados con [VERIFICAR], [INFERIDO] o "
    "[FUENTE REQUERIDA] deben ser confirmados antes de su presentación judicial."
)


def _add_header(doc: "DocxDocument", title: str):
    """Add Estudio Oro header to document."""
    header_para = doc.add_paragraph()
    header_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = header_para.add_run(ESTUDIO_HEADER)
    run.bold = True
    run.font.size = Pt(14)
    run.font.color.rgb = RGBColor(0xC8, 0x96, 0x00)  # Gold

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run2 = sub.add_run("Abogados · Corredores Inmobiliarios")
    run2.font.size = Pt(9)
    run2.font.color.rgb = RGBColor(0x80, 0x80, 0x80)

    doc.add_paragraph()  # spacer


def _add_firma(doc: "DocxDocument"):
    """Add firm signature block."""
    doc.add_paragraph()  # spacer
    doc.add_paragraph("─" * 40)
    for line in FIRMA_LINES:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        run = p.add_run(line)
        run.font.size = Pt(10)


def _add_ai_warning(doc: "DocxDocument"):
    """Add anti-hallucination warning footer."""
    doc.add_paragraph()
    p = doc.add_paragraph()
    run = p.add_run(ANTI_HALLUCINATION_WARNING)
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor(0xFF, 0x00, 0x00)
    run.italic = True


def generate_escrito_docx(
    tribunal: str,
    causa: str,
    caratula: str,
    objeto: str,
    hechos: str,
    derecho: str,
    petitorio: str,
    fecha: str | None = None,
) -> bytes:
    """
    Generate a judicial writing (escrito) as DOCX.
    Returns: bytes of the .docx file.
    """
    if not HAS_DOCX:
        return _fallback_markdown(
            "ESCRITO JUDICIAL",
            tribunal=tribunal,
            causa=causa,
            caratula=caratula,
            objeto=objeto,
            hechos=hechos,
            derecho=derecho,
            petitorio=petitorio,
        )

    doc = DocxDocument()
    _add_header(doc, "ESCRITO JUDICIAL")

    # Date
    if not fecha:
        fecha = datetime.now(timezone.utc).strftime("%d de %B de %Y")
    p_date = doc.add_paragraph()
    p_date.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_date.add_run(f"Buenos Aires, {fecha}").font.size = Pt(11)

    # Tribunal/Causa/Carátula
    doc.add_paragraph()
    info_lines = [
        f"Tribunal: {tribunal}",
        f"Causa N°: {causa}",
        f"Carátula: {caratula}",
    ]
    for line in info_lines:
        p = doc.add_paragraph()
        run = p.add_run(line)
        run.bold = True
        run.font.size = Pt(11)

    doc.add_paragraph()

    # Sections
    sections = [
        ("I. OBJETO", objeto),
        ("II. HECHOS", hechos),
        ("III. DERECHO", derecho),
        ("IV. PETITORIO", petitorio),
    ]

    for title, content in sections:
        heading = doc.add_paragraph()
        run = heading.add_run(title)
        run.bold = True
        run.font.size = Pt(12)
        run.font.color.rgb = RGBColor(0x1A, 0x1A, 0x2E)

        # Split content by paragraphs
        for para_text in content.split("\n"):
            if para_text.strip():
                p = doc.add_paragraph(para_text.strip())
                p.paragraph_format.space_after = Pt(6)
                for run in p.runs:
                    run.font.size = Pt(11)

    # Proveer / Firma
    doc.add_paragraph()
    proveer = doc.add_paragraph()
    run = proveer.add_run("PROVEER DE CONFORMIDAD, SERÁ JUSTICIA.")
    run.bold = True
    run.font.size = Pt(11)

    _add_firma(doc)
    _add_ai_warning(doc)

    # Return bytes
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def generate_carta_documento_docx(
    destinatario: str,
    domicilio_destinatario: str,
    asunto: str,
    cuerpo: str,
    remitente: str = "Dr. Diego Orosa — Estudio Oro S.A.S.",
    fecha: str | None = None,
) -> bytes:
    """
    Generate a carta documento as DOCX.
    """
    if not HAS_DOCX:
        return _fallback_markdown(
            "CARTA DOCUMENTO",
            destinatario=destinatario,
            asunto=asunto,
            cuerpo=cuerpo,
        )

    doc = DocxDocument()
    _add_header(doc, "CARTA DOCUMENTO")

    if not fecha:
        fecha = datetime.now(timezone.utc).strftime("%d de %B de %Y")

    doc.add_paragraph(f"Buenos Aires, {fecha}")
    doc.add_paragraph()

    # Destinatario
    doc.add_paragraph(f"Señor/a: {destinatario}")
    doc.add_paragraph(f"Domicilio: {domicilio_destinatario}")
    doc.add_paragraph()

    # Ref
    p_ref = doc.add_paragraph()
    run = p_ref.add_run(f"REF: {asunto}")
    run.bold = True
    run.font.size = Pt(11)
    doc.add_paragraph()

    # Cuerpo
    doc.add_paragraph("De mi mayor consideración:")
    doc.add_paragraph()

    for para_text in cuerpo.split("\n"):
        if para_text.strip():
            p = doc.add_paragraph(para_text.strip())
            for run in p.runs:
                run.font.size = Pt(11)

    doc.add_paragraph()
    doc.add_paragraph(
        "Queda Ud. debidamente notificado/a, haciendo esta carta documento "
        "las veces de fehaciente intimación."
    )

    _add_firma(doc)
    _add_ai_warning(doc)

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def generate_due_diligence_report_docx(
    property_data: dict,
    checklist: dict,
    risk_level: str,
) -> bytes:
    """Generate a due diligence report as DOCX."""
    if not HAS_DOCX:
        return _fallback_markdown("INFORME DUE DILIGENCE", **property_data)

    doc = DocxDocument()
    _add_header(doc, "INFORME DE DUE DILIGENCE INMOBILIARIO")

    fecha = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    doc.add_paragraph(f"Fecha: {fecha}")
    doc.add_paragraph()

    # Property info
    heading = doc.add_paragraph()
    run = heading.add_run("DATOS DEL INMUEBLE")
    run.bold = True
    run.font.size = Pt(12)

    fields = [
        ("Dirección", property_data.get("address", "N/D")),
        ("Ciudad", property_data.get("city", "N/D")),
        ("Provincia", property_data.get("province", "N/D")),
        ("País", property_data.get("country", "N/D")),
        ("Tipo", property_data.get("property_type", "N/D")),
        ("Folio Real", property_data.get("folio_real", "N/D")),
        ("Propietario", property_data.get("owner_name", "N/D")),
    ]
    for label, value in fields:
        doc.add_paragraph(f"{label}: {value}")

    doc.add_paragraph()

    # Risk level
    risk_emoji = {"verde": "🟢", "amarillo": "🟡", "rojo": "🔴"}.get(risk_level, "⚪")
    risk_p = doc.add_paragraph()
    run = risk_p.add_run(f"NIVEL DE RIESGO: {risk_emoji} {risk_level.upper()}")
    run.bold = True
    run.font.size = Pt(13)
    if risk_level == "rojo":
        run.font.color.rgb = RGBColor(0xFF, 0x00, 0x00)
    elif risk_level == "amarillo":
        run.font.color.rgb = RGBColor(0xFF, 0xA5, 0x00)
    else:
        run.font.color.rgb = RGBColor(0x00, 0x80, 0x00)

    doc.add_paragraph()

    # Checklist
    heading2 = doc.add_paragraph()
    run2 = heading2.add_run("CHECKLIST DE VERIFICACIÓN")
    run2.bold = True
    run2.font.size = Pt(12)

    status_icons = {"ok": "✅", "problema": "❌", "pendiente": "⏳", "no_aplica": "➖"}

    for key, item in checklist.items():
        status = item.get("status", "pendiente")
        icon = status_icons.get(status, "?")
        label = item.get("label", key)
        notes = item.get("notes", "")
        line = f"{icon} {label}"
        if notes:
            line += f" — {notes}"
        doc.add_paragraph(line)

    doc.add_paragraph()

    # Recommendation
    heading3 = doc.add_paragraph()
    run3 = heading3.add_run("RECOMENDACIÓN")
    run3.bold = True
    run3.font.size = Pt(12)

    if risk_level == "verde":
        doc.add_paragraph("La operación puede proceder. Todos los ítems verificados.")
    elif risk_level == "amarillo":
        doc.add_paragraph(
            "La operación requiere completar los ítems pendientes antes de proceder. "
            "Se recomienda no avanzar hasta tener todas las verificaciones completas."
        )
    else:
        doc.add_paragraph(
            "⚠️ NO SE RECOMIENDA PROCEDER. Existen ítems con problemas o "
            "insuficiente verificación. Consultar con el director del estudio."
        )

    _add_firma(doc)
    _add_ai_warning(doc)

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def _fallback_markdown(title: str, **kwargs) -> bytes:
    """Fallback when python-docx is not available: generate Markdown."""
    lines = [
        f"# {title}",
        f"## {ESTUDIO_HEADER}",
        f"Fecha: {datetime.now(timezone.utc).strftime('%d/%m/%Y')}",
        "",
    ]
    for key, value in kwargs.items():
        lines.append(f"**{key.replace('_', ' ').title()}:** {value}")
        lines.append("")

    lines.append("---")
    for line in FIRMA_LINES:
        lines.append(line)
    lines.append("")
    lines.append(f"*{ANTI_HALLUCINATION_WARNING}*")

    return "\n".join(lines).encode("utf-8")
