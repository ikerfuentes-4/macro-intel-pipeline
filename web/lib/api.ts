// Cliente tipado contra el backend FastAPI existente (api/server.py) -- cero cambios en el
// backend: Next.js reescribe /api/* y /reports/* hacia el (ver next.config.ts), asi que el
// navegador solo habla con el propio origen de Next.js (sin CORS).
//
// Todo endpoint de datos exige un JWT (Institutional Prompt, seccion 6) -- getJSON/postJSON
// adjuntan el Bearer token de lib/auth.ts en cada llamada, y si el backend devuelve 401 (sin
// token, token invalido o caducado) se limpia la sesion y se redirige a /login: no tiene sentido
// dejar la pagina en un estado a medio autenticar.

import { clearSession, getToken } from "@/lib/auth";

export interface GeoLocation {
  pais_o_region: string;
  latitud: number;
  longitud: number;
  nivel_geografico: string;
}

export interface RatePrediction {
  instrumento: string;
  direccion: "SUBIDA" | "BAJADA" | "MANTENER";
  probabilidad: number;
  horizonte_meses: number;
  justificacion: string;
}

export interface AssetReaction {
  clase_activo: string;
  veredicto: "GANADOR" | "PERDEDOR" | "NEUTRAL";
  magnitud_esperada: "BAJA" | "MEDIA" | "ALTA";
  racional: string;
}

export interface FalsifiableHypothesis {
  enunciado: string;
  ticker_validacion: string;
  comparador: string;
  valor_umbral: number;
  fecha_limite_revision: string;
  descripcion_metrica: string;
}

export interface DashboardEvent {
  evento_id: string;
  cluster_id: string;
  titular: string;
  fuentes_contrastadas: string[];
  diversidad_institucional: number;
  ubicacion: GeoLocation | null;
  causa_raiz_geopolitica: string;
  vectores_impacto: string[];
  prediccion_tipos_interes: RatePrediction | null;
  reacciones_activos: AssetReaction[];
  hipotesis_falsable: FalsifiableHypothesis | null;
  nivel_confianza_analisis: number | null;
  limitaciones_y_sesgos_potenciales: string;
  prediccion_status: string | null;
  prediccion_valor_real: number | null;
  created_at: string;
}

export interface ActiveConflict {
  id: number;
  nombre: string;
  continente: string;
  pais_principal: string;
  paises: string[];
  latitud: number;
  longitud: number;
  inicio_aproximado: string;
  muertes_acumuladas: number | null;
  muertes_recientes: number | null;
  fuente_url: string;
}

export interface CalibrationBand {
  banda: string;
  n: number;
  probabilidad_media: number;
  tasa_acierto_real: number;
}

export interface TrackRecordSummary {
  total_evaluadas: number;
  aciertos: number;
  fallos: number;
  pendientes: number;
  errores: number;
  tasa_acierto: number | null;
  brier_score_medio: number | null;
  calibracion: CalibrationBand[];
  predicciones_sin_probabilidad_registrada: number;
  muestra_pequena: boolean;
  muestra_minima_recomendada: number;
}

export interface RiskScoreEntry {
  pais: string;
  conflict_risk_score: number;
  etiqueta: string;
  num_conflictos_activos: number;
  muertes_recientes_totales: number;
  conflictos: string[];
  methodology_version: string;
}

export interface EnergyRiskEntry {
  pais: string;
  energy_risk_score: number;
  etiqueta: string;
  peso_energetico: number;
  conflict_risk_score_base: number;
  methodology_version: string;
}

export interface SystemRunEntry {
  id: number;
  run_type: string;
  started_at: string;
  finished_at: string | null;
  status: string;
  records_processed: number;
  errors: string[];
  warnings: string[];
}

export interface ProductForecast {
  producto: string;
  conflictos_considerados: string[];
  resumen_bancos_centrales: string;
  resumen_energia_suministro: string;
  resumen_sentimiento: string;
  tesis_inversion: string;
  direccion: "ALCISTA" | "BAJISTA" | "LATERAL";
  probabilidad: number;
  horizonte_meses: number;
  escenario_alternativo: string;
  hipotesis_falsable: FalsifiableHypothesis;
  nivel_confianza: number;
  limitaciones: string;
  report_url: string | null;
}

// `fetch("/api/x")` con ruta relativa solo funciona en el NAVEGADOR (se resuelve contra el
// origen de la pagina, y ahi si aplican las reescrituras de next.config.ts). En un Server
// Component, el fetch lo ejecuta el proceso Node.js del propio servidor Next.js -- ahi no hay
// "origen de pagina" implicito y una ruta relativa lanza `TypeError: Invalid URL`. Por eso se
// resuelve un origen absoluto solo quando se ejecuta en el servidor (typeof window === undefined).
const SERVER_API_BASE = process.env.API_BASE_URL || "http://localhost:8000";

function resolveUrl(path: string): string {
  return typeof window === "undefined" ? `${SERVER_API_BASE}${path}` : path;
}

// Un 401 en un Server Component (SSR, sin sesion de navegador que limpiar) simplemente se
// propaga como error normal -- solo en el navegador tiene sentido "cerrar sesion y mandar a
// /login", porque solo ahi existe la sesion de localStorage y una URL a la que redirigir.
function handleUnauthorized(): void {
  if (typeof window === "undefined") return;
  clearSession();
  if (window.location.pathname !== "/login") {
    window.location.href = "/login";
  }
}

async function getJSON<T>(path: string): Promise<T> {
  const url = resolveUrl(path);
  const token = getToken();
  const res = await fetch(url, {
    cache: "no-store",
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (res.status === 401) {
    handleUnauthorized();
  }
  if (!res.ok) {
    throw new Error(`${path}: HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

// El predictor tarda ~60-90s (4 bloques de datos reales + LLM) -- se llama SOLO desde el
// navegador (componente cliente), asi que no necesita la resolucion de URL de getJSON, pero se
// usa de todas formas por consistencia y por si algun dia se invoca desde un Server Action.
async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const url = resolveUrl(path);
  const token = getToken();
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });
  if (res.status === 401) {
    handleUnauthorized();
  }
  if (!res.ok) {
    const errBody = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(errBody.detail || `${path}: HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

// ============================== Gobierno institucional ==============================
// Tipos y llamadas contra las secciones nuevas de api/server.py: kill switch, circuit
// breakers, inventario de modelos (SR 11-7) y revision humana antes de publicar.

export interface KillSwitchStatus {
  predictions_publishing_enabled: boolean;
  disabled_by: string | null;
  disabled_at: string | null;
  disabled_reason: string | null;
}

export interface CircuitBreakerStatus {
  name: string;
  state: "CLOSED" | "OPEN" | "HALF_OPEN";
  consecutive_failures: number;
  failure_threshold: number;
}

export interface ModelCardEntry {
  name: string;
  role_in_chain: string;
  module_path: string;
  version: string;
  purpose: string;
  known_limitations: string;
  owner_email: string | null;
  last_independent_validation: string | null;
  validated_by: string | null;
  governance_status: "VALIDATED" | "AWAITING_INDEPENDENT_VALIDATION";
}

export interface AuditVerification {
  valid: boolean;
  entries_checked: number;
  broken_at_id: number | null;
  reason?: string;
}

export interface PendingReviewItem {
  id: number;
  enunciado: string;
  ticker_validacion: string;
  comparador: string;
  valor_umbral: number;
  fecha_limite_revision: string;
  probabilidad: number | null;
}

export type ReviewKind = "pipeline" | "product";

export const api = {
  events: () => getJSON<DashboardEvent[]>("/api/events"),
  summary: () => getJSON<TrackRecordSummary>("/api/summary"),
  conflicts: () => getJSON<ActiveConflict[]>("/api/conflicts"),
  productSummary: () => getJSON<TrackRecordSummary>("/api/product-summary"),
  riskScore: () => getJSON<RiskScoreEntry[]>("/api/risk-score"),
  energyRisk: () => getJSON<EnergyRiskEntry[]>("/api/energy-risk"),
  systemRuns: () => getJSON<SystemRunEntry[]>("/api/system-runs"),
  predictProduct: (producto: string) => postJSON<ProductForecast>("/api/predict", { producto }),

  killSwitchStatus: () => getJSON<KillSwitchStatus>("/api/system/kill-switch"),
  setKillSwitch: (enabled: boolean, reason?: string) =>
    postJSON<KillSwitchStatus>("/api/system/kill-switch", { enabled, reason }),
  circuitBreakers: () => getJSON<CircuitBreakerStatus[]>("/api/system/circuit-breakers"),
  modelInventory: () => getJSON<ModelCardEntry[]>("/api/model-inventory"),
  auditVerify: () => getJSON<AuditVerification>("/api/audit-log/verify"),
  pendingReview: (kind: ReviewKind) => getJSON<PendingReviewItem[]>(`/api/review/${kind}/pending`),
  reviewDecision: (kind: ReviewKind, id: number, decision: "APPROVED" | "REJECTED", note?: string) =>
    postJSON<{ id: number; review_status: string; reviewed_by: string }>(`/api/review/${kind}/${id}`, { decision, note }),
};
