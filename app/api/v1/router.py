"""
OroGest Lex — API v1 Router
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    users,
    cases,
    documents,
    properties,
    ai_proxy,
    orchestrator,
    dashboard,
    audit,
    search,
    notifications,
    export,
    calculadora,
    files,
    clients,
    templates,
    timeline,
    batch,
    webhooks,
    events,
    quick,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(cases.router)
api_router.include_router(documents.router)
api_router.include_router(properties.router)
api_router.include_router(ai_proxy.router)
api_router.include_router(orchestrator.router)
api_router.include_router(dashboard.router)
api_router.include_router(audit.router)
api_router.include_router(search.router)
api_router.include_router(notifications.router)
api_router.include_router(export.router)
api_router.include_router(calculadora.router)
api_router.include_router(files.router)
api_router.include_router(clients.router)
api_router.include_router(templates.router)
api_router.include_router(timeline.router)
api_router.include_router(batch.router)
api_router.include_router(webhooks.router)
api_router.include_router(events.router)
api_router.include_router(quick.router)
