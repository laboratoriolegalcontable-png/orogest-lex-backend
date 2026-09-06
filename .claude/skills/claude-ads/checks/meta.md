# Meta Ads — 50 Checks
## Agente: audit-meta

### PIXEL / CAPI / PRIVACY (12 checks)

M01 · critico · Pixel de Meta no instalado o sin disparar en paginas clave del funnel
M02 · critico · Conversions API (CAPI) no desplegada — 30-40% de perdida de datos estimada
M03 · critico · EMQ (Event Match Quality) < 6.0 en eventos principales (Purchase, Lead)
M04 · critico · Consent Mode no configurado en mercados UE, UK o con regulacion de privacidad
M05 · alto   · Eventos duplicados sin deduplicacion correcta entre Pixel y CAPI
M06 · alto   · Evento Purchase sin parametros value y currency enviados correctamente
M07 · alto   · Sin eventos de mid-funnel activos (ViewContent, AddToCart, InitiateCheckout)
M08 · alto   · Attribution window < 7 dias sin justificacion estrategica
M09 · medio  · Pixel sin Advanced Matching configurado (email, phone hashed)
M10 · medio  · CAPI con latencia de envio >1 hora respecto al evento real del usuario
M11 · medio  · Sin test de eventos en Meta Events Manager en los ultimos 30 dias
M12 · medio  · AEM (Aggregated Event Measurement) no configurado en campanas iOS

### ESTRUCTURA DE CAMPANAS (12 checks)

M13 · critico · Campana activa sin conversion goal configurado correctamente
M14 · critico · Budget diario <$5 por ad set — insuficiente para fase de aprendizaje
M15 · alto   · Mas de 5 ad sets activos en una sola campana (fragmentacion de presupuesto)
M16 · alto   · Ad sets con audiencias solapadas >60% sin exclusion mutua
M17 · alto   · Campana sin periodo de aprendizaje completado antes de hacer cambios
M18 · alto   · Sin campana de remarketing activa con Custom Audience de visitantes web
M19 · alto   · Sin campana de retention activa con Customer List de compradores
M20 · alto   · Campana de conversion con audience >50M sin testear audiencias mas acotadas
M21 · medio  · Sin Lifetime Budget en campanas estacionales o de periodo limitado
M22 · medio  · Campaign Budget Optimization (CBO) deshabilitado en campanas con 3+ ad sets
M23 · medio  · Ad sets pausados sin archivar (ensucian el reporting y la interfaz)
M24 · medio  · Sin campana de Lookalike basada en lista de compradores (LAL 1%)

### ADVANTAGE+ (8 checks)

M25 · critico · Advantage+ Shopping no testeada en cuentas de ecommerce con $5k+/mes de gasto
M26 · alto   · Advantage+ con creative controls todos habilitados sin testing previo
M27 · alto   · Advantage+ sin exclusion de Customer List de compradores recientes
M28 · alto   · Budget de Advantage+ <$100/dia — volumen insuficiente para optimizacion
M29 · medio  · Advantage+ Shopping y campanas manuales sin split de budget claro
M30 · medio  · Sin Advantage+ Creative activo en ad sets manuales elegibles
M31 · medio  · Advantage+ sin segmento de audience de "existing customers" configurado
M32 · medio  · Sin comparacion sistematica de performance Advantage+ vs campanas manuales

### CREATIVOS / ANDROMEDA (10 checks)

M33 · critico · Ad set con un solo creativo activo (sin diversidad para el algoritmo Andromeda)
M34 · critico · Frecuencia >3 en campanas de cold audience con CPM en alza
M35 · alto   · Sin creativos en formato Reels o vertical 9:16 en campanas activas
M36 · alto   · Creativos con texto sobre imagen que supera el 20% del area visual
M37 · alto   · Sin hook claro en primeros 3 segundos en videos de Feed o Reels
M38 · alto   · Creativos con mas de 60 dias sin refresh en campanas con frecuencia alta
M39 · medio  · Sin A/B test de concepto creativo activo en campanas de prospecting
M40 · medio  · Todos los creativos del mismo formato (falta mix video / imagen / carousel)
M41 · medio  · Sin Dynamic Creative Testing (DCT) activo en campanas de prospecting
M42 · medio  · Creativos sin subtitulos en videos (85% del contenido se ve sin sonido en Meta)

### AUDIENCIAS (8 checks)

M43 · alto   · Broad Audience activa sin datos de pixel suficientes (<1000 eventos/semana)
M44 · alto   · Detailed Targeting Expansion habilitado en campanas con audiencia muy especifica
M45 · alto   · Sin exclusion de Custom Audience de compradores recientes en campanas de prospecting
M46 · alto   · Remarketing audiences con menos de 1000 personas activas (volumen insuficiente)
M47 · medio  · Sin segmentacion por etapa del funnel (TOF / MOF / BOF) en campanas distintas
M48 · medio  · Lookalike basado en email list desactualizada (sin refresh en mas de 90 dias)
M49 · medio  · Sin Engagement Custom Audience activa (video viewers, page engagers, IG interactors)
M50 · medio  · Sin uso de Interests targeting validado con Audience Insights antes de escalar
