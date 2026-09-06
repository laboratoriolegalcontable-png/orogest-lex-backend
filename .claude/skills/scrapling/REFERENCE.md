# SCRAPLING v3.0 — REFERENCE

Referencia completa de prompts, configuracion, plantillas y precios de mercado.

---

## CONFIG MCP — claude_desktop_config.json

Agregar dentro de `"mcpServers"` sin sobreescribir otros MCPs:

```json
{
  "mcpServers": {
    "scrapling": {
      "command": "uvx",
      "args": ["--from", "scrapling[all]", "scrapling-mcp"]
    }
  }
}
```

Alternativa si uvx no funciona:
```json
{
  "scrapling": {
    "command": "uv",
    "args": ["run", "--with", "scrapling[all]", "scrapling-mcp"]
  }
}
```

**Ubicacion del archivo:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

Despues de modificar: cerrar Claude Desktop con Cmd+Q y reabrir.

---

## PROMPTS MAESTROS POR GRUPO

### JURIDICO — Prompts de extraccion

#### Empresas nuevas (societario)
```
Usa Scrapling para buscar nuevas sociedades S.A. y S.R.L. registradas en Argentina
en los ultimos 6 meses. Fuente: registros publicos de IGJ o AFIP si estan disponibles.

Para cada una quiero: razon social, CUIT/CUIL, fecha de inscripcion, domicilio legal,
actividad declarada, y si encontras datos del representante legal (nombre y cargo).

Filtra solo las que tengan mas de 1 ano desde su inscripcion inicial (ya pasaron la
etapa de riesgo — tienen activos pero todavia son jovenes = necesitan abogado).

Ordena por antiguedad descendente. Exporta a ~/Desktop/SCRAPLING-BASES/juridico-leads.xlsx
tab "Societario". Score asignado: +3 si tiene mas de 3 anos, +2 si el sector es
salud/construccion/finanzas, +2 si tiene empleados declarados.
```

#### CEOs y directivos para derecho penal/laboral premium
```
Usa Scrapling para extraer perfiles de LinkedIn de personas con cargo CEO, Director
General, Socio, Gerente de RRHH en empresas argentinas de 50 a 500 empleados,
activas en los sectores: construccion, salud, tecnologia, retail y logistica.

Para cada perfil quiero: nombre completo, cargo, empresa, tamano de empresa estimado,
sector, ciudad, URL del perfil y email si aparece en la bio.

No extraer datos de perfiles privados — solo informacion publica.
Limita a 50 perfiles por ejecucion. Guarda en tab "Penal-Laboral".
```

#### Personas buscando abogado activamente
```
Usa Scrapling para buscar publicaciones recientes en MercadoLibre servicios, OLX y
Clasificados Argentina donde personas buscan: abogado, estudio juridico, consulta
legal, divorcio, sucesion, herencia, accidente laboral.

Para cada publicacion: titulo, descripcion, ciudad, fecha, y cualquier dato de
contacto visible. Prioriza publicaciones de los ultimos 30 dias.

Exporta a tab "Busqueda-Activa". Score: +5 (demanda inmediata confirmada).
```

---

### INMOBILIARIA — Prompts de extraccion

#### Propiedades publicadas +90 dias (vendedores urgentes)
```
Usa Scrapling para extraer propiedades de ZonaProp y Argenprop que:
- Sean departamentos o casas (no terrenos)
- Precio entre $80,000 y $500,000 USD
- Publicadas hace mas de 90 dias sin actualizacion significativa
- En zonas: CABA, GBA Norte (Tigre, San Isidro, Vicente Lopez), GBA Sur (Lomas, Quilmes)

Para cada propiedad: titulo, precio, superficie, zona, barrio, fecha de publicacion,
dias en el mercado, nombre del propietario (si es particular), telefono, email,
descripcion completa y link directo.

Filtra: solo propiedades publicadas por PROPIETARIO (sin inmobiliaria).
Ordena por "dias en mercado" descendente — los mas desesperados primero.
Score: +3 por cada 30 dias adicionales sobre 90, +2 por propietario sin inmobiliaria.

Exporta a ~/Desktop/SCRAPLING-BASES/inmobiliaria-leads.xlsx tab "Vendedores-Urgentes".
```

#### Inversores en LinkedIn
```
Usa Scrapling para buscar perfiles de LinkedIn en Argentina con estos terminos en
el cargo o bio: "inversor inmobiliario", "real estate investor", "desarrollador
inmobiliario", "inversiones en propiedades", "portafolio de propiedades".

Para cada perfil: nombre, cargo, empresa (si aplica), ubicacion, descripcion,
seguidores estimados, URL, email si aparece publicamente.

Solo perfiles con actividad reciente (publicaron en los ultimos 3 meses).
Exporta a tab "Inversores".
```

#### Constructoras con permisos activos
```
Usa Scrapling para buscar constructoras y desarrolladoras con permisos de construccion
activos o expedientes abiertos en municipios de CABA y GBA. Fuentes posibles:
GCBA datos abiertos (data.buenosaires.gob.ar), boletines municipales online.

Para cada empresa: razon social, CUIT, obra en curso (si aparece), zona,
representante o contacto declarado.

Exporta a tab "Desarrolladores".
```

---

### IA/TECNOLOGIA — Prompts de extraccion

#### Agencias de marketing sin IA
```
Usa Scrapling para encontrar agencias de marketing y publicidad en Argentina con
estas caracteristicas:
- Google Maps: 3+ estrellas, 10+ resenas
- SIN ChatBot o asistente IA visible en su web
- Web con diseno anterior a 2022 (indicio de stack desactualizado)
- Tamano estimado: 5-50 empleados (LinkedIn o "nosotros" page)

Para cada una: nombre, telefono, direccion, web, email de contacto (si esta en la
web), nombre del dueno o director (Google Maps o LinkedIn), tamano estimado,
servicios que ofrecen, URL de Google Maps.

Score: +3 si no tienen IA, +2 si el web es viejo, +2 si tienen mas de 20 empleados.

Exporta a ~/Desktop/SCRAPLING-BASES/ia-automatizacion-leads.xlsx tab "Agencias-Mktg".
Busca en: CABA, GBA, Cordoba, Rosario, Mendoza.
```

#### Estudios contables con 5+ profesionales
```
Usa Scrapling para extraer estudios contables y de auditoria de Google Maps en
Argentina que tengan:
- 4+ estrellas y 15+ resenas
- Descripcion que mencione "equipo", "profesionales", "socios"
- Sin sistema digital visible (sin software de gestion mencionado en web o Maps)

Para cada uno: nombre, telefono, direccion, web, calificacion, resenas,
contador o socio principal (si aparece en Maps o web), email.

Score: +3 si tienen 10+ empleados estimados, +2 si no mencionan software digital,
+2 si estan en zona comercial premium.

Exporta a tab "Estudios-Contables".
```

#### Startups argentinas con funding reciente
```
Usa Scrapling para buscar startups argentinas que hayan levantado inversion en los
ultimos 12 meses. Fuentes: Crunchbase, Latam Startup, blogs de VC, LinkedIn.

Para cada startup: nombre, sector, monto levantado (si se conoce), fundadores (nombre
y LinkedIn), tamano del equipo, ciudad, web, email de contacto.

Filtra: solo las que tengan entre 5 y 100 empleados (ya tienen dinero pero no quieren
contratar masivo — escenario perfecto para automatizacion con IA).

Score: +4 si levantaron mas de $500k, +3 si el sector es compatible con automatizacion
(fintech, healthtech, edtech, e-commerce, logistica).

Exporta a tab "Startups".
```

---

### GASTRONOMIA — Prompts de extraccion

#### Cafes y restaurantes sin web propia
```
Usa Scrapling para extraer cafes, cafeterias de especialidad y restaurantes de
Buenos Aires (zonas: Palermo, Belgrano, San Telmo, Recoleta, Villa Crespo) que:
- Tengan mas de 100 resenas en Google Maps
- Calificacion 4.0 o superior
- NO tengan web propia (solo Instagram o sin presencia digital)

Para cada uno: nombre, direccion, telefono, calificacion, numero de resenas,
horario, si tiene web o no, link de Instagram si tienen.

Ordena por numero de resenas descendente (los mas populares sin web son el
mejor prospecto — ya tienen demanda, solo les falta presencia digital).

Score: +3 por cada 100 resenas sobre 100, +3 por no tener web, +2 por zona premium.

Exporta a ~/Desktop/SCRAPLING-BASES/gastronomia-leads.xlsx tab "Sin-Web".
```

---

### SALUD — Prompts de extraccion

#### Clinicas sin sistema de turnos online
```
Usa Scrapling para extraer clinicas privadas, centros medicos y consultorios en
CABA y GBA que:
- Tengan 15+ resenas en Google Maps
- NO mencionen "turnos online", "reserva online" o "agenda digital" en su descripcion
- Tengan mas de 3 especialidades (indicio de tamano suficiente)

Para cada uno: nombre, especialidades, telefono, direccion, calificacion, resenas,
web (si tiene), email de contacto.

Score: +3 si tienen 10+ profesionales, +3 si no tienen turnos online,
+2 si estan en zona de alto poder adquisitivo.

Exporta a ~/Desktop/SCRAPLING-BASES/salud-leads.xlsx tab "Clinicas".
```

---

## PLANTILLA DE PROPUESTA COMERCIAL

Para vender listas de leads como servicio de Estudio Oro:

```
PROPUESTA DE SERVICIO — LISTA DE LEADS CALIFICADOS
Fecha: [FECHA]
Para: [NOMBRE DEL CLIENTE]
Preparado por: Estudio Oro

QUE INCLUYE ESTA LISTA
  - [N] leads de [nicho] en [ciudad/zona]
  - Score de calidad 1-10 por cada registro
  - Datos verificados: nombre, telefono, web, email (cuando disponible)
  - Exportada en Excel con tabs por zona geografica
  - Primer mensaje de contacto personalizado para cada lead (3 canales)
  - Plan de publicacion recomendado

VALOR DE MERCADO
  Agencias de leads especializadas cobran:
  - Lista basica (nombre + telefono): $5-15 por lead
  - Lista enriquecida (+ email + web + score): $15-40 por lead
  - Para [N] leads: valor de mercado estimado $[N x $25] USD

NUESTRA PROPUESTA
  Precio: $[X] USD (incluye actualizacion mensual)
  - Entrega en 48hs desde la confirmacion
  - Actualizacion mensual con leads nuevos
  - Soporte para configurar la campana de contacto

GARANTIA
  Si mas del 20% de los datos estan incorrectos o desactualizados,
  los reponemos sin costo adicional.

PROXIMO PASO
  Confirmar el nicho y las zonas geograficas para empezar la extraccion.
  Responder este mensaje o llamar a [TELEFONO].
```

---

## TABLA DE PRECIOS DE MERCADO (referencia)

| Tipo de lista | Precio por lead (agencia) | Lo que cobra Estudio Oro |
|---------------|--------------------------|--------------------------|
| Nombre + telefono basico | $5-10 USD | $2-5 USD |
| Enriquecida (+ email + web) | $15-25 USD | $8-15 USD |
| Premium (+ score + mensajes) | $30-60 USD | $15-30 USD |
| Con monitoreo mensual | $50-100/lead/ano | $20-40/lead/ano |
| Lista juridica (CEO/Director) | $40-80 USD | $20-40 USD |
| Lista inmobiliaria (propietarios) | $25-50 USD | $12-25 USD |
| Lista de startups con funding | $60-100 USD | $30-50 USD |

---

## EXCEL MULTI-TAB — Estructura de columnas

### Columnas estandar (todos los grupos)
A: Nombre / Empresa
B: Telefono (formato E.164)
C: Email
D: Web
E: Direccion
F: Ciudad
G: Pais
H: Zona (CABA / GBA Norte / GBA Sur / Interior)
I: Calificacion Google Maps
J: Numero de resenas
K: Score potencial (1-10)
L: Canal de origen (Google Maps / LinkedIn / Instagram / Directorio)
M: Fecha de extraccion
N: Etapa CRM (Nuevo / Contactado / Interesado / Propuesta / Cerrado)
O: Mensaje WhatsApp (listo para copiar)
P: Primer email (listo para copiar)
Q: LinkedIn InMail (listo para copiar)
R: Notas
S: Proxima accion
T: Fecha de seguimiento

### Columnas especificas por grupo

**JURIDICO** (columnas adicionales):
- CUIT/CUIL
- Cargo del decision maker
- Rama del derecho relevante
- Patrimonio estimado (visible/alto/muy alto)

**INMOBILIARIO** (columnas adicionales):
- Precio de la propiedad (USD)
- Superficie (m2)
- Dias en el mercado
- Tipo (venta/alquiler/inversion)
- Propietario directo (SI/NO)

**IA/TECNOLOGIA** (columnas adicionales):
- Numero de empleados (estimado)
- Sector/industria
- Stack tecnologico visible
- Tiene IA actualmente (SI/NO)
- Proceso mas automatizable

---

## TROUBLESHOOTING POR SITIO

### Google Maps bloquea
```python
# Activar Camoufox explicitamente
from scrapling.defaults import Camoufox
page = Camoufox(headless=False)  # headless=False para debugging
# Agregar delay entre requests
import time; time.sleep(random.uniform(3, 8))
```
Alternativa: cambiar a Yelp o TripAdvisor para el mismo nicho.

### LinkedIn requiere login
Scrapling no puede bypassear el muro de login de LinkedIn sin credenciales.
Alternativa: usar la busqueda publica de Google con operador site:linkedin.com.
Ejemplo: `site:linkedin.com/in "CEO" "empresa argentina" "fintech"`

### ZonaProp o Argenprop devuelven resultados vacios
Probar con diferentes User-Agent via Camoufox. Si persiste, usar
MercadoLibre propiedades que tiene scraping mas permisivo.

### scrapling install falla
```bash
# Instalar Playwright manualmente
pip install playwright
playwright install chromium

# Instalar Camoufox manualmente
pip install camoufox
python -m camoufox fetch
```

### MCP no aparece en Claude Desktop
1. Verificar JSON valido en claude_desktop_config.json (usar jsonlint.com)
2. Verificar que el comando `uvx` existe: `uvx --version`
3. Cerrar Claude con Cmd+Q (no solo cerrar la ventana)
4. Revisar logs de Claude Desktop en `~/Library/Logs/Claude/`

---

## INTEGRACION WHAPI (notificaciones WhatsApp)

El MCP de Whapi ya esta configurado en el proyecto como escenario `s4472022`.
Para enviar notificacion al terminar una extraccion:

Mensaje de notificacion automatico:
```
Scrapling completo
Nicho: [nicho]
Ciudad: [ciudad]
Leads encontrados: [N]
Score promedio: [X]/10
Leads con score +8: [N]
Guardado en: Desktop/SCRAPLING-BASES/[archivo].xlsx
```

---

## INTEGRACION NOTION CRM

Estructura de base de datos Notion recomendada por grupo:

**Propiedades:**
- Nombre (titulo)
- Empresa (texto)
- Telefono (telefono)
- Email (email)
- Score (numero 1-10)
- Etapa (select: Nuevo/Contactado/Interesado/Propuesta/Cerrado)
- Canal origen (select: Google Maps/LinkedIn/Instagram/Directorio)
- Ultimo contacto (fecha)
- Proxima accion (texto)
- Fecha seguimiento (fecha)
- Grupo (select: Juridico/Inmobiliario/IA/Gastronomia/Salud/Otros)
- Notas (texto largo)

**Vistas recomendadas:**
- Kanban por Etapa (pipeline visual)
- Lista ordenada por Score (prioridad de contacto)
- Calendario por Fecha de seguimiento
- Tabla para exportar a Google Sheets

---

## PRECIOS DE ADS — Referencias por sector (Argentina 2026)

| Sector | CPL promedio Google Ads | CPL promedio Meta Ads | Ticket promedio del cliente |
|--------|------------------------|----------------------|----------------------------|
| Abogado (especialidad) | $15-40 USD | $8-20 USD | $1,000-10,000 USD |
| Inmobiliaria | $20-60 USD | $10-30 USD | Comision 3% de la operacion |
| IA/Automatizacion | $30-80 USD | $15-40 USD | $2,000-8,000 USD |
| Diseno web | $10-25 USD | $5-15 USD | $500-3,000 USD |
| Clinica (turnos online) | $20-50 USD | $10-25 USD | $500-2,000 USD |

**Break even aproximado (inversion $500 USD/mes):**
- Juridico: cerrar 1 caso de $1,500+ USD = break even
- Inmobiliario: cerrar 1 operacion de $100,000 USD = break even en el mes 1
- IA: cerrar 1 proyecto de $2,000 USD = break even
