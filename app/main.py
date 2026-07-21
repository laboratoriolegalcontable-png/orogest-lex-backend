"""
OroGest Lex — Main Application v2
Estudio Oro S.A.S. | CUIT 30-71933033-5

Full middleware stack:
1. CORS
2. Request logging (timing, correlation IDs)
3. Rate limiting (per-user sliding window)
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.requests import Request

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.middleware.logging_middleware import RequestLoggingMiddleware, setup_logging
from app.middleware.rate_limit import RateLimitMiddleware

settings = get_settings()
logger = logging.getLogger("orogest")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    # ── Startup ──
    setup_logging(debug=settings.DEBUG)
    logger.info(f"OroGest Lex API v{settings.APP_VERSION} starting...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")

    # Try connecting to Redis
    try:
        from app.services.redis_service import get_redis

        redis = await get_redis()
        await redis.ping()
        logger.info("Redis connected ✅")
    except Exception as e:
        logger.warning(f"Redis not available (non-critical): {e}")

    # Log DB config (masked)
    db_host = settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else "configured"
    logger.info(f"Database: {db_host}")
    logger.info(f"Claude model: {settings.CLAUDE_MODEL}")
    logger.info("OroGest Lex API ready 🟢")

    yield

    # ── Shutdown ──
    try:
        from app.services.redis_service import close_redis

        await close_redis()
        logger.info("Redis disconnected")
    except Exception:
        pass
    logger.info("OroGest Lex API shut down 🔴")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "API backend para OroGest Lex — Sistema de gestión legal y real estate "
        "de Estudio Oro S.A.S. (CUIT 30-71933033-5). "
        "RBAC multi-rol, proxy Claude con anti-alucinación y RAG, "
        "audit log SHA-256, due diligence ARG/ESP/URY, "
        "rate limiting, AES-256-GCM encryption."
    ),
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# ── Middleware stack (applied in reverse order) ──
# 3. Rate limiting (outermost after CORS)
app.add_middleware(RateLimitMiddleware)

# 2. Request logging
app.add_middleware(RequestLoggingMiddleware)

# 1. CORS (innermost, applied first)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-Request-ID",
        "X-Response-Time",
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
    ],
)

# ── Routes ──
app.include_router(api_router)


# ── Global exception handler ──
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "unknown")
    logger.exception(f"Unhandled error [{request_id}]: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Error interno del servidor. Contactar soporte.",
            "request_id": request_id,
        },
    )


# ── Health check ──
@app.get("/health")
async def health_check():
    health = {
        "status": "ok",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }

    # Redis check
    try:
        from app.services.redis_service import get_redis

        redis = await get_redis()
        await redis.ping()
        health["redis"] = "connected"
    except Exception:
        health["redis"] = "unavailable"

    return health


# ── API info ──
@app.get("/")
async def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs" if settings.DEBUG else "disabled in production",
        "health": "/health",
        "api": "/api/v1",
        "firma": "Estudio Oro S.A.S. — Dr. Diego Orosa",
    }
