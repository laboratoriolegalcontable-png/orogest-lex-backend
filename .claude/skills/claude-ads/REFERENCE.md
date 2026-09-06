# Referencia — Claude Ads v2.4.0

## Prompts listos para usar

### Primera auditoria completa

```
/ads audit

Mi gasto mensual es $[cantidad] repartido en [Meta / Google / TikTok].
Mi objetivo del trimestre es [conversiones / leads / ventas / trafico].

Quiero:
1. Ads Health Score general y grade A-F
2. Sub-scores por plataforma para ver donde estoy sangrando
3. Los 5 critical issues mas urgentes con tiempo estimado de fix
4. Quick wins que pueda implementar hoy en menos de 1 hora cada uno
5. Cualquier compliance flag (Special Ad Categories, Consent Mode V2)

Al terminar, correre /ads next para priorizar el top 3.
```

### Plan estrategico por industria

```
/ads plan [ecommerce / local-service / real-estate / healthcare / finance / agency / generic]

Producto o servicio: [descripcion breve en 1-2 lineas]
Mercado: [pais o region]
Presupuesto mensual: $[cantidad]
Objetivo: [leads / ventas / instalaciones / awareness]
Plataformas: [Meta / Google / TikTok / todas]

Quiero:
1. Estructura de campanas recomendada por plataforma
2. Audiencias y exclusiones especificas para esta industria
3. Reparto de presupuesto con razones
4. KPIs objetivo con benchmarks de industria
5. Disclosures regulatorios si aplica
```

### Inteligencia de competencia cross-plataforma

```
/ads competitor

Competidores principales: [competidor 1], [competidor 2], [competidor 3]
Industria: [industria]
Plataformas activas: [Meta / Google / TikTok]

Para cada competidor:
1. Tipos de anuncios activos y volumen estimado
2. Angulos creativos y mensajes principales
3. Audiencias y geos donde estan pujando
4. Patrones de creativos (formato, duracion, hooks)

Cerrar con 3 oportunidades concretas donde pueda diferenciarme o superar su posicionamiento.
```

### Auditoria de creativos

```
/ads creative

Plataformas a revisar: [Meta / Google / TikTok]

Evaluar:
- Hook en primeros 3 segundos (video) o headline (imagen)
- Frecuencia vs engagement (fatiga creativa)
- Diversidad de formatos
- Claridad del CTA
- Match con la landing page

Dar ranking de mejores a peores con recomendaciones especificas.
```

### Calculadora de rentabilidad

```
/ads math

Datos de mi cuenta:
- Gasto mensual: $[cantidad]
- Ingresos atribuidos: $[cantidad]
- Ticket promedio: $[cantidad]
- Margen bruto: [%]
- Conversiones del mes: [numero]

Calcular: CPA, ROAS, Break-even ROAS, MER y si el mix de plataformas tiene sentido.
```

### Diseno de A/B test

```
/ads test

Plataforma: [Meta / Google / TikTok]
Campana: [descripcion]
Quiero testear: [variable — hook / CTA / imagen / audiencia / copy]

Hipotesis: creo que [variable A] funciona mejor que [variable B] porque [razon].
Budget disponible para el test: $[cantidad/dia]
Duracion maxima: [X dias]

Dame el diseno completo del test con sample size minimo y criterio de victoria.
```

## Configurar conexiones — guia rapida

### Meta Ads (5 minutos)
1. Ir a business.facebook.com → Configuracion → Usuarios del sistema
2. Crear Usuario del sistema con permisos de anunciante
3. Generar token con scope: `ads_read, ads_management`
4. Guardar: Ad Account ID (formato: act_XXXXXXXXXX)
5. Variables de entorno: `META_ACCESS_TOKEN` y `META_AD_ACCOUNT_ID`

### Google Ads (1-3 dias habiles)
1. Solicitar Developer Token en developers.google.com/google-ads
2. Crear credenciales OAuth 2.0 en Google Cloud Console
3. Obtener Customer ID de tu cuenta (formato: XXX-XXX-XXXX)
4. Variables de entorno: `GOOGLE_DEVELOPER_TOKEN`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_CUSTOMER_ID`

### TikTok Ads (1 hora)
1. Ir a ads.tiktok.com → Tools → TikTok for Business API
2. Crear app con permisos: `advertiser:read, campaign:read`
3. Generar Access Token (renovar cada 30 dias con refresh token)
4. Variables de entorno: `TIKTOK_ACCESS_TOKEN` y `TIKTOK_ADVERTISER_ID`

### Prompt para configurar desde cero

```
Tengo Claude Ads instalado y ya corri /ads start. Quiero conectar mis cuentas
con la API directa para tener datos en vivo.

Mis plataformas activas son: [Meta / Google / TikTok]

Para cada plataforma:
1. Dime exactamente que credenciales necesito y donde sacarlas (con URLs)
2. Llevame paso a paso por el OAuth
3. Verifica con una llamada de lectura que funciona antes de seguir
4. Guarda todo en ~/.claude-ads/profile.json una vez verificado

Empieza en read-only. Solo habilita escritura despues de confirmar que funciona.
```

## Benchmarks por industria — 2026

| Industria | CPA objetivo | ROAS minimo | CTR Search | CPM Meta |
|---|---|---|---|---|
| Ecommerce DTC | $15-45 | 3.0x | 3-5% | $8-15 |
| Servicios locales | $25-80 | 4.0x | 5-8% | $12-20 |
| SaaS B2B | $80-200 | 2.5x | 2-4% | $15-30 |
| Real Estate | $40-120 | 2.0x | 3-6% | $10-18 |
| Healthcare | $30-90 | 3.5x | 4-7% | $11-22 |
| Finanzas | $50-150 | 2.8x | 2-5% | $18-35 |
| Infoproductos | $20-60 | 4.0x | 3-6% | $8-16 |
| Apps moviles | $2-8 CPI | 2.0x | 1-3% | $6-12 |

## Activacion global — todos los proyectos

Para que Claude Ads se active automaticamente en CUALQUIER sesion y proyecto:

```bash
# Copiar skill a la carpeta global de Claude
cp -r .claude/skills/claude-ads ~/.claude/skills/
cp .claude/hooks/ads-start.sh ~/.claude/hooks/

# Agregar al ~/.claude/settings.json global:
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/.claude/hooks/ads-start.sh",
            "timeout": 10,
            "statusMessage": "Cargando Claude Ads v2.4.0..."
          }
        ]
      }
    ]
  }
}
```

## Recursos relacionados

- `CLAUDE-ADS.md` — Descripcion general del skill (raiz del repo)
- `CLAUDE-META-ADS.md` — Guia especifica de Meta Ads
- `GOOGLE-ADS-CAMPANAS.md` — Guia especifica de Google Ads
- `.claude/skills/claude-ads/checks/` — Los 161 checks por plataforma
