"""
OroGest Lex — Orchestrator Endpoint
Classifies, routes, and executes tasks through the appropriate workflow.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import OrchestratorTask
from app.api.deps import RequirePermission, get_current_user
from app.core.security import Permission
from app.db.session import get_db
from app.models.models import User
from app.services.ai_service import create_or_continue_conversation
from app.services.audit_service import create_audit_entry

router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])


class OrchestratorRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)
    case_id: str | None = None
    auto_execute: bool = True  # If True, classify AND execute. If False, classify only.


class ClassificationResponse(BaseModel):
    task_id: str
    domain: str
    urgency: str
    workflow: str
    confidence: float
    matched_keywords: list[str]


class OrchestratorResponse(BaseModel):
    task_id: str
    domain: str
    urgency: str
    workflow: str
    confidence: float
    response: str | None = None
    tokens_used: int | None = None
    verification_flags: dict | None = None


@router.post("/classify", response_model=ClassificationResponse)
async def classify_only(
    body: OrchestratorRequest,
    user: User = Depends(get_current_user),
):
    """Classify a request without executing it. Useful for previewing routing."""
    task = OrchestratorTask(input_text=body.message)
    task.classify()

    return ClassificationResponse(
        task_id=task.id,
        domain=task.classification.domain.value,
        urgency=task.classification.urgency.value,
        workflow=task.classification.workflow.value,
        confidence=task.classification.confidence,
        matched_keywords=task.classification.matched_keywords,
    )


@router.post("/execute", response_model=OrchestratorResponse)
async def classify_and_execute(
    body: OrchestratorRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.AI_CHAT)),
):
    """
    Full pipeline: classify → route → execute via Claude → return result.
    This is the primary entry point for the OroGest Lex copilot.
    """
    # Step 1: Classify
    task = OrchestratorTask(input_text=body.message)
    task.classify()
    task.start()

    # Step 2: Execute via Claude with the appropriate workflow
    import uuid as uuid_mod

    case_uuid = uuid_mod.UUID(body.case_id) if body.case_id else None

    try:
        result, _conversation = await create_or_continue_conversation(
            db=db,
            user_id=user.id,
            message=body.message,
            case_id=case_uuid,
            workflow=task.classification.workflow.value,
        )
        task.complete(result["response"])
    except Exception as e:  # noqa: BLE001 — API error boundary: mark task failed, respond 502
        task.fail(str(e))
        raise HTTPException(status_code=502, detail="Error en la ejecución del orquestador.")

    # Step 3: Audit
    await create_audit_entry(
        db,
        action="orchestrator.execute",
        user_id=user.id,
        details={
            "task_id": task.id,
            "domain": task.classification.domain.value,
            "urgency": task.classification.urgency.value,
            "workflow": task.classification.workflow.value,
            "confidence": task.classification.confidence,
            "tokens": result["tokens_used"],
        },
        ip_address=request.client.host if request.client else None,
    )

    return OrchestratorResponse(
        task_id=task.id,
        domain=task.classification.domain.value,
        urgency=task.classification.urgency.value,
        workflow=task.classification.workflow.value,
        confidence=task.classification.confidence,
        response=result["response"],
        tokens_used=result["tokens_used"],
        verification_flags=result["verification_flags"],
    )
