"use client";

import { useState } from "react";
import {
  api,
  type AuditVerification,
  type CircuitBreakerStatus,
  type KillSwitchStatus,
  type ModelCardEntry,
  type PendingReviewItem,
  type ReviewKind,
  type SystemRunEntry,
} from "@/lib/api";
import { getUser, hasRole } from "@/lib/auth";
import { useAuthedData } from "@/lib/useAuthedData";

const STATUS_COLOR: Record<string, string> = {
  SUCCESS: "text-emerald-400 border-emerald-500/30",
  FAILED: "text-rose-400 border-rose-500/30",
  RUNNING: "text-amber-400 border-amber-500/30",
};

const BREAKER_COLOR: Record<string, string> = {
  CLOSED: "text-emerald-400 border-emerald-500/30",
  HALF_OPEN: "text-amber-400 border-amber-500/30",
  OPEN: "text-rose-400 border-rose-500/30",
};

function KillSwitchPanel() {
  const user = getUser();
  const { data, loading, error } = useAuthedData<KillSwitchStatus>(() => api.killSwitchStatus());
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<KillSwitchStatus | null>(null);
  const current = status ?? data;

  const toggle = async () => {
    if (!current || busy) return;
    setBusy(true);
    try {
      const next = await api.setKillSwitch(
        !current.predictions_publishing_enabled,
        !current.predictions_publishing_enabled ? undefined : "Activado desde el panel de System"
      );
      setStatus(next);
    } catch (err) {
      alert(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <p className="text-sm text-slate-500">Cargando estado del kill switch…</p>;
  if (error) return <p className="text-sm text-rose-400">Error: {error}</p>;
  if (!current) return null;

  const active = !current.predictions_publishing_enabled;

  return (
    <div className={`border rounded-lg p-4 ${active ? "border-rose-500/40 bg-rose-500/5" : "border-slate-800 bg-slate-900/50"}`}>
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-medium text-slate-200">Kill switch de publicacion</h3>
          <p className="text-xs text-slate-500 mt-1">
            {active
              ? `Activo desde ${current.disabled_at ? new Date(current.disabled_at).toLocaleString("es-ES") : "—"} por ${current.disabled_by ?? "—"}${current.disabled_reason ? ` (${current.disabled_reason})` : ""}. Ningun analisis nuevo puede aprobarse mientras siga activo.`
              : "Publicacion de predicciones habilitada. Un admin puede pararla sin apagar el servicio."}
          </p>
        </div>
        {hasRole(user, "admin") ? (
          <button
            onClick={toggle}
            disabled={busy}
            className={`shrink-0 text-xs px-3 py-1.5 rounded-lg border transition-colors disabled:opacity-50 ${
              active
                ? "border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10"
                : "border-rose-500/40 text-rose-300 hover:bg-rose-500/10"
            }`}
          >
            {busy ? "…" : active ? "Desactivar" : "Activar kill switch"}
          </button>
        ) : (
          <span className={`shrink-0 text-xs px-2 py-0.5 rounded-full border ${active ? "text-rose-300 border-rose-500/30" : "text-emerald-300 border-emerald-500/30"}`}>
            {active ? "ACTIVO" : "OK"}
          </span>
        )}
      </div>
    </div>
  );
}

function CircuitBreakersPanel() {
  const { data, loading, error } = useAuthedData<CircuitBreakerStatus[]>(() => api.circuitBreakers());
  if (loading) return <p className="text-sm text-slate-500">Cargando circuit breakers…</p>;
  if (error) return <p className="text-sm text-rose-400">Error: {error}</p>;
  if (!data) return null;

  return (
    <div className="border border-slate-800 rounded-lg bg-slate-900/50 p-4">
      <h3 className="text-sm font-medium text-slate-200 mb-1">Circuit breakers (proveedores LLM)</h3>
      <p className="text-xs text-slate-500 mb-3">
        Se registran solo al primer uso de cada proveedor en este proceso -- lista vacia es normal si el pipeline
        no ha llamado a ningun LLM todavia.
      </p>
      {data.length === 0 ? (
        <p className="text-xs text-slate-500">Sin proveedores invocados todavia en este proceso.</p>
      ) : (
        <div className="space-y-2">
          {data.map((b) => (
            <div key={b.name} className="flex items-center justify-between text-sm">
              <span className="text-slate-300">{b.name}</span>
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-500">{b.consecutive_failures}/{b.failure_threshold} fallos</span>
                <span className={`text-xs px-2 py-0.5 rounded-full border ${BREAKER_COLOR[b.state] ?? ""}`}>{b.state}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ModelInventoryPanel() {
  const { data, loading, error } = useAuthedData<ModelCardEntry[]>(() => api.modelInventory());
  if (loading) return <p className="text-sm text-slate-500">Cargando inventario de modelos…</p>;
  if (error) return <p className="text-sm text-rose-400">Error: {error}</p>;
  if (!data) return null;

  return (
    <div className="border border-slate-800 rounded-lg bg-slate-900/50 p-4">
      <h3 className="text-sm font-medium text-slate-200 mb-1">Inventario de modelos (estilo SR 11-7)</h3>
      <p className="text-xs text-slate-500 mb-3">
        Cada agente de la cadena de razonamiento, con su version de prompt y su estado de validacion independiente
        -- ver persistence/model_inventory.py.
      </p>
      <div className="space-y-2">
        {data.map((m) => (
          <div key={m.name} className="border-t border-slate-800/60 pt-2 first:border-t-0 first:pt-0">
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm text-slate-300">{m.name}</span>
              <span
                className={`text-[10px] px-2 py-0.5 rounded-full border shrink-0 ${
                  m.governance_status === "VALIDATED"
                    ? "text-emerald-300 border-emerald-500/30"
                    : "text-amber-300 border-amber-500/30"
                }`}
              >
                {m.governance_status === "VALIDATED" ? "VALIDADO" : "PENDIENTE DE VALIDACION"}
              </span>
            </div>
            <p className="text-xs text-slate-500">{m.role_in_chain} &middot; version {m.version}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function AuditChainPanel() {
  const [result, setResult] = useState<AuditVerification | null>(null);
  const [busy, setBusy] = useState(false);
  const user = getUser();

  const verify = async () => {
    setBusy(true);
    try {
      setResult(await api.auditVerify());
    } catch (err) {
      alert(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  if (!hasRole(user, "admin")) return null;

  return (
    <div className="border border-slate-800 rounded-lg bg-slate-900/50 p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-medium text-slate-200">Cadena de auditoria</h3>
          <p className="text-xs text-slate-500 mt-1">
            Recalcula el hash de cada entrada del log y confirma que ninguna fue alterada retroactivamente.
          </p>
        </div>
        <button
          onClick={verify}
          disabled={busy}
          className="shrink-0 text-xs px-3 py-1.5 rounded-lg border border-slate-700 text-slate-300 hover:bg-slate-800 transition-colors disabled:opacity-50"
        >
          {busy ? "Verificando…" : "Verificar cadena"}
        </button>
      </div>
      {result && (
        <p className={`text-xs mt-3 ${result.valid ? "text-emerald-400" : "text-rose-400"}`}>
          {result.valid
            ? `Integra: ${result.entries_checked} entradas verificadas, sin alteraciones.`
            : `ALTERADA en el id ${result.broken_at_id}: ${result.reason}`}
        </p>
      )}
    </div>
  );
}

function ReviewQueue({ kind, title }: { kind: ReviewKind; title: string }) {
  const user = getUser();
  const { data, loading, error } = useAuthedData<PendingReviewItem[]>(() => api.pendingReview(kind), [kind]);
  const [items, setItems] = useState<PendingReviewItem[] | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const list = items ?? data;

  const decide = async (id: number, decision: "APPROVED" | "REJECTED") => {
    setBusyId(id);
    try {
      await api.reviewDecision(kind, id, decision);
      setItems((list ?? []).filter((i) => i.id !== id));
    } catch (err) {
      alert(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyId(null);
    }
  };

  if (!hasRole(user, "reviewer")) return null;
  if (loading) return <p className="text-sm text-slate-500">Cargando cola de revision ({title})…</p>;
  if (error) return <p className="text-sm text-rose-400">Error: {error}</p>;
  if (!list) return null;

  return (
    <div className="border border-slate-800 rounded-lg bg-slate-900/50 p-4">
      <h3 className="text-sm font-medium text-slate-200 mb-1">Revision pendiente &mdash; {title}</h3>
      <p className="text-xs text-slate-500 mb-3">
        La IA propone, una persona con rol reviewer o superior dispone -- nada de esto llega al dashboard publico
        hasta ser aprobado aqui.
      </p>
      {list.length === 0 ? (
        <p className="text-xs text-slate-500">Nada pendiente de revision.</p>
      ) : (
        <div className="space-y-2">
          {list.map((item) => (
            <div key={item.id} className="border border-slate-800 rounded-md p-3 text-sm">
              <p className="text-slate-300">{item.enunciado}</p>
              <p className="text-xs text-slate-500 mt-1">
                #{item.id} &middot; {item.ticker_validacion} {item.comparador} {item.valor_umbral} &middot; revision:{" "}
                {item.fecha_limite_revision}
                {item.probabilidad != null && ` · ${Math.round(item.probabilidad * 100)}% prob.`}
              </p>
              <div className="flex gap-2 mt-2">
                <button
                  onClick={() => decide(item.id, "APPROVED")}
                  disabled={busyId === item.id}
                  className="text-xs px-3 py-1 rounded-md border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10 disabled:opacity-50"
                >
                  Aprobar
                </button>
                <button
                  onClick={() => decide(item.id, "REJECTED")}
                  disabled={busyId === item.id}
                  className="text-xs px-3 py-1 rounded-md border border-rose-500/40 text-rose-300 hover:bg-rose-500/10 disabled:opacity-50"
                >
                  Rechazar
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function SystemRunsPanel() {
  const { data: runs, loading, error } = useAuthedData<SystemRunEntry[]>(() => api.systemRuns());
  if (loading) return <p className="text-sm text-slate-500">Cargando ejecuciones…</p>;
  if (error) return <p className="text-sm text-rose-400">Error: {error}</p>;
  if (!runs) return null;

  return (
    <div className="space-y-2">
      {runs.map((r) => {
        const style = STATUS_COLOR[r.status] ?? "text-slate-400 border-slate-700";
        return (
          <div key={r.id} className="border border-slate-800 rounded-lg p-3 bg-slate-900/50 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-slate-300">
                #{r.id} &middot; {r.run_type}
              </span>
              <span className={`text-xs px-2 py-0.5 rounded-full border ${style}`}>{r.status}</span>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              {new Date(r.started_at).toLocaleString("es-ES")} &middot; {r.records_processed} registros procesados
            </p>
            {r.errors.length > 0 && <p className="text-xs text-rose-400 mt-1">{r.errors.join(" · ")}</p>}
            {r.warnings.length > 0 && <p className="text-xs text-amber-400 mt-1">{r.warnings.join(" · ")}</p>}
          </div>
        );
      })}
      {runs.length === 0 && <p className="text-slate-500 text-sm">Sin ejecuciones registradas todavia.</p>}
    </div>
  );
}

export default function SystemPage() {
  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-lg font-semibold text-slate-100">System</h2>
        <p className="text-xs text-slate-500 mt-1">
          Gobierno del sistema: kill switch, salud de integraciones externas, inventario de modelos, revision
          humana y cadena de auditoria -- ver core/auth.py, persistence/audit.py, persistence/review.py.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <KillSwitchPanel />
        <CircuitBreakersPanel />
      </div>

      <ReviewQueue kind="pipeline" title="Pipeline automatico" />
      <ReviewQueue kind="product" title="Predictor de producto" />

      <div className="grid gap-4 md:grid-cols-2">
        <ModelInventoryPanel />
        <AuditChainPanel />
      </div>

      <section>
        <h3 className="text-sm font-medium text-slate-300 mb-3">Historial de ejecuciones</h3>
        <SystemRunsPanel />
      </section>
    </div>
  );
}
