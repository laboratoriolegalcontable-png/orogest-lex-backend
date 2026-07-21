"""
OroGest Lex — Núcleo Orquestador (Fase 4)

This is the brain of the system. It:
1. Classifies incoming requests by domain and urgency
2. Routes to the appropriate workflow
3. Coordinates multi-step operations
4. Tracks execution state

This is the REALISTIC version: a deterministic router + state machine,
NOT a fantasy autonomous AI. Claude handles the intelligence;
this module handles the coordination and state.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


# ═══════════════════════════════════════════
# DOMAIN CLASSIFICATION
# ═══════════════════════════════════════════
class Domain(str, Enum):
    PENAL = "penal"
    INMOBILIARIO = "inmobiliario"
    SOCIETARIO = "societario"
    LABORAL = "laboral"
    CIVIL = "civil"
    COMPLIANCE = "compliance"
    TECH = "tech"
    MARKETING = "marketing"
    GENERAL = "general"


class Urgency(str, Enum):
    CRITICAL = "critica"  # 🚨 detenido, vence hoy, habeas corpus
    HIGH = "alta"  # ⚠️ plazo próximo, cautelar
    NORMAL = "normal"


class Workflow(str, Enum):
    ESCRITO_BLINDADO = "escrito_blindado"
    DUE_DILIGENCE = "due_diligence"
    ESTRATEGIA_PROCESAL = "estrategia_procesal"
    ESCUDO_PATRIMONIAL = "escudo_patrimonial"
    GENERAL = "general"


# ═══════════════════════════════════════════
# KEYWORD-BASED CLASSIFIER
# ═══════════════════════════════════════════
URGENCY_KEYWORDS = {
    Urgency.CRITICAL: [
        "detenido",
        "preso",
        "vence hoy",
        "urgente",
        "cautelar",
        "hábeas corpus",
        "habeas corpus",
        "siniestro",
        "despido inmediato",
    ],
    Urgency.HIGH: [
        "plazo",
        "vencimiento",
        "audiencia mañana",
        "notificación",
        "embargo",
        "inhibición",
    ],
}

DOMAIN_KEYWORDS: dict[Domain, list[str]] = {
    Domain.PENAL: [
        "penal",
        "imputado",
        "fiscal",
        "defensa",
        "nulidad",
        "casación",
        "recurso",
        "prisión",
        "libertad",
        "morigeración",
        "excarcelación",
        "probation",
        "art. 76",
        "sobreseimiento",
        "requerimiento",
        "elevación",
        "cppn",
        "cpp",
        "tribunal oral",
        "cámara",
        "alegato",
    ],
    Domain.INMOBILIARIO: [
        "inmueble",
        "propiedad",
        "compraventa",
        "boleto",
        "escritura",
        "titulo",
        "folio real",
        "matrícula",
        "remate",
        "subasta",
        "due diligence",
        "corredor",
        "comisión",
        "expensas",
        "hipoteca",
    ],
    Domain.SOCIETARIO: [
        "sociedad",
        "sas",
        "srl",
        "sa",
        "acta",
        "asamblea",
        "directorio",
        "estatuto",
        "igj",
        "constitución societaria",
        "aporte",
        "socio",
    ],
    Domain.LABORAL: [
        "laboral",
        "despido",
        "indemnización",
        "art 245",
        "lct",
        "ripte",
        "preaviso",
        "sac",
        "vacaciones",
        "carta documento",
    ],
    Domain.COMPLIANCE: [
        "uif",
        "lavado",
        "pld",
        "ros",
        "siplaf",
        "pep",
        "kyc",
        "debida diligencia",
        "compliance",
        "res 21/2023",
    ],
}

WORKFLOW_KEYWORDS: dict[Workflow, list[str]] = {
    Workflow.ESCRITO_BLINDADO: [
        "escrito",
        "nulidad",
        "recurso",
        "planteo",
        "defensa",
        "habeas corpus",
        "excepción",
        "contestación",
        "alegato",
        "casación",
        "redactar",
        "blindar",
    ],
    Workflow.DUE_DILIGENCE: [
        "due diligence",
        "verificar propiedad",
        "checklist",
        "inhibiciones",
        "deudas",
        "folio",
        "título",
    ],
    Workflow.ESTRATEGIA_PROCESAL: [
        "estrategia",
        "riesgo procesal",
        "probabilidad",
        "chances",
        "scoring",
        "análisis de causa",
    ],
    Workflow.ESCUDO_PATRIMONIAL: [
        "inversor",
        "propuesta",
        "servicio",
        "fee",
        "membresía",
        "escudo",
        "presentación",
        "pitch",
        "plan",
    ],
}


@dataclass
class ClassificationResult:
    domain: Domain
    urgency: Urgency
    workflow: Workflow
    confidence: float  # 0.0 to 1.0
    matched_keywords: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def classify_request(text: str) -> ClassificationResult:
    """
    Deterministic keyword-based classification.
    This is NOT AI — it's a fast router that decides which workflow
    and system prompt to use before calling Claude.
    """
    text_lower = text.lower()
    matched = []

    # 1. Urgency
    urgency = Urgency.NORMAL
    for level, keywords in URGENCY_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                urgency = level
                matched.append(f"urgency:{kw}")
                break
        if urgency != Urgency.NORMAL:
            break

    # 2. Domain
    domain_scores: dict[Domain, int] = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            domain_scores[domain] = score
            matched.extend(f"domain:{kw}" for kw in keywords if kw in text_lower)

    domain = max(domain_scores, key=domain_scores.get) if domain_scores else Domain.GENERAL

    # 3. Workflow
    workflow_scores: dict[Workflow, int] = {}
    for wf, keywords in WORKFLOW_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            workflow_scores[wf] = score
            matched.extend(f"workflow:{kw}" for kw in keywords if kw in text_lower)

    workflow = (
        max(workflow_scores, key=workflow_scores.get) if workflow_scores else Workflow.GENERAL
    )

    # 4. Confidence (simple heuristic)
    total_matches = len(matched)
    confidence = min(1.0, total_matches / 5.0)  # 5+ matches = full confidence

    return ClassificationResult(
        domain=domain,
        urgency=urgency,
        workflow=workflow,
        confidence=confidence,
        matched_keywords=matched,
    )


# ═══════════════════════════════════════════
# TASK STATE MACHINE
# ═══════════════════════════════════════════
class TaskState(str, Enum):
    PENDING = "pending"
    CLASSIFIED = "classified"
    IN_PROGRESS = "in_progress"
    AWAITING_REVIEW = "awaiting_review"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class OrchestratorTask:
    """
    Represents a unit of work flowing through the system.
    This is an in-memory state object; for persistence, use the DB task model.
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    input_text: str = ""
    classification: ClassificationResult | None = None
    state: TaskState = TaskState.PENDING
    result: str | None = None
    error: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str | None = None

    def classify(self):
        self.classification = classify_request(self.input_text)
        self.state = TaskState.CLASSIFIED

    def start(self):
        self.state = TaskState.IN_PROGRESS

    def complete(self, result: str):
        self.result = result
        self.state = TaskState.COMPLETED
        self.completed_at = datetime.now(timezone.utc).isoformat()

    def fail(self, error: str):
        self.error = error
        self.state = TaskState.FAILED
        self.completed_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "state": self.state.value,
            "classification": {
                "domain": self.classification.domain.value,
                "urgency": self.classification.urgency.value,
                "workflow": self.classification.workflow.value,
                "confidence": self.classification.confidence,
            }
            if self.classification
            else None,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }
