#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# OroGest Lex — Setup & Installation Script v1.0
# Estudio Oro S.A.S. | CUIT 30-71933033-5
# ═══════════════════════════════════════════════════════════════

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
GOLD='\033[0;33m'
NC='\033[0m'
BOLD='\033[1m'

echo ""
echo -e "${GOLD}═══════════════════════════════════════════════════${NC}"
echo -e "${GOLD}  OroGest Lex — Instalación v1.0.0${NC}"
echo -e "${GOLD}  Estudio Oro S.A.S.${NC}"
echo -e "${GOLD}═══════════════════════════════════════════════════${NC}"
echo ""

# ── Check prerequisites ──
echo -e "${BOLD}[1/8] Verificando prerequisitos...${NC}"

check_cmd() {
    if command -v "$1" &> /dev/null; then
        echo -e "  ${GREEN}✅${NC} $1 $(command -v $1)"
    else
        echo -e "  ${RED}❌${NC} $1 no encontrado"
        return 1
    fi
}

check_cmd python3 || { echo "Instalar Python 3.12+"; exit 1; }
check_cmd pip || check_cmd pip3 || { echo "Instalar pip"; exit 1; }
PIP_CMD=$(command -v pip3 2>/dev/null || command -v pip)

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo -e "  Python version: ${PYTHON_VERSION}"

# Docker optional
if command -v docker &> /dev/null; then
    echo -e "  ${GREEN}✅${NC} Docker disponible"
    HAS_DOCKER=true
else
    echo -e "  ${YELLOW}⚠️${NC}  Docker no disponible (instalación manual de PostgreSQL/Redis necesaria)"
    HAS_DOCKER=false
fi

# ── Environment setup ──
echo ""
echo -e "${BOLD}[2/8] Configurando entorno...${NC}"

if [ ! -f .env ]; then
    cp .env.example .env
    # Generate real secrets
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(64))")
    ENCRYPTION_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/CAMBIAR-generar-con-openssl-rand-hex-64/$SECRET_KEY/" .env
        sed -i '' "s/CAMBIAR-32-bytes-base64/$ENCRYPTION_KEY/" .env
    else
        sed -i "s/CAMBIAR-generar-con-openssl-rand-hex-64/$SECRET_KEY/" .env
        sed -i "s/CAMBIAR-32-bytes-base64/$ENCRYPTION_KEY/" .env
    fi
    echo -e "  ${GREEN}✅${NC} .env creado con secretos generados"
    echo -e "  ${YELLOW}⚠️${NC}  Editar .env para configurar: CLAUDE_API_KEY, DATABASE_URL"
else
    echo -e "  ${GREEN}✅${NC} .env ya existe"
fi

# ── Install dependencies ──
echo ""
echo -e "${BOLD}[3/8] Instalando dependencias Python...${NC}"

$PIP_CMD install -e ".[dev]" --quiet 2>&1 | tail -3
$PIP_CMD install "bcrypt>=4.0.0,<4.1.0" python-docx --quiet 2>&1 | tail -1
echo -e "  ${GREEN}✅${NC} Dependencias instaladas"

# ── Start infrastructure ──
echo ""
echo -e "${BOLD}[4/8] Infraestructura (PostgreSQL + Redis)...${NC}"

if [ "$HAS_DOCKER" = true ]; then
    echo "  Levantando containers..."
    docker compose up -d db redis 2>&1 | tail -3
    echo "  Esperando que PostgreSQL esté listo..."
    sleep 5
    
    # Wait for PostgreSQL
    for i in {1..30}; do
        if docker compose exec -T db pg_isready -U orogest -d orogest_lex > /dev/null 2>&1; then
            echo -e "  ${GREEN}✅${NC} PostgreSQL listo"
            break
        fi
        sleep 1
        if [ $i -eq 30 ]; then
            echo -e "  ${RED}❌${NC} PostgreSQL no respondió en 30s"
        fi
    done
    
    # Check Redis
    if docker compose exec -T redis redis-cli ping > /dev/null 2>&1; then
        echo -e "  ${GREEN}✅${NC} Redis listo"
    fi
else
    echo -e "  ${YELLOW}⚠️${NC}  Sin Docker. Asegurar PostgreSQL y Redis corriendo manualmente."
    echo "     PostgreSQL: postgresql://orogest:orogest_dev_2026@localhost:5432/orogest_lex"
    echo "     Redis: redis://localhost:6379/0"
fi

# ── Create upload directory ──
echo ""
echo -e "${BOLD}[5/8] Creando directorios...${NC}"
mkdir -p /tmp/orogest/uploads 2>/dev/null || true
echo -e "  ${GREEN}✅${NC} Directorio de uploads creado"

# ── Run tests ──
echo ""
echo -e "${BOLD}[6/8] Ejecutando tests...${NC}"

TEST_OUTPUT=$(python3 -m pytest tests/ -q --tb=line 2>&1)
TEST_RESULT=$?
PASSED=$(echo "$TEST_OUTPUT" | grep -oP '\d+ passed' | head -1)

if [ $TEST_RESULT -eq 0 ]; then
    echo -e "  ${GREEN}✅${NC} Tests: ${PASSED}"
else
    echo -e "  ${RED}❌${NC} Tests fallaron"
    echo "$TEST_OUTPUT" | tail -10
fi

# ── Seed data ──
echo ""
echo -e "${BOLD}[7/8] Cargando datos iniciales...${NC}"

# Only seed if we have DB
if [ "$HAS_DOCKER" = true ]; then
    python3 -m scripts.seed 2>&1 | grep -E "✅|🟢" || echo -e "  ${YELLOW}⚠️${NC}  Seed requiere DB activa"
else
    echo -e "  ${YELLOW}⚠️${NC}  Seed pendiente (necesita DB)"
fi

# ── Final summary ──
echo ""
echo -e "${BOLD}[8/8] Resumen de instalación${NC}"
echo ""

# Count
ENDPOINTS=$(python3 -c "
from app.main import app
routes = [r for r in app.routes if hasattr(r, 'methods') and r.path.startswith('/api')]
print(len(routes))
" 2>/dev/null || echo "?")

TESTS=$(echo "$PASSED" | grep -oP '\d+' || echo "?")

LINES=$(find app/ -name "*.py" -not -path "*__pycache__*" | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}')

echo -e "${GOLD}═══════════════════════════════════════════════════${NC}"
echo -e "${GOLD}  OroGest Lex v1.0.0 — INSTALADO${NC}"
echo -e "${GOLD}═══════════════════════════════════════════════════${NC}"
echo ""
echo -e "  Endpoints API:    ${GREEN}${ENDPOINTS}${NC}"
echo -e "  Tests:            ${GREEN}${TESTS} passed${NC}"
echo -e "  Líneas de código: ${GREEN}${LINES}${NC}"
echo ""
echo -e "  ${BOLD}Comandos:${NC}"
echo -e "    ${GOLD}make dev${NC}              Arrancar API (hot reload)"
echo -e "    ${GOLD}make test${NC}             Ejecutar tests"
echo -e "    ${GOLD}make docker-run${NC}       Arrancar con Docker Compose"
echo -e "    ${GOLD}python -m scripts.cli${NC} CLI de administración"
echo ""
echo -e "  ${BOLD}URLs:${NC}"
echo -e "    API:    http://localhost:8000"
echo -e "    Docs:   http://localhost:8000/docs"
echo -e "    Health: http://localhost:8000/health"
echo ""
echo -e "  ${BOLD}Próximos pasos:${NC}"
echo -e "    1. Editar .env → configurar CLAUDE_API_KEY"
echo -e "    2. ${GOLD}make dev${NC}"
echo -e "    3. POST /api/v1/auth/login con diego@estudiooro.com"
echo ""
echo -e "${GOLD}  Dr. Diego Orosa — Estudio Oro S.A.S.${NC}"
echo -e "${GOLD}  CPACF T° 145 F° 433 | CASI T° LV F° 206${NC}"
echo ""
