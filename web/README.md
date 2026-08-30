# Macro Intelligence Engine — Web (Next.js / TypeScript / MapLibre)

Segunda opción de frontend (Master Build Prompt, sección 4 y 17), consumiendo la MISMA API
FastAPI que ya usa el frontend estático de Fase 1 (`../frontend/index.html`) — cero cambios en
el backend Python.

## Ejecutar

```bash
cd macro-intel-pipeline
uvicorn api.server:app --reload --port 8000    # backend, en otra terminal
cd web
npm install
npm run dev -- --port 3005                     # http://localhost:3005
```

`next.config.ts` reescribe `/api/*` y `/reports/*` hacia `http://localhost:8000` (configurable
vía `API_BASE_URL`) — el navegador solo habla con el origen de Next.js, sin CORS.

## Páginas

| Ruta | Contenido |
|---|---|
| `/` | Overview: resumen de ambos track records + top países por `conflict_risk` |
| `/geopolitics` | Mapa interactivo (MapLibre GL + tiles CartoDB oscuros, gratuitos, sin API key) con conflictos activos y eventos analizados |
| `/predictions` | Predicciones del pipeline automático con su hipótesis falsable |
| `/predictor` | Predictor de producto: 4 bloques de datos reales + tesis de inversión + hipótesis falsable + descarga del Excel de 5 pestañas |
| `/track-record` | Brier score + calibración por bandas, pipeline y predictor por separado |
| `/system` | Trazabilidad de cada ejecución (`system_runs`) |

Con esto `web/` tiene paridad de funcionalidad completa con el frontend estático de Fase 1
(`../frontend/index.html`) más las vistas nuevas (Track Record con calibración, System). Pendiente
de esta iteración (no implementado, para no reclamar más de lo construido): pestañas
Macro/Energy/Markets/Sources dedicadas del dashboard completo de la sección 17 — hoy sus datos
ya están disponibles vía la API (`/api/events`, `/api/energy-risk`, etc.) pero sin una vista
propia en `web/`.

## Notas técnicas

- **MapLibre GL v6 no tiene export por defecto** (`import maplibregl from "maplibre-gl"` NO
  funciona en esta versión) — usa exports nombrados, ver `components/MapView.tsx`. Verificado
  contra los tipos instalados, no asumido.
- El estilo del mapa es un raster manual apuntando a los mismos tiles de CartoDB ya usados en
  el frontend Leaflet — MapLibre soporta fuentes raster nativamente, no hace falta una cuenta
  en MapTiler/Mapbox.
- `lib/api.ts` resuelve una URL absoluta (`API_BASE_URL`) cuando se ejecuta en el servidor
  (Server Components) y una ruta relativa cuando se ejecuta en el navegador — un `fetch()` con
  ruta relativa falla en Node.js (no hay "origen de página" implícito), solo funciona en el
  navegador.

## Verificado

`npx tsc --noEmit`, `npx eslint .` y `npm run build` pasan limpios. Las páginas Overview,
Predictions, Predictor, Track Record y System se probaron en vivo contra la API real (con datos
generados por el pipeline durante esta sesión) y renderizan correctamente — el predictor incluye
una consulta real end-to-end (4 bloques + LLM + Excel descargado y verificado con `fetch`). La
página `/geopolitics`
compila y sirve datos reales al mapa (confirmado por las peticiones de red), pero el renderizado
visual de los marcadores de MapLibre (basado en WebGL + `requestAnimationFrame`) no se pudo
confirmar visualmente en el entorno de esta sesión porque el panel de preview no compositaba
frames (mismo límite que afectó a las capturas de pantalla de Leaflet en una sesión anterior,
ver README principal) — el código sigue el mismo patrón ya validado del mapa Leaflet y debería
renderizar con normalidad en un navegador real.
