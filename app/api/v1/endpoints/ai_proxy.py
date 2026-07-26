"""
OroGest Lex — AI Proxy Endpoint (Claude API)
Rate limited, audited, anti-hallucination enforced.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RequirePermission
from app.core.security import Permission
from app.db.session import get_db
from app.models.models import User
from app.schemas.schemas import AIQueryRequest, AIQueryResponse
from app.services.ai_service import create_or_continue_conversation
from app.services.audit_service import create_audit_entry

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/query", response_model=AIQueryResponse)
async def ai_query(
    body: AIQueryRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.AI_CHAT)),
):
    """
    Proxy request to Claude API with:
    - Anti-hallucination system prompt
    - Workflow-specific prompts (escrito_blindado, due_diligence, etc.)
    - Token tracking
    - Audit trail
    """
    try:
        result, conversation = await create_or_continue_conversation(
            db=db,
            user_id=user.id,
            message=body.message,
            case_id=body.case_id,
            workflow=body.workflow,
            system_prompt_override=body.system_prompt_override,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:  # noqa: BLE001 — API error boundary: log to audit, respond 502, never leak internals
        await create_audit_entry(
            db,
            action="ai.query.error",
            user_id=user.id,
            details={"error": str(e)[:500]},
            ip_address=request.client.host if request.client else None,
        )
        raise HTTPException(
            status_code=502,
            detail="Error al comunicarse con el servicio de IA. Intentá de nuevo.",
        )

    # Audit the successful query
    await create_audit_entry(
        db,
        action="ai.query",
        user_id=user.id,
        resource_type="ai_conversation",
        resource_id=str(conversation.id),
        details={
            "workflow": body.workflow,
            "tokens": result["tokens_used"],
            "flags_count": sum(len(v) for v in result["verification_flags"].values()),
        },
        ip_address=request.client.host if request.client else None,
    )

    return AIQueryResponse(
        response=result["response"],
        conversation_id=conversation.id,
        tokens_used=result["tokens_used"],
        verification_flags=result["verification_flags"],
        model=result["model"],
    )


@router.post("/draft", response_model=AIQueryResponse)
async def ai_draft(
    body: AIQueryRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequirePermission(Permission.AI_DRAFT)),
):
    """
    Generate a legal draft (escrito) with the Escrito Blindado workflow.
    Requires AI_DRAFT permission (abogado+).
    """
    # Force escrito_blindado workflow
    body_with_workflow = AIQueryRequest(
        message=body.message,
        case_id=body.case_id,
        workflow="escrito_blindado",
        system_prompt_override=body.system_prompt_override,
    )

    try:
        result, conversation = await create_or_continue_conversation(
            db=db,
            user_id=user.id,
            message=body_with_workflow.message,
            case_id=body_with_workflow.case_id,
            workflow="escrito_blindado",
            system_prompt_override=body_with_workflow.system_prompt_override,
        )
    except Exception as e:  # noqa: BLE001 — API error boundary: log to audit, respond 502, never leak internals
        await create_audit_entry(
            db,
            action="ai.draft.error",
            user_id=user.id,
            details={"error": str(e)[:500]},
            ip_address=request.client.host if request.client else None,
        )
        raise HTTPException(status_code=502, detail="Error generando el escrito.")

    await create_audit_entry(
        db,
        action="ai.draft",
        user_id=user.id,
        resource_type="ai_conversation",
        resource_id=str(conversation.id),
        details={
            "tokens": result["tokens_used"],
            "case_id": str(body.case_id) if body.case_id else None,
        },
        ip_address=request.client.host if request.client else None,
    )

    return AIQueryResponse(
        response=result["response"],
        conversation_id=conversation.id,
        tokens_used=result["tokens_used"],
        verification_flags=result["verification_flags"],
        model=result["model"],
    )
