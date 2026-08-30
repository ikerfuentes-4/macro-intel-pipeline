# Macro Intelligence Pipeline

Pipeline 100% autónomo y modular en Python que ingiere, contrasta, analiza y registra
predicciones macroeconómicas y geopolíticas, diseñado como track record técnico verificable.

## Arquitectura

```
[1] INGESTA MULTI-FUENTE          [2] CONSENSO CRUZADO          [3] ANÁLISIS MACRO         [4] TRACK RECORD           [5] DASHBOARD
 ingestion/sources.py       ->     crosscheck/clustering.py  ->  analysis/schemas.py    ->  persistence/db.py    ->   api/server.py
 ingestion/fetchers.py             crosscheck/reliability.py     analysis/system_prompt.py  persistence/track_record.py frontend/index.html
 ingestion/raw_data_lake.py        crosscheck/consensus.py       analysis/macro_engine.py   evaluation/market_data.py
        |                                  |                            |                          |                       |
   data/raw_lake/*.jsonl          veredicto LLM + reglas          JSON estructurado         SQLite / PostgreSQL      mapa interactivo
   (inmutable, append-only)       deterministas anti-sesgo        con geolocalizacion        + evaluación automática  (Leaflet + Tailwind)
```

El LLM se invoca a través de [llm/client.py](llm/client.py), una capa agnóstica de proveedor.
Por defecto usa **Google Gemini** (tier gratuito de Google AI Studio); como alternativa admite
**Groq** (tier gratuito, modelos Llama). Ninguno de los dos requiere tarjeta de crédito.

Orquestado por [main.py](main.py) (`run` y `evaluate`), con puntos de entrada dedicados para
tareas programadas en [scheduler/](scheduler/).

### Por qué esta separación

- **Data Lake crudo vs. base curada**: los artículos tal cual se capturaron viven en archivos
  `.jsonl` inmutables (evidencia auditable), independientes de la base de datos relacional que
  solo contiene eventos ya validados. Así nunca se pierde el rastro de qué se ingirió, aunque
  el filtro de consenso lo descarte después.
- **Verificador de hechos ≠ analista**: `crosscheck/consensus.py` usa un system prompt y una
  tool distintos de `analysis/macro_engine.py`. El primero solo certifica convergencia factual
  entre fuentes; el segundo interpreta implicaciones económicas sobre hechos ya certificados.
  Mezclar ambos roles en un solo prompt es la forma más común de que un LLM "alucine" análisis
  sobre hechos no verificados.
- **JSON mode + revalidación Pydantic, agnóstico de proveedor**: `llm/client.py` fuerza al
  modelo (Gemini o Groq) a responder en modo JSON nativo, describiendo el JSON Schema esperado
  en el propio prompt, y revalida la respuesta con Pydantic al recibirla, con un reintento
  automático si el JSON no es válido. Se prefirió este patrón a function-calling nativo porque
  el formato de schema de funciones difiere sustancialmente entre proveedores (soporte de
  `$ref`, uniones, campos nulos...), mientras que "JSON mode + schema en el prompt" funciona
  igual en cualquiera.
- **Hipótesis falsables ancladas a tickers reales**: cada `FalsifiableHypothesis` exige un
  ticker de Yahoo Finance, un comparador (`>`, `<`, `>=`, `<=`, `~=`) y un umbral numérico, de
  modo que `persistence/track_record.py` puede evaluarla sin intervención humana ni ambigüedad.
- **Geolocalización con corrección determinista**: el LLM decide QUÉ lugar es relevante para
  `MacroAnalysis.ubicacion` (juicio contextual), pero [geo/geocode.py](geo/geocode.py)
  contrasta ese nombre contra un catálogo verificado de centroides de países (ampliado más
  allá de los que tienen conflicto armado propio) y de regiones/áreas no nacionales (estrechos,
  mares, territorios en disputa), con alias en español y coincidencia difusa como respaldo. Si
  hay coincidencia, se sobreescriben las coordenadas del LLM con el dato verificado; si no, se
  conserva su estimación. Mismo principio anti-alucinación que el resto del pipeline: usar el
  dato verificable cuando existe, en vez de confiar ciegamente en el modelo.

## Instalación (Windows / PowerShell)

```bash
cd macro-intel-pipeline
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Edita `.env` y configura como mínimo una de estas dos opciones (ambas gratuitas, sin tarjeta):

- **Gemini (por defecto, `LLM_PROVIDER=gemini`)**: consigue una clave gratuita en
  https://aistudio.google.com/apikey (solo requiere iniciar sesión con una cuenta de Google) y
  ponla en `GEMINI_API_KEY`.
- **Groq (`LLM_PROVIDER=groq`)**: consigue una clave gratuita en
  https://console.groq.com/keys y ponla en `GROQ_API_KEY`.

El resto de variables tienen valores por defecto razonables (ver comentarios en
[.env.example](.env.example)). Los nombres de modelo gratuito por defecto
(`gemini-2.5-flash`, `llama-3.3-70b-versatile`) pueden quedar desactualizados con el tiempo;
revisa la documentación de cada proveedor si el pipeline reporta un modelo no encontrado y
ajusta `GEMINI_MODEL` / `GROQ_MODEL` en `.env`.

## Uso manual

```bash
python main.py run
```

Ejecuta: ingesta de todas las fuentes en [ingestion/sources.py](ingestion/sources.py) → guardado
crudo en `data/raw_lake/` → clustering de noticias por evento → veredicto de consenso cruzado
(LLM + reglas deterministas) → análisis macro estructurado para los eventos aprobados →
persistencia en `data/macro_intel.db` (SQLite por defecto).

```bash
python main.py evaluate
```

Busca predicciones cuya `fecha_limite_revision` ya venció, obtiene el dato de mercado real vía
`yfinance` y marca cada una como `CUMPLIDA`, `FALLIDA` o `ERROR` (si el ticker falla). Imprime
un resumen JSON con el track record acumulado (aciertos, fallos, tasa de acierto).

## Dashboard geoespacial

```bash
uvicorn api.server:app --reload --port 8000
```

Abre http://localhost:8000. Es un backend FastAPI ([api/server.py](api/server.py)) que expone
`GET /api/events` (todos los análisis con su consenso, geolocalización y estado de predicción)
y `GET /api/summary` (métricas agregadas del track record), y sirve el frontend estático
([frontend/index.html](frontend/index.html)) desde el mismo origen — sin CORS, sin build step.

El frontend es una única página HTML con **Tailwind CSS** y **Leaflet.js + OpenStreetMap**
(vía CDN, sin npm/webpack). Se eligió Leaflet sobre Mapbox porque no requiere cuenta ni clave
de API en absoluto —ni siquiera un tier gratuito con registro—, consistente con el resto del
proyecto. Los tiles oscuros son de CartoDB (gratuitos, requieren solo la atribución visible en
el mapa). El mapa hace polling a `/api/events` cada 60s (no hay WebSockets; es "tiempo real"
en el sentido de refresco periódico, no push instantáneo) y cada marcador, al hacer clic,
despliega un panel lateral con: titular/resumen del evento, fuentes contrastadas, causa raíz
geopolítica, vectores de impacto, predicción de tipos de interés, reacción de activos,
hipótesis falsable con su estado actual (pendiente/cumplida/fallida) y las limitaciones y
sesgos que el propio análisis declaró.

Nota: `cdn.tailwindcss.com` avisa en consola que no es apto para producción (recompila en cada
carga). Para un uso personal/portfolio es aceptable; si despliegas esto públicamente con
tráfico real, compila Tailwind con su CLI o como plugin de PostCSS.

### Capa de conflictos activos (todos, no solo los que aparecen en las noticias del día)

```bash
python main.py sync-conflicts
```

El pipeline de noticias (`python main.py run`) solo genera un análisis cuando un evento tiene
corroboración multi-institucional real ese día — es intencionadamente estricto, así que la
mayoría de conflictos en curso (Sudán, Yemen, Myanmar, RD Congo...) no van a tener cobertura
fresca con 2+ tipos de fuente cada 24-48h. Para mostrar **todos** los conflictos activos, no
solo los analizados, [`ingestion/conflict_registry.py`](ingestion/conflict_registry.py)
sincroniza la lista *"List of ongoing armed conflicts"* de Wikipedia (vía su API oficial,
gratuita y sin registro) — una fuente editada activamente, no una lista fija escrita a mano
que quedaría desactualizada. Cada conflicto se geolocaliza con un centroide estático de país
(`geo/country_centroids.py`, dato geográfico estable, no LLM).

Esta capa es deliberadamente **factual, no analizada por IA**: no pasa por consenso cruzado ni
por el motor macro, se muestra en el mapa como puntos grises distinguibles de los eventos
analizados (coloreados), y su tarjeta de detalle no ofrece impacto económico — para eso está
el predictor de producto. Sincronízala periódicamente (los conflictos cambian poco día a día,
con `scheduler/cron_sync_conflicts.py` para Task Scheduler) — `GET /api/conflicts` la expone.

### Predictor de producto: arquitectura multi-pestaña (segunda pestaña del dashboard)

Al escribir un producto financiero y pulsar "Analizar", `POST /api/predict` orquesta 4 bloques
de datos **reales, no generados por el LLM** ([analysis/product_research.py](analysis/product_research.py)):

1. **Conflictos_Geopoliticos** — el registro completo sincronizado desde Wikipedia, con
   coordenadas.
2. **Bancos_Centrales_Tipos** — titulares en vivo de las fuentes oficiales de bancos centrales
   ya configuradas (Fed, BCE, BoJ, BoE, Banco de Canadá, RBA, SNB) + proxies reales de tipos
   (`^IRX`, `^TNX`, `^TYX` via yfinance).
3. **Cadenas_Suministro_Energia** — WTI, Brent, gas natural y cobre (proxy industrial) via
   yfinance.
4. **Sentimiento_Fondos** — VIX, S&P 500, Euro Stoxx 50, oro y DXY como proxies de mercado
   (no son datos de flujos de fondos de pago tipo EPFR/Bloomberg — eso requeriría una API de
   pago, incompatible con el objetivo "sin tarjeta de crédito").

El LLM (`analysis/system_prompt.py:PRODUCT_FORECAST_SYSTEM_PROMPT`) sintetiza cada bloque por
separado y luego los **cruza** en una tesis de inversión (`ProductForecast.tesis_inversion`),
con una hipótesis falsable de igual rigor que el motor principal (ticker real, comparador,
umbral, fecha límite). El resultado se guarda en la respuesta como `report_url`: un informe
**Excel de 5 pestañas** (`analysis/product_report.py`, vía `openpyxl`) — "Analisis_Activo" como
pestaña principal + las 4 pestañas de datos crudos que lo alimentaron, para que el cruce de
variables sea auditable en vez de una caja negra.

Decisión de diseño importante: la hipótesis falsable de cada consulta **sí se persiste**, pero
en una tabla y un track record **separados** del pipeline automático
(`persistence/product_track_record.py`, expuesto en `GET /api/product-summary`). Nunca se
combinan con `GET /api/summary`: una consulta bajo demanda del usuario (potencialmente
repetible hasta obtener una respuesta favorable) y un análisis automático sobre una noticia ya
contrastada por consenso cruzado no son estadísticamente comparables — mezclarlos
distorsionaría la credibilidad del track record principal. La interfaz lo dice explícitamente
y muestra ambos contadores por separado.

## Ejecución autónoma (Windows Task Scheduler)

Para que el pipeline corra solo, crea dos tareas programadas apuntando a los scripts dedicados
en `scheduler/` (evita pasar argumentos por CLI, más robusto para tareas programadas):

```bash
schtasks /create /tn "MacroIntel_Ingesta" /tr "\"C:\Users\ikerf\Desktop\Webs\macro-intel-pipeline\.venv\Scripts\python.exe\" \"C:\Users\ikerf\Desktop\Webs\macro-intel-pipeline\scheduler\cron_ingest.py\"" /sc hourly /mo 4 /st 06:00
```

```bash
schtasks /create /tn "MacroIntel_Evaluacion" /tr "\"C:\Users\ikerf\Desktop\Webs\macro-intel-pipeline\.venv\Scripts\python.exe\" \"C:\Users\ikerf\Desktop\Webs\macro-intel-pipeline\scheduler\cron_evaluate.py\"" /sc daily /st 23:30
```

```bash
schtasks /create /tn "MacroIntel_Conflictos" /tr "\"C:\Users\ikerf\Desktop\Webs\macro-intel-pipeline\.venv\Scripts\python.exe\" \"C:\Users\ikerf\Desktop\Webs\macro-intel-pipeline\scheduler\cron_sync_conflicts.py\"" /sc daily /st 05:00
```

Ajusta rutas, frecuencia (`/sc hourly /mo 4` = cada 4 horas) y hora a tu preferencia. Verifica
las tareas con `schtasks /query /tn "MacroIntel_Ingesta"` y revisa los logs en la consola de
salida (redirígelos a archivo con `>> ingesta.log 2>&1` si prefieres persistirlos).

Alternativa multiplataforma: `crontab -e` con las mismas rutas si migras a Linux/macOS, o
`APScheduler` en un proceso long-running si prefieres no depender del scheduler del SO.

## Construyendo el track record público

1. Cada `python main.py run` añade análisis nuevos con hipótesis y fecha límite fijadas
   **antes** de conocerse el resultado — condición necesaria para que el track record sea
   creíble (no se puede reescribir una predicción después del hecho).
2. `python main.py evaluate` (programado diariamente) cierra las predicciones vencidas de
   forma determinista contra datos de mercado reales.
3. Para publicarlo como portfolio verificable: commitea periódicamente un export de
   `track_record_summary()` (o la base SQLite completa si aceptas exponerla) a un repositorio
   público. El historial de commits de Git actúa como sello de tiempo adicional de que las
   predicciones no se alteraron retroactivamente.
4. El dashboard en [api/server.py](api/server.py) + [frontend/index.html](frontend/index.html)
   ya expone `/api/summary` con las métricas agregadas listas para mostrar públicamente.

## Extender fuentes

Añade entradas a `SOURCES` en [ingestion/sources.py](ingestion/sources.py). Para fuentes sin
RSS público (ej. Bloomberg, Reuters Terminal, NewsAPI), crea un conector nuevo en
[ingestion/fetchers.py](ingestion/fetchers.py) que devuelva una lista de `RawArticle` — el
resto del pipeline es agnóstico al método de ingesta. Recuerda asignar un `institution_type`
correcto: es lo que usa el motor de consenso para exigir diversidad institucional real.

Si una fuente discontinúa su RSS o lo protege con detección de bots (403 incluso con
User-Agent de navegador real — no intentes sortearlo, es justo lo que esa protección busca
evitar), usa el helper `_google_news_proxy(dominio, window="7d")` de `sources.py`: construye
una búsqueda RSS de Google News filtrada por `site:dominio`, que sí es un servicio público
legítimo. Es el patrón usado hoy para 10 de las 26 fuentes configuradas (verificado con
peticiones HTTP reales, no asumido). Limitación: el `link` de estas entradas apunta a un
redirect de `news.google.com`, no a la URL directa del artículo.

Red de fuentes actual (26 fuentes, 6 tipos institucionales):

| Tipo | Fuentes |
|---|---|
| `banco_central` (7) | Fed, BCE, BoJ, BoE, Banco de Canadá, RBA (Australia), SNB (Suiza) |
| `organismo_multilateral` (2) | FMI, Banco Mundial |
| `agencia_prensa` (3) | Reuters, BBC, Al Jazeera |
| `think_tank` (9) | CFR, Brookings, Chatham House, RAND, Crisis Group, Atlantic Council, CSIS, The Diplomat, Carnegie Endowment, SIPRI |
| `defensa_seguridad` (4) | War on the Rocks, Defense One, Breaking Defense, ISW |

`defensa_seguridad` es una categoría nueva, separada de `think_tank`: análisis especializado y
más técnico de conflicto armado, que también ayuda al motor de consenso a detectar diversidad
institucional real en eventos puramente militares que los think tanks generalistas no cubren
con la misma profundidad.

## Limitaciones conocidas

- Varias instituciones (Reuters, FMI, Banco Mundial, CFR, Brookings, Chatham House) ya no
  ofrecen RSS directo estable; se sirven vía el proxy de Google News (ver arriba). Si en el
  futuro alguna recupera un feed propio, sustituye su entrada en `ingestion/sources.py` por la
  URL oficial.
- El clustering por similitud de titulares (`rapidfuzz`) es una heurística ligera, no semántica
  completa; eventos con títulos muy distintos entre fuentes pueden no agruparse. Ver nota de
  extensibilidad en [crosscheck/clustering.py](crosscheck/clustering.py) para migrar a
  embeddings si lo necesitas.
- La geolocalización se corrige contra un catálogo verificado (`geo/geocode.py`) cuando el
  lugar es reconocible, pero para lugares muy específicos ausentes del catálogo (una ciudad
  pequeña, una instalación concreta) se conserva la estimación del LLM — sigue sin ser
  geocodificación de precisión de nivel calle. Amplía `geo/country_centroids.py` o
  `geo/region_centroids.py` si detectas un lugar recurrente mal ubicado.
- El registro de conflictos activos posiciona cada conflicto en el centroide del PRIMER país
  de su lista de ubicaciones en Wikipedia (un conflicto puede abarcar varios); no es precisión
  cartográfica del punto exacto de combate.
- El predictor de producto tiene su propia disciplina de falsabilidad (misma rigurosidad de
  hipótesis que el pipeline principal) pero es una consulta bajo demanda, potencialmente
  repetible: por eso su track record se reporta siempre por separado, nunca mezclado con el
  del pipeline automático (ver sección del predictor arriba).
- Los datos de "sentimiento de fondos" son proxies de mercado (VIX, índices, oro, DXY), no
  datos de flujos de fondos reales de pago (EPFR/Bloomberg) — esa fuente requeriría tarjeta de
  crédito, incompatible con el objetivo del proyecto.
- Los análisis generados **no constituyen asesoramiento de inversión personalizado**; son un
  ejercicio de razonamiento macro estructurado y verificable, tal como se declara en el propio
  system prompt ([analysis/system_prompt.py](analysis/system_prompt.py)).

## Tests

```bash
pytest
```

Valida que los esquemas Pydantic aceptan un payload de análisis realista y que el JSON Schema
generado tiene la forma esperada para describírselo al LLM en `llm/client.py`.
