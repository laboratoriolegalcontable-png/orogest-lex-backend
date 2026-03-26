#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# OroGest Lex — Setup macOS
# Estudio Oro S.A.S. | Dr. Diego Orosa
# ═══════════════════════════════════════════════════════════════

set -e

GOLD='\033[0;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

echo ""
echo -e "${GOLD}═══════════════════════════════════════════════════${NC}"
echo -e "${GOLD}  OroGest Lex v1.0.0 — Setup macOS${NC}"
echo -e "${GOLD}  Estudio Oro S.A.S.${NC}"
echo -e "${GOLD}═══════════════════════════════════════════════════${NC}"
echo ""

# ═══════════════════════════════════════════
# STEP 1: Check/Install Homebrew
# ═══════════════════════════════════════════
echo -e "${BOLD}[1/7] Verificando Homebrew...${NC}"

if command -v brew &> /dev/null; then
    echo -e "  ${GREEN}✅${NC} Homebrew instalado"
else
    echo -e "  ${YELLOW}⚠️${NC}  Homebrew no encontrado. Instalando..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Add to PATH for Apple Silicon
    if [ -f /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
    fi
    echo -e "  ${GREEN}✅${NC} Homebrew instalado"
fi

# ═══════════════════════════════════════════
# STEP 2: Install Python 3.12
# ═══════════════════════════════════════════
echo ""
echo -e "${BOLD}[2/7] Verificando Python 3.12...${NC}"

PYTHON_CMD=""

# Check if python3.12 exists
if command -v python3.12 &> /dev/null; then
    PYTHON_CMD="python3.12"
    echo -e "  ${GREEN}✅${NC} Python 3.12 encontrado: $(python3.12 --version)"
elif command -v python3 &> /dev/null; then
    PY_VER=$(python3 -c "import sys; print(sys.version_info.minor)")
    if [ "$PY_VER" -ge 11 ]; then
        PYTHON_CMD="python3"
        echo -e "  ${GREEN}✅${NC} Python 3.${PY_VER} encontrado"
    fi
fi

if [ -z "$PYTHON_CMD" ]; then
    echo -e "  ${YELLOW}📦${NC} Instalando Python 3.12 via Homebrew..."
    brew install python@3.12
    PYTHON_CMD="python3.12"
    
    # Homebrew Python path for Apple Silicon
    if [ -f /opt/homebrew/bin/python3.12 ]; then
        PYTHON_CMD="/opt/homebrew/bin/python3.12"
    fi
    echo -e "  ${GREEN}✅${NC} Python 3.12 instalado"
fi

echo -e "  Usando: ${GOLD}$PYTHON_CMD$(${PYTHON_CMD} --version 2>&1 | awk '{print " "$2}')${NC}"

# ═══════════════════════════════════════════
# STEP 3: Create virtual environment
# ═══════════════════════════════════════════
echo ""
echo -e "${BOLD}[3/7] Creando entorno virtual...${NC}"

if [ -d "venv" ]; then
    echo -e "  ${GREEN}✅${NC} venv ya existe"
else
    $PYTHON_CMD -m venv venv
    echo -e "  ${GREEN}✅${NC} venv creado"
fi

# Activate
source venv/bin/activate
echo -e "  ${GREEN}✅${NC} venv activado: $(python --version)"

# Upgrade pip
pip install --upgrade pip setuptools wheel --quiet
echo -e "  ${GREEN}✅${NC} pip actualizado"

# ═══════════════════════════════════════════
# STEP 4: Install dependencies
# ═══════════════════════════════════════════
echo ""
echo -e "${BOLD}[4/7] Instalando dependencias...${NC}"

pip install \
    "fastapi>=0.115.0" \
    "uvicorn[standard]>=0.30.0" \
    "sqlalchemy[asyncio]>=2.0.30" \
    "asyncpg>=0.29.0" \
    "alembic>=1.13.0" \
    "pydantic>=2.7.0" \
    "pydantic-settings>=2.3.0" \
    "python-jose[cryptography]>=3.3.0" \
    "passlib>=1.7.4" \
    "bcrypt>=4.0.0,<4.1.0" \
    "python-multipart>=0.0.9" \
    "redis>=5.0.0" \
    "httpx>=0.27.0" \
    "cryptography>=42.0.0" \
    "python-docx>=1.1.0" \
    "email-validator>=2.0.0" \
    "pytest>=8.0.0" \
    --quiet 2>&1 | tail -3

echo -e "  ${GREEN}✅${NC} Dependencias instaladas"

# ═══════════════════════════════════════════
# STEP 5: Configure .env
# ═══════════════════════════════════════════
echo ""
echo -e "${BOLD}[5/7] Configurando entorno...${NC}"

if [ ! -f .env ] || grep -q "CAMBIAR-generar" .env 2>/dev/null; then
    cp .env.example .env
    SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(64))")
    ENCRYPTION_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
    
    sed -i '' "s/CAMBIAR-generar-con-openssl-rand-hex-64/$SECRET_KEY/" .env
    sed -i '' "s/CAMBIAR-32-bytes-base64/$ENCRYPTION_KEY/" .env
    echo -e "  ${GREEN}✅${NC} .env creado con secretos generados"
else
    echo -e "  ${GREEN}✅${NC} .env ya configurado"
fi

# ═══════════════════════════════════════════
# STEP 6: Run tests
# ═══════════════════════════════════════════
echo ""
echo -e "${BOLD}[6/7] Ejecutando tests...${NC}"

TEST_OUTPUT=$(python -m pytest tests/ -q --tb=line 2>&1)
PASSED=$(echo "$TEST_OUTPUT" | grep -oE '[0-9]+ passed' | head -1)

if echo "$TEST_OUTPUT" | grep -q "passed"; then
    echo -e "  ${GREEN}✅${NC} Tests: ${PASSED}"
else
    echo -e "  ${RED}❌${NC} Algunos tests fallaron:"
    echo "$TEST_OUTPUT" | tail -5
fi

# ═══════════════════════════════════════════
# STEP 7: Final summary
# ═══════════════════════════════════════════
echo ""
echo -e "${BOLD}[7/7] Verificación final...${NC}"

ENDPOINTS=$(python -c "
from app.main import app
routes = [r for r in app.routes if hasattr(r, 'methods') and r.path.startswith('/api')]
print(len(routes))
" 2>/dev/null || echo "?")

VERSION=$(python -c "from app.core.config import get_settings; print(get_settings().APP_VERSION)" 2>/dev/null || echo "?")

echo ""
echo -e "${GOLD}═══════════════════════════════════════════════════${NC}"
echo -e "${GOLD}  OroGest Lex v${VERSION} — INSTALADO ✅${NC}"
echo -e "${GOLD}═══════════════════════════════════════════════════${NC}"
echo ""
echo -e "  Endpoints:  ${GREEN}${ENDPOINTS}${NC}"
echo -e "  Tests:      ${GREEN}${PASSED}${NC}"
echo -e "  Python:     $(python --version)"
echo -e "  Entorno:    $(pwd)/venv"
echo ""
echo -e "  ${BOLD}Para arrancar la API:${NC}"
echo ""
echo -e "    ${GOLD}cd $(pwd)${NC}"
echo -e "    ${GOLD}source venv/bin/activate${NC}"
echo -e "    ${GOLD}uvicorn app.main:app --reload${NC}"
echo ""
echo -e "  ${BOLD}Después abrir:${NC}"
echo -e "    http://localhost:8000       → Info"
echo -e "    http://localhost:8000/docs  → Swagger UI"
echo -e "    http://localhost:8000/health → Health check"
echo ""
echo -e "  ${BOLD}Para usar con PostgreSQL + Redis (opcional):${NC}"
echo ""
echo -e "    ${GOLD}brew install postgresql@16 redis${NC}"
echo -e "    ${GOLD}brew services start postgresql@16${NC}"
echo -e "    ${GOLD}brew services start redis${NC}"
echo -e "    ${GOLD}createdb orogest_lex${NC}"
echo -e "    ${GOLD}python -m scripts.seed${NC}"
echo ""
echo -e "  ${BOLD}CLI de administración:${NC}"
echo ""
echo -e "    ${GOLD}python -m scripts.cli stats${NC}"
echo -e "    ${GOLD}python -m scripts.cli seed-templates${NC}"
echo ""
echo -e "${GOLD}  Dr. Diego Orosa — Estudio Oro S.A.S.${NC}"
echo -e "${GOLD}  CPACF T° 145 F° 433 | CASI T° LV F° 206${NC}"
echo ""
