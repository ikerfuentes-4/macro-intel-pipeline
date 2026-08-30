"use client";

import { api, type TrackRecordSummary } from "@/lib/api";
import { useAuthedData } from "@/lib/useAuthedData";

function SummaryBlock({ title, note, summary }: { title: string; note: string; summary: TrackRecordSummary }) {
  return (
    <div className="border border-slate-800 rounded-lg p-4 bg-slate-900/50">
      <h3 className="text-sm font-medium text-slate-200">{title}</h3>
      <p className="text-xs text-slate-500 mb-3">{note}</p>

      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-sm mb-3">
        <div>
          <p className="text-slate-500 text-xs">Cumplidas</p>
          <p className="text-emerald-400 text-lg">{summary.aciertos}</p>
        </div>
        <div>
          <p className="text-slate-500 text-xs">Fallidas</p>
          <p className="text-rose-400 text-lg">{summary.fallos}</p>
        </div>
        <div>
          <p className="text-slate-500 text-xs">Pendientes</p>
          <p className="text-amber-400 text-lg">{summary.pendientes}</p>
        </div>
        <div>
          <p className="text-slate-500 text-xs">Tasa acierto</p>
          <p className="text-slate-200 text-lg">
            {summary.tasa_acierto != null ? `${Math.round(summary.tasa_acierto * 100)}%` : "—"}
          </p>
        </div>
        <div>
          <p className="text-slate-500 text-xs">Brier score</p>
          <p className="text-slate-200 text-lg">{summary.brier_score_medio ?? "—"}</p>
        </div>
      </div>

      {summary.muestra_pequena && (
        <p className="text-xs text-amber-500/80 mb-3">
          Muestra pequena (&lt;{summary.muestra_minima_recomendada} predicciones resueltas): ninguna metrica de
          calibracion es estadisticamente fiable todavia -- se muestra igualmente por transparencia.
        </p>
      )}

      {summary.calibracion.length > 0 && (
        <table className="w-full text-xs">
          <thead>
            <tr className="text-slate-500 text-left border-b border-slate-800">
              <th className="pb-1 font-normal">Banda de probabilidad</th>
              <th className="pb-1 font-normal">N</th>
              <th className="pb-1 font-normal">Prob. media declarada</th>
              <th className="pb-1 font-normal">Tasa de acierto real</th>
            </tr>
          </thead>
          <tbody>
            {summary.calibracion.map((b) => (
              <tr key={b.banda} className="border-t border-slate-800/60">
                <td className="py-1.5 text-slate-300">{b.banda}</td>
                <td className="text-slate-400">{b.n}</td>
                <td className="text-slate-400">{Math.round(b.probabilidad_media * 100)}%</td>
                <td className="text-slate-400">{Math.round(b.tasa_acierto_real * 100)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

interface TrackRecordData {
  summary: TrackRecordSummary;
  productSummary: TrackRecordSummary;
}

export default function TrackRecordPage() {
  const { data, loading, error } = useAuthedData<TrackRecordData>(async () => {
    const [summary, productSummary] = await Promise.all([api.summary(), api.productSummary()]);
    return { summary, productSummary };
  });

  if (loading) return <p className="text-sm text-slate-500">Cargando track record…</p>;
  if (error) return <p className="text-sm text-rose-400">Error: {error}</p>;
  if (!data) return null;

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-slate-100">Track Record</h2>
      <p className="text-xs text-slate-500">
        Brier score y calibracion, no solo % de acierto -- la calibracion compara la probabilidad
        DECLARADA por el sistema contra la frecuencia REAL de acierto en esa banda.
      </p>

      <SummaryBlock
        title="Pipeline automatico"
        note="Analisis generados automaticamente sobre eventos ya contrastados por consenso cruzado."
        summary={data.summary}
      />
      <SummaryBlock
        title="Predictor de producto"
        note="Consultas bajo demanda del usuario -- track record SEPARADO a proposito, nunca mezclado con el de arriba."
        summary={data.productSummary}
      />
    </div>
  );
}
