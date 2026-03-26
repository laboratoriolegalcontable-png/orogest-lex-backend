"""
OroGest Lex — Rate Limiting Middleware (Fase 12)
Redis-based sliding window rate limiter per user.

Limits:
- AI endpoints: CLAUDE_PROXY_RATE_LIMIT requests/minute (default 30)
- General API: 120 requests/minute per user
- Auth endpoints: 10 login attempts per 5 minutes per IP
"""

import time
from typing import Callable

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings

settings = get_settings()


class InMemoryRateLimiter:
    """
    Simple in-memory rate limiter for development.
    In production, replace with Redis-based implementation.

    Uses sliding window counters per key.
    """

    def __init__(self):
        self._windows: dict[str, list[float]] = {}

    def _clean_window(self, key: str, window_seconds: int):
        now = time.time()
        if key in self._windows:
            self._windows[key] = [
                t for t in self._windows[key] if now - t < window_seconds
            ]

    def check(self, key: str, max_requests: int, window_seconds: int = 60) -> tuple[bool, int]:
        """
        Check if request is allowed.
        Returns: (allowed: bool, remaining: int)
        """
        self._clean_window(key, window_seconds)

        if key not in self._windows:
            self._windows[key] = []

        current_count = len(self._windows[key])

        if current_count >= max_requests:
            return False, 0

        self._windows[key].append(time.time())
        return True, max_requests - current_count - 1


# Singleton
_limiter = InMemoryRateLimiter()


# ── Rate limit configurations ──
RATE_LIMITS = {
    "/api/v1/ai/": {"max_requests": settings.CLAUDE_PROXY_RATE_LIMIT, "window": 60},
    "/api/v1/orchestrator/execute": {"max_requests": settings.CLAUDE_PROXY_RATE_LIMIT, "window": 60},
    "/api/v1/auth/login": {"max_requests": 10, "window": 300},  # 10 per 5 min by IP
    "default": {"max_requests": 120, "window": 60},
}


def get_rate_limit_config(path: str) -> dict:
    """Get rate limit config for a given path."""
    for prefix, config in RATE_LIMITS.items():
        if prefix != "default" and path.startswith(prefix):
            return config
    return RATE_LIMITS["default"]


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware that enforces per-user rate limits.
    Extracts user from JWT if available, falls back to IP.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip health check
        if request.url.path in ("/health", "/docs", "/redoc", "/openapi.json"):
            return await call_next(request)

        # Determine rate limit key
        # Try to extract user from auth header
        key = self._get_rate_key(request)
        config = get_rate_limit_config(request.url.path)

        allowed, remaining = _limiter.check(
            key=key,
            max_requests=config["max_requests"],
            window_seconds=config["window"],
        )

        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Demasiadas solicitudes. Esperá un momento antes de reintentar.",
                headers={
                    "Retry-After": str(config["window"]),
                    "X-RateLimit-Limit": str(config["max_requests"]),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(config["max_requests"])
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response

    def _get_rate_key(self, request: Request) -> str:
        """Build rate limit key: user_id if authenticated, IP otherwise."""
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            # Extract sub from JWT without full validation (just for rate limit key)
            try:
                import base64, json
                token = auth_header[7:]
                payload = token.split(".")[1]
                # Add padding
                payload += "=" * (4 - len(payload) % 4)
                decoded = json.loads(base64.urlsafe_b64decode(payload))
                user_id = decoded.get("sub", "")
                if user_id:
                    return f"user:{user_id}:{request.url.path}"
            except Exception:
                pass

        # Fallback to IP
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}:{request.url.path}"
