# Google Ads — 80 Checks
## Agente: audit-google

### SEARCH (20 checks)

G01 · critico · Calidad de anuncio RSA <7 en campanas activas de alto gasto
G02 · critico · Keywords Broad Match sin Smart Bidding activado
G03 · alto   · RSA con menos de 3 headlines sin pinnear en los primeros 3 slots
G04 · alto   · Sin extension de sitelink en campanas de Search
G05 · alto   · Sin extension de llamada en campanas con objetivo de leads
G06 · alto   · Search Terms report sin revisar en 14+ dias
G07 · alto   · Keywords duplicadas entre grupos de anuncios (canibalismo)
G08 · medio  · Ad Strength < "Bueno" en mas del 50% de RSAs activos
G09 · medio  · Sin negative keywords list a nivel campana
G10 · medio  · Grupos de anuncios con mas de 20 keywords activas
G11 · medio  · Landing page distinta al dominio principal sin razon justificada
G12 · medio  · Bid adjustments manuales sobre campanas con Smart Bidding (conflicto)
G13 · medio  · Sin A/B test de RSA activo en campanas de alto volumen
G14 · medio  · Campana con presupuesto limitado mas de 3 dias consecutivos
G15 · medio  · Search Impression Share <50% con presupuesto disponible
G16 · medio  · Sin extension de precio en campanas de ecommerce con productos listados
G17 · medio  · Customer Match no configurado en campanas de retention o upsell
G18 · medio  · Sin extension de imagen en RSAs de Search elegibles
G19 · medio  · Quality Score promedio <6 en keywords de mayor gasto
G20 · medio  · Sin Audience Targeting en modo observacion en campanas de Search

### PERFORMANCE MAX (20 checks)

G21 · critico · PMax sin asset group dedicado por linea de producto o servicio
G22 · critico · PMax sin senales de audiencia configuradas
G23 · critico · PMax con conversion goal incorrecto o sin conversiones rastreadas
G24 · alto   · PMax sin Customer Match como senal de audiencia principal
G25 · alto   · Asset groups con Asset Strength < "Buena"
G26 · alto   · Menos de 5 headlines por asset group activo
G27 · alto   · Menos de 5 imagenes landscape por asset group
G28 · alto   · Sin video en asset group (Google genera automatico de baja calidad)
G29 · alto   · PMax y Search campana solapando mismas keywords sin prioridad clara
G30 · alto   · Sin negative keyword list aplicada a PMax
G31 · alto   · PMax con ROAS target irreal que limita el volumen de impresiones
G32 · medio  · Sin segmentacion brand vs non-brand dentro de PMax
G33 · medio  · PMax sin datos de offline conversion import
G34 · medio  · Asset groups sin UTM parameters para tracking por segmento
G35 · medio  · Sin Shopping feed vinculado en PMax de ecommerce con catalogo
G36 · medio  · PMax con budget compartido con otras campanas (distorsion)
G37 · medio  · Sin Merchant Center vinculado correctamente a la cuenta
G38 · medio  · PMax sin datos de Enhanced Conversions activos
G39 · medio  · Sin remarketing list como senal de audiencia en PMax
G40 · medio  · PMax activo menos de 6 semanas sin respetar periodo de aprendizaje

### AI MAX / DEMAND GEN (15 checks)

G41 · critico · AI Max no configurado en campanas Search elegibles con volumen suficiente
G42 · alto   · AI Max con URL expansion deshabilitada sin razon justificada
G43 · alto   · Enhanced Conversions deshabilitado en la cuenta
G44 · alto   · Demand Gen sin formato de video corto (<30s) para YouTube Shorts
G45 · alto   · Demand Gen sin lookalike audiences configuradas
G46 · alto   · Demand Gen solapando audiencias con campanas de Display existentes
G47 · medio  · AI Max sin brand exclusions configuradas
G48 · medio  · Demand Gen sin split de creativos por segmento de audiencia
G49 · medio  · Demand Gen sin frequency cap configurado
G50 · medio  · AI Max sin datos de conversion en primeras 2 semanas de vida
G51 · medio  · Demand Gen sin URL custom para cada ad format
G52 · medio  · Sin Google Tag Manager correctamente instalado y publicado en el sitio
G53 · medio  · Conversion window menor al ciclo de venta real del negocio
G54 · medio  · Smart Bidding sin suficientes conversiones para operar correctamente (min 50/mes)
G55 · medio  · Sin Google Analytics 4 vinculado con datos de conversion importados

### CTV / YOUTUBE VIDEO (25 checks)

G56 · critico · YouTube skippable sin hook en primeros 5 segundos
G57 · critico · Sin Bumper Ads (6s) como complemento a TrueView en campanas de branding
G58 · alto   · Video con resolucion menor a 1080p en campanas activas
G59 · alto   · YouTube sin Brand Safety exclusions configuradas
G60 · alto   · YouTube Shorts sin formato vertical 9:16
G61 · alto   · CTV campana sin frequency capping configurado
G62 · alto   · Sin companion banner en campanas de TrueView in-stream
G63 · alto   · YouTube sin Google Ads vinculado a Analytics 4 con conversiones de vista
G64 · alto   · Video ad con duracion >2 min sin justificacion de upper funnel
G65 · medio  · YouTube sin view-through conversion window configurado
G66 · medio  · CTV sin IP exclusions para trafico no deseado o bots
G67 · medio  · Sin secuencia de video (Video Ad Sequencing) para storytelling
G68 · medio  · YouTube sin remarketing de video viewers a campanas de Search
G69 · medio  · CTV targeting por contenido sin exclusion de contenido sensible
G70 · medio  · Video sin closed captions para accesibilidad y retencion
G71 · medio  · YouTube Demand Gen sin conexion a Google Merchant Center para ecommerce
G72 · medio  · Sin Director Mix para personalizacion de creativos por audiencia
G73 · medio  · YouTube sin test de duracion activo (15s vs 30s vs 60s)
G74 · medio  · CTV sin medicion de Brand Lift activa en campanas de awareness
G75 · medio  · Video sin CTA overlay configurado
G76 · medio  · Sin revision de YouTube Analytics en los ultimos 30 dias
G77 · medio  · Campana de video sin audiencias de intencion como targeting primario
G78 · medio  · Sin custom affinity audience basada en URLs de competidores
G79 · medio  · YouTube sin datos de conversion de vista rastreados
G80 · medio  · Sin Google Surveys for Brand Measurement en campanas de awareness
