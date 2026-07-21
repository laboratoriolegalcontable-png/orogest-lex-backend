"""
OroGest Lex — Database Models
Estudio Oro S.A.S. | Fase 3: Base de datos

Models:
  - User: usuarios del estudio con RBAC
  - Case: causas judiciales (penal, civil, etc.)
  - Document: escritos y documentos asociados a causas
  - Property: inmuebles bajo gestión
  - AIConversation: historial de interacciones con Claude
  - AuditLog: registro de auditoría con hash chain SHA-256
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.security import Role
from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


# ═══════════════════════════════════════════
# USER
# ═══════════════════════════════════════════
class User(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        SAEnum(
            Role,
            name="user_role",
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=Role.PASANTE,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    cases: Mapped[list["Case"]] = relationship(back_populates="assigned_to_user", lazy="selectin")
    documents: Mapped[list["Document"]] = relationship(
        back_populates="created_by_user", lazy="selectin"
    )
    ai_conversations: Mapped[list["AIConversation"]] = relationship(
        back_populates="user", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<User {self.email} role={self.role}>"


# ═══════════════════════════════════════════
# CASE (Causa judicial)
# ═══════════════════════════════════════════
class CaseBranch(str, SAEnum):
    """Ramas del derecho que maneja Estudio Oro."""

    pass


CASE_BRANCHES = [
    "penal",
    "civil",
    "laboral",
    "familia",
    "comercial",
    "contencioso_administrativo",
    "inmobiliario",
    "societario",
    "ejecucion_penal",
    "penal_economico",
    "constitucional",
]

CASE_STATUSES = [
    "activa",
    "en_tramite",
    "con_sentencia",
    "en_recurso",
    "archivada",
    "prescripta",
    "finalizada",
]


class Case(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "cases"

    # Identification
    case_number: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    internal_id: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        default=lambda: f"EO-{datetime.now(timezone.utc).year}-{uuid.uuid4().hex[:6].upper()}",
    )
    caption: Mapped[str] = mapped_column(String(500), nullable=False)  # Carátula

    # Classification
    branch: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # from CASE_BRANCHES
    status: Mapped[str] = mapped_column(String(50), default="activa", index=True)

    # Jurisdiction
    jurisdiction: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # CABA / PBA / Federal
    court: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Tribunal
    judge: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prosecutor: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Fiscal

    # Client
    client_name: Mapped[str] = mapped_column(String(255), nullable=False)
    client_role: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # imputado / querellante / actor / demandado

    # Risk scoring (Workflow 3 del Oráculo)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-100
    risk_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Dates
    filing_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Assignments
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    assigned_to_user: Mapped["User | None"] = relationship(back_populates="cases")

    # Notes (encrypted at app layer for sensitive data)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    documents: Mapped[list["Document"]] = relationship(back_populates="case", lazy="selectin")

    __table_args__ = (
        Index("ix_cases_branch_status", "branch", "status"),
        Index("ix_cases_next_deadline", "next_deadline"),
    )

    def __repr__(self) -> str:
        return f"<Case {self.internal_id} [{self.branch}] {self.caption[:40]}>"


# ═══════════════════════════════════════════
# DOCUMENT (Escritos judiciales, contratos, informes)
# ═══════════════════════════════════════════
DOCUMENT_TYPES = [
    "escrito_judicial",
    "nulidad",
    "recurso_casacion",
    "recurso_apelacion",
    "habeas_corpus",
    "contestacion",
    "alegato",
    "contrato",
    "boleto_compraventa",
    "due_diligence",
    "informe",
    "carta_documento",
    "otro",
]


class Document(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "documents"

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)  # Markdown/plaintext
    file_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)  # S3 path
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)  # SHA-256

    # Anti-hallucination flags from Oráculo
    verification_flags: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # e.g. {"verificar": ["art. 168 CPPN"], "inferido": ["fecha arresto"]}

    # Relations
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id"), nullable=True
    )
    case: Mapped["Case | None"] = relationship(back_populates="documents")

    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_by_user: Mapped["User"] = relationship(back_populates="documents")

    version: Mapped[int] = mapped_column(Integer, default=1)
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<Document {self.title[:40]} v{self.version}>"


# ═══════════════════════════════════════════
# PROPERTY (Inmuebles — Workflow 2 Due Diligence)
# ═══════════════════════════════════════════
PROPERTY_STATUSES = [
    "captado",
    "en_due_diligence",
    "publicado",
    "reservado",
    "vendido",
    "archivado",
]


class Property(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "properties"

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    province: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(10), default="ARG")  # ARG / ESP / URY

    property_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # departamento / casa / terreno / local / oficina
    status: Mapped[str] = mapped_column(String(50), default="captado", index=True)

    # Valuation
    asking_price_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    asking_price_ars: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Registry
    folio_real: Mapped[str | None] = mapped_column(String(100), nullable=True)
    matricula: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Due diligence (Workflow 2 checklist result)
    dd_checklist: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    dd_risk_level: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )  # verde / amarillo / rojo
    dd_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owner_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:
        return f"<Property {self.title[:40]} [{self.status}]>"


# ═══════════════════════════════════════════
# AI CONVERSATION (Claude proxy history)
# ═══════════════════════════════════════════
class AIConversation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ai_conversations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    user: Mapped["User"] = relationship(back_populates="ai_conversations")

    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id"), nullable=True
    )

    workflow: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # escrito_blindado / due_diligence / estrategia_procesal / escudo_patrimonial

    messages: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    # [{role: "user"|"assistant", content: "...", timestamp: "..."}]

    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    model_used: Mapped[str] = mapped_column(String(100), default="claude-sonnet-4-20250514")

    # Anti-hallucination tracking
    verification_flags_count: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (Index("ix_ai_conv_user_created", "user_id", "created_at"),)


# ═══════════════════════════════════════════
# AUDIT LOG (SHA-256 chained)
# ═══════════════════════════════════════════
class AuditLog(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "audit_logs"

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # e.g. "case.create", "document.update", "ai.query", "user.login"

    resource_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    # Hash chain
    previous_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="GENESIS")
    current_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    __table_args__ = (Index("ix_audit_resource", "resource_type", "resource_id"),)


# ═══════════════════════════════════════════
# CLIENT (Gestión de clientes del estudio)
# ═══════════════════════════════════════════
class Client(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "clients"

    # Identity
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    document_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # DNI / CUIT / CUIL / Pasaporte / NIE
    document_number: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    nationality: Mapped[str] = mapped_column(String(50), default="argentina")

    # Contact
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    province: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str] = mapped_column(String(10), default="ARG")

    # Classification
    client_type: Mapped[str] = mapped_column(String(30), default="persona_fisica")
    # persona_fisica / persona_juridica / consorcio
    client_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # imputado / querellante / comprador / vendedor / inversor / inquilino

    # UIF/Compliance (Res. UIF 21/2023)
    is_pep: Mapped[bool] = mapped_column(Boolean, default=False)
    pep_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    kyc_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    kyc_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Notes (encrypted at app layer)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relations
    cases: Mapped[list["CaseClient"]] = relationship(back_populates="client", lazy="selectin")

    __table_args__ = (Index("ix_clients_name_doc", "full_name", "document_number"),)

    def __repr__(self) -> str:
        return f"<Client {self.full_name} [{self.document_number}]>"


# ═══════════════════════════════════════════
# CASE ↔ CLIENT (Many-to-Many with role)
# ═══════════════════════════════════════════
class CaseClient(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "case_clients"

    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    # imputado / querellante / actor / demandado / comprador / vendedor / testigo
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relations
    case: Mapped["Case"] = relationship(lazy="selectin")
    client: Mapped["Client"] = relationship(back_populates="cases", lazy="selectin")

    __table_args__ = (Index("ix_case_clients_unique", "case_id", "client_id", "role", unique=True),)


# ═══════════════════════════════════════════
# WRITING TEMPLATE (Plantillas de escritos reutilizables)
# ═══════════════════════════════════════════
class WritingTemplate(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "writing_templates"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    branch: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # penal / inmobiliario / laboral / societario / etc.
    doc_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # nulidad / recurso_casacion / contestacion / carta_documento / etc.

    # Template content with placeholders: {{tribunal}}, {{causa}}, {{caratula}}, etc.
    template_content: Mapped[str] = mapped_column(Text, nullable=False)
    # JSON schema of required variables
    variables_schema: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # e.g. {"tribunal": {"type": "string", "required": true}, "causa": {...}}

    # Metadata
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    # System templates can't be deleted by non-directors

    def __repr__(self) -> str:
        return f"<WritingTemplate {self.name} [{self.branch}/{self.doc_type}]>"
