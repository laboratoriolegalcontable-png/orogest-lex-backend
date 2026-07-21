"""
OroGest Lex — Request Logging Middleware
Structured logging for all API requests with timing, error capture, and request ID.
"""

import logging
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("orogest.api")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Logs every request with:
    - Request ID (for correlation)
    - Method, path, status code
    - Response time in ms
    - User ID if authenticated
    - Error details on 4xx/5xx
    """

    SKIP_PATHS = {"/health", "/docs", "/redoc", "/openapi.json", "/favicon.ico"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        start_time = time.perf_counter()

        # Extract user hint from auth header (lightweight, no validation)
        user_hint = self._extract_user_hint(request)

        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 1)

            log_data = {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
                "user": user_hint,
                "ip": request.client.host if request.client else None,
            }

            if response.status_code >= 500:
                logger.error("Request failed", extra=log_data)
            elif response.status_code >= 400:
                logger.warning("Client error", extra=log_data)
            elif duration_ms > 5000:
                logger.warning("Slow request", extra=log_data)
            else:
                logger.info("Request completed", extra=log_data)

            # Add headers for correlation
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{duration_ms}ms"
            return response

        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 1)
            logger.exception(
                "Unhandled exception",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                    "error": str(exc)[:500],
                },
            )
            raise

    def _extract_user_hint(self, request: Request) -> str | None:
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            try:
                import base64
                import json

                payload = auth[7:].split(".")[1]
                payload += "=" * (4 - len(payload) % 4)
                decoded = json.loads(base64.urlsafe_b64decode(payload))
                return decoded.get("email") or decoded.get("sub")
            except Exception:
                pass
        return None


# ═══════════════════════════════════════════
# STRUCTURED LOG FORMAT
# ═══════════════════════════════════════════
class StructuredFormatter(logging.Formatter):
    """JSON-like structured log formatter for production."""

    def format(self, record):
        base = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        # Add extra fields
        for key in ("request_id", "method", "path", "status", "duration_ms", "user", "ip", "error"):
            if hasattr(record, key):
                base[key] = getattr(record, key)
        return str(base)


def setup_logging(debug: bool = False):
    """Configure logging for the application."""
    level = logging.DEBUG if debug else logging.INFO

    # Console handler
    handler = logging.StreamHandler()
    handler.setLevel(level)

    if debug:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )
    else:
        formatter = StructuredFormatter()

    handler.setFormatter(formatter)

    # Configure root and app loggers
    for logger_name in ("orogest", "orogest.api", "uvicorn"):
        log = logging.getLogger(logger_name)
        log.setLevel(level)
        log.addHandler(handler)
        log.propagate = False
