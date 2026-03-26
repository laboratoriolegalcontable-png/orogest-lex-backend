# OroGest Lex — Makefile
# Estudio Oro S.A.S.

.PHONY: help dev test lint clean docker seed migrate

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Development ──
dev: ## Start API with hot reload
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

install: ## Install dependencies
	pip install -e ".[dev]"
	pip install "bcrypt>=4.0.0,<4.1.0"

# ── Database ──
docker-up: ## Start PostgreSQL + Redis
	docker compose up -d db redis

docker-down: ## Stop all containers
	docker compose down

migrate: ## Run Alembic migrations
	alembic upgrade head

migration: ## Create new migration (usage: make migration msg="add xyz")
	alembic revision --autogenerate -m "$(msg)"

seed: ## Seed initial data (director user + samples)
	python -m scripts.seed

# ── Testing ──
test: ## Run all tests
	pytest tests/ -v --tb=short

test-fast: ## Run tests without verbose
	pytest tests/ -q

test-coverage: ## Run tests with coverage
	pytest tests/ --cov=app --cov-report=term-missing

# ── Linting ──
lint: ## Lint code
	ruff check app/ tests/

format: ## Format code
	ruff format app/ tests/

# ── Docker ──
docker-build: ## Build Docker image
	docker build -t orogest-lex-api .

docker-run: ## Run full stack
	docker compose up --build

# ── Cleanup ──
clean: ## Remove caches and temp files
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache .mypy_cache
	find . -name "*.pyc" -delete

# ── Info ──
routes: ## List all API routes
	python -c "from app.main import app; [print(f'{r.methods} {r.path}') for r in app.routes if hasattr(r, 'methods')]"

count: ## Count lines of code
	@echo "Python source:"
	@find app/ -name "*.py" | xargs wc -l | tail -1
	@echo "Tests:"
	@find tests/ -name "*.py" | xargs wc -l | tail -1
