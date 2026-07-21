"""
OroGest Lex — Webhooks Endpoint
Inbound/outbound webhooks for N8n, WhatsApp, and external integrations.

Inbound: receive events from external systems
Outbound: register webhook URLs to receive OroGest events
"""

import hashlib
import hmac
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

import httpx

from app.api.deps import RequireRole
from app.core.config import get_settings
from app.core.security import Role
from app.db.session import get_db
from app.models.models import User
from app.services.audit_service import create_audit_entry

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
settings = get_settings()

# In-memory webhook registry (production: use DB table)
_webhook_registry: dict[str, dict] = {}


# ── Schemas ──
class WebhookRegister(BaseModel):
    url: str = Field(min_length=10)
    events: list[str] = Field(min_length=1)
    # Events: case.created, case.updated, document.created, ai.completed,
    #         deadline.approaching, property.risk_changed
    secret: str | None = None  # For HMAC signature verification
    name: str = Field(min_length=2, max_length=100)


class WhatsAppInbound(BaseModel):
    """Inbound message from N8n WhatsApp integration."""

    phone: str
    message: str
    name: str | None = None
    timestamp: str | None = None


class N8nTrigger(BaseModel):
    """Generic N8n webhook trigger."""

    workflow_id: str | None = None
    event: str
    data: dict


# ── Webhook Registry ──
@router.post("/register")
async def register_webhook(
    body: WebhookRegister,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireRole(Role.DIRECTOR)),
):
    """Register a webhook URL to receive events. DIRECTOR only."""
    webhook_id = uuid.uuid4().hex[:12]
    _webhook_registry[webhook_id] = {
        "id": webhook_id,
        "url": body.url,
        "events": body.events,
        "secret": body.secret,
        "name": body.name,
        "created_by": str(user.id),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "active": True,
        "delivery_count": 0,
        "error_count": 0,
    }

    await create_audit_entry(
        db,
        action="webhook.register",
        user_id=user.id,
        details={"webhook_id": webhook_id, "url": body.url, "events": body.events},
        ip_address=request.client.host if request.client else None,
    )

    return {"webhook_id": webhook_id, "status": "registered", "events": body.events}


@router.get("/")
async def list_webhooks(
    user: User = Depends(RequireRole(Role.DIRECTOR)),
):
    """List all registered webhooks."""
    return {
        "webhooks": [
            {k: v for k, v in wh.items() if k != "secret"} for wh in _webhook_registry.values()
        ]
    }


@router.delete("/{webhook_id}")
async def delete_webhook(
    webhook_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireRole(Role.DIRECTOR)),
):
    if webhook_id not in _webhook_registry:
        raise HTTPException(status_code=404, detail="Webhook no encontrado")
    del _webhook_registry[webhook_id]

    await create_audit_entry(
        db,
        action="webhook.delete",
        user_id=user.id,
        details={"webhook_id": webhook_id},
        ip_address=request.client.host if request.client else None,
    )
    return {"status": "deleted"}


# ── Dispatch (internal function called by other services) ──
async def dispatch_webhook_event(event: str, payload: dict):
    """
    Send event to all registered webhooks that listen for it.
    Called internally by other services when events occur.
    Non-blocking: fires and forgets (logs errors).
    """
    for wh_id, wh in _webhook_registry.items():
        if not wh["active"] or event not in wh["events"]:
            continue

        body = {
            "event": event,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
            "source": "orogest-lex",
        }

        headers = {"Content-Type": "application/json", "X-OroGest-Event": event}

        # HMAC signature if secret configured
        if wh.get("secret"):
            import json

            sig = hmac.new(
                wh["secret"].encode(), json.dumps(body, sort_keys=True).encode(), hashlib.sha256
            ).hexdigest()
            headers["X-OroGest-Signature"] = f"sha256={sig}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(wh["url"], json=body, headers=headers)
                wh["delivery_count"] += 1
                if resp.status_code >= 400:
                    wh["error_count"] += 1
        except Exception:
            wh["error_count"] += 1


# ── Inbound: WhatsApp via N8n ──
@router.post("/whatsapp/inbound")
async def whatsapp_inbound(
    body: WhatsAppInbound,
    request: Request,
    x_webhook_secret: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Receive inbound WhatsApp messages via N8n.
    Used for lead qualification and case updates.

    Expected N8n flow:
    WhatsApp → N8n → POST /api/v1/webhooks/whatsapp/inbound → OroGest processes → N8n → WhatsApp reply
    """
    # Simple secret validation (production: use proper HMAC)
    expected_secret = settings.SECRET_KEY[:16]
    if x_webhook_secret != expected_secret:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    # Classify the incoming message
    from app.agents.orchestrator import classify_request

    classification = classify_request(body.message)

    # Log it
    await create_audit_entry(
        db,
        action="webhook.whatsapp.inbound",
        details={
            "phone": body.phone[-4:],  # Only last 4 digits for privacy
            "domain": classification.domain.value,
            "urgency": classification.urgency.value,
            "message_length": len(body.message),
        },
        ip_address=request.client.host if request.client else None,
    )

    # Auto-response routing
    response_data = {
        "status": "received",
        "phone": body.phone,
        "classification": {
            "domain": classification.domain.value,
            "urgency": classification.urgency.value,
            "workflow": classification.workflow.value,
            "confidence": classification.confidence,
        },
        "suggested_action": _suggest_whatsapp_action(classification),
    }

    # Dispatch to registered webhooks
    await dispatch_webhook_event("whatsapp.inbound", response_data)

    return response_data


def _suggest_whatsapp_action(classification) -> str:
    """Suggest next action based on message classification."""

    if classification.urgency.value == "critica":
        return "URGENT: Derivar al Dr. Orosa inmediatamente. Llamar al +54 11 6877-7777."

    if classification.domain.value == "inmobiliario":
        return "Agendar consulta inmobiliaria. Enviar formulario de pre-calificación."

    if classification.domain.value == "penal":
        return "Agendar consulta penal urgente. Solicitar datos de la causa."

    return "Agendar consulta general. Enviar horarios disponibles."


# ── Inbound: N8n Generic ──
@router.post("/n8n/trigger")
async def n8n_trigger(
    body: N8nTrigger,
    request: Request,
    x_webhook_secret: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Generic N8n webhook trigger.
    Allows N8n workflows to push events into OroGest.
    """
    expected_secret = settings.SECRET_KEY[:16]
    if x_webhook_secret != expected_secret:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    await create_audit_entry(
        db,
        action=f"webhook.n8n.{body.event}",
        details={
            "workflow_id": body.workflow_id,
            "event": body.event,
            "data_keys": list(body.data.keys()),
        },
        ip_address=request.client.host if request.client else None,
    )

    return {
        "status": "processed",
        "event": body.event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
