"use client";

import { api, type ActiveConflict, type DashboardEvent, type RiskScoreEntry, type TrackRecordSummary } from "@/lib/api";
import StatCard from "@/components/StatCard";
import { useAuthedData } from "@/lib/useAuthedData";

interface OverviewData {
  summary: TrackRecordSummary;
  productSummary: TrackRecordSummary;
  risk: RiskScoreEntry[];
  events: DashboardEvent[];
  conflicts: ActiveConflict[];
}

async function loadOverview(): Promise<OverviewData> {
  const [summary, productSummary, risk, events, conflicts] = await Promise.all([
    api.summary(),
    api.productSummary(),
    api.riskScore(),
    api.events(),
    api.conflicts(),
  ]);
  return { summary, productSummary, risk, events, conflicts };
}

export default function OverviewPage() {
  const { data, loading, error } = useAuthedData(loadOverview);

  if (loading) return <p className="text-sm text-slate-500">Cargando resumen…</p>;
  if (error) return <p className="text-sm text-rose-400">Error: {error}</p>;
  if (!data) return null;

  const { summary, productSummary, risk, events, conflicts } = data;

  return (
    <div className="space-y-8">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Pipeline automatico"
          value={`${summary.aciertos}/${summary.total_evaluadas}`}
          sub="cumplidas / evaluadas"
          accent="emerald"
        />
        <StatCard
          title="Predictor de producto"
          value={`${productSummary.aciertos}/${productSummary.total_evaluadas}`}
          sub="cumplidas / evaluadas (track record separado)"
          accent="amber"
        />
        <StatCard title="Eventos analizados por IA" value={String(events.length)} sub="cadena de 8 agentes" />
        <StatCard title="Conflictos activos registrados" value={String(conflicts.length)} sub="Wikipedia, sincronizado" />
      </div>

      <section>
        <h2 className="text-sm font-medium text-slate-300 mb-3">Top riesgo de conflicto (conflict_risk)</h2>
        <p className="text-xs text-slate-500 mb-3">
          Formula 100% deterministica, sin LLM &mdash; ver metodologia documentada en docs/risk_score_methodology.md.
        </p>
        <div className="border border-slate-800 rounded-lg divide-y divide-slate-800/60">
          {risk.slice(0, 10).map((r) => (
            <div key={r.pais} className="flex items-center justify-between text-sm px-4 py-2">
              <span className="text-slate-300">{r.pais}</span>
              <div className="flex items-center gap-3">
                <span className="text-xs text-slate-500">{r.num_conflictos_activos} conflictos</span>
                <span className="text-slate-400 tabular-nums">{r.conflict_risk_score}</span>
                <span className="text-xs px-2 py-0.5 rounded-full border border-slate-700 text-slate-400">{r.etiqueta}</span>
              </div>
            </div>
          ))}
          {risk.length === 0 && <p className="px-4 py-3 text-sm text-slate-500">Sin datos todavia.</p>}
        </div>
      </section>
    </div>
  );
}
