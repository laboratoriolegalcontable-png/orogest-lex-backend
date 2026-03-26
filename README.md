# OroGest Lex — Backend API v1.0.0

**Estudio Oro S.A.S.** | CUIT 30-71933033-5 | Dr. Diego Orosa
Sistema de gestión legal y real estate con IA integrada.

## Métricas

| Métrica | Valor |
|---------|-------|
| Endpoints API | **77** |
| Módulos | **21** |
| Tests | **140** ✅ |
| Modelos DB | **9** |
| Líneas código (app) | **7,168** |
| Líneas tests | **1,281** |
| Archivos Python | **54** |

## Stack Tecnológico

| Componente | Tecnología |
|------------|-----------|
| Runtime | Python 3.12 + FastAPI (async) |
| Database | PostgreSQL 16 + pgvector |
| Cache | Redis 7 |
| Auth | JWT access/refresh + RBAC 4 niveles (16 permisos) |
| AI | Proxy Claude API + anti-alucinación + RAG |
| Audit | SHA-256 chained log (tamper-evident) |
| Encryption | AES-256-GCM (Ley 25.326) |
| Export | DOCX (escritos/cartas/DD) + CSV |
| Real-time | SSE (Server-Sent Events) |
| Webhooks | N8n + WhatsApp integration |
| Scheduler | Background deadline scanner |
| Deploy | Docker multi-stage + production compose |

## 21 Módulos / 77 Endpoints

| Módulo | Endpoints | Descripción |
|--------|-----------|-------------|
| auth | 6 | Login, refresh, register, password management |
| users | 5 | CRUD usuarios, activar/desactivar |
| cases | 5 | CRUD causas judiciales (11 ramas) |
| clients | 6 | CRUD clientes, KYC/PEP, vinculación a causas |
| documents | 6 | CRUD con versionado, historial |
| properties | 6 | CRUD + due diligence ARG/ESP/URY |
| ai | 2 | Proxy Claude con anti-alucinación + RAG |
| orchestrator | 2 | Clasificador dominio/urgencia/workflow |
| templates | 5 | Plantillas de escritos reutilizables |
| export | 5 | DOCX (escritos, cartas, DD) + CSV |
| calculadora | 1 | Indemnización Art. 245 LCT completa |
| files | 2 | Upload/download (50MB, SHA-256) |
| batch | 3 | Operaciones masivas (status, assign, tags) |
| webhooks | 5 | N8n + WhatsApp inbound/outbound |
| events | 2 | SSE real-time stream |
| quick | 2 | Mobile-optimized status |
| timeline | 2 | Activity feed por causa/usuario |
| notifications | 5 | Alertas de vencimientos |
| dashboard | 2 | Métricas + health check |
| audit | 4 | Logs + chain verification |
| search | 1 | Búsqueda global cross-entity |

## Instalación Rápida

```bash
git clone <repo> && cd orogest-backend
chmod +x setup.sh && ./setup.sh
```

## Instalación Manual

```bash
# 1. Infra
docker compose up -d db redis

# 2. Config (genera secretos automáticamente)
cp .env.example .env
# Editar: CLAUDE_API_KEY=sk-ant-xxx

# 3. Deps
pip install -e ".[dev]" && pip install "bcrypt>=4.0.0,<4.1.0" python-docx

# 4. Seed
python -m scripts.seed

# 5. API
uvicorn app.main:app --reload

# 6. Tests
pytest tests/ -v

# 7. CLI admin
python -m scripts.cli stats
python -m scripts.cli seed-templates
```

## Producción

```bash
# Con Docker Compose
docker compose -f docker-compose.prod.yml up -d

# Incluye: API (4 workers) + PostgreSQL + Redis + Scheduler automático
```

## CLI de Administración

```bash
python -m scripts.cli seed              # Datos iniciales
python -m scripts.cli create-user       # Crear usuario
python -m scripts.cli list-users        # Listar usuarios
python -m scripts.cli reset-password    # Resetear contraseña
python -m scripts.cli stats             # Estadísticas
python -m scripts.cli verify-audit      # Verificar cadena audit
python -m scripts.cli seed-templates    # Cargar plantillas del sistema
```

## Plantillas de Escritos Incluidas

1. **Nulidad por prueba digital ilegal** — Cellebrite/WhatsApp, cadena de custodia, casación-ready
2. **Carta documento por incumplimiento** — Intimación 48hs, fehaciente
3. **Morigeración de prisión preventiva** — Domiciliaria, Arts. 210/283 CPPN

## Honestidad Técnica

- **77 endpoints, 140 tests, 7,168 líneas**: todo implementado y testeado
- **El orquestador es determinístico** (keywords), no autónomo
- **Anti-alucinación = regex + system prompt**, no garantía absoluta
- **Valores RIPTE/SMVM/topes**: los provee el usuario, nunca el sistema
- **Requiere infra real** (PostgreSQL, Redis, Claude API key) para producción
