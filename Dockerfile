## OroGest Lex — Multi-stage Dockerfile
## Estudio Oro S.A.S.

# ── Stage 1: Builder ──
FROM python:3.12-slim AS builder

WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir --prefix=/install .

# ── Stage 2: Production ──
FROM python:3.12-slim AS production

LABEL maintainer="Estudio Oro S.A.S. <diego@estudiooro.com>"
LABEL description="OroGest Lex API — Legal & Real Estate Management"

WORKDIR /app

# Runtime deps only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy app
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini .
COPY scripts/ scripts/

# Create non-root user
RUN groupadd -r orogest && useradd -r -g orogest -d /app orogest && \
    mkdir -p /data/orogest/uploads && chown -R orogest:orogest /app /data

USER orogest

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
