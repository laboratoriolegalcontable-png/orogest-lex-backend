# TikTok Ads — 28 Checks
## Agente: audit-tiktok

### SMART+ / CAMPANAS AUTOMATICAS (8 checks)

T01 · critico · Smart+ campana sin minimo de 50 conversiones/semana para que el algoritmo optimice
T02 · critico · Events API de TikTok no configurada — dependencia total del Pixel del navegador
T03 · alto   · Smart+ con creative controls que limitan el algoritmo innecesariamente
T04 · alto   · Budget de Smart+ <$100/dia — volumen insuficiente para fase de aprendizaje
T05 · alto   · Sin exclusion de compradores recientes en Smart+ de prospecting
T06 · alto   · Smart+ sin datos de Customer File como senal de audiencia de calidad
T07 · alto   · Spark Ads no activados cuando hay contenido organico de la marca con buen engagement
T08 · medio  · Sin test de creativos nativos (UGC-style) vs creativos producidos en estudio

### GMV MAX / TIKTOK SHOP (6 checks)

T09 · critico · TikTok Shop no vinculado correctamente al Business Center de la cuenta
T10 · critico · GMV Max sin producto catalog actualizado (sync con retraso >48 horas)
T11 · alto   · GMV Max sin video de producto en formato nativo vertical (<60s, 9:16)
T12 · alto   · Shop Ads sin precio visible en el creativo (reduce CTR a tienda)
T13 · medio  · Sin campana de GMV Max testeada en cuentas de ecommerce con catalogo elegible
T14 · medio  · TikTok Shop sin reviews de producto activas en la plataforma

### CREATIVOS / SYMPHONY (8 checks)

T15 · critico · Creativos con duracion >60s en campanas de conversion (drop-off critico en TikTok)
T16 · critico · Sin hook claro en primeros 2 segundos — el 63% de las vistas se pierden ahi
T17 · alto   · Creativos producidos en estudio sin elementos nativos de TikTok (texto animado, sonido, estilo UGC)
T18 · alto   · Sin rotacion de creativos en los ultimos 14 dias en campanas activas (fatiga)
T19 · alto   · Video sin sonido o musica activos — el 93% del contenido en TikTok se consume con sonido
T20 · alto   · Sin subtitulos en video (afecta accesibilidad y retencion del contenido)
T21 · medio  · Sin test de TikTok Symphony (generacion de creativos con IA) en cuentas elegibles
T22 · medio  · Sin CTA nativo visible en los ultimos 5 segundos del video

### SEARCH ADS / EVENTS API (6 checks)

T23 · alto   · TikTok Search Ads no activados en campanas con presupuesto y audiencia elegibles
T24 · alto   · Pixel de TikTok sin verificacion de instalacion en los ultimos 30 dias
T25 · alto   · Events API sin deduplicacion de eventos con el Pixel del navegador
T26 · medio  · Sin campana de Search Ads con Hashtag targeting en nicho relevante de la marca
T27 · medio  · Events API con latencia >2 horas en envio de eventos de compra o lead
T28 · medio  · Sin TikTok Instant Page configurada para landing page nativa de la plataforma
