"use client";

import { api } from "@/lib/api";
import { useAuthedData } from "@/lib/useAuthedData";

const STATUS_STYLE: Record<string, string> = {
  PENDIENTE: "text-amber-400 border-amber-500/30",
  CUMPLIDA: "text-emerald-400 border-emerald-500/30",
  FALLIDA: "text-rose-400 border-rose-500/30",
  ERROR: "text-slate-400 border-slate-600/30",
};

export default function PredictionsPage() {
  const { data: events, loading, error } = useAuthedData(() => api.events());

  if (loading) return <p className="text-sm text-slate-500">Cargando predicciones…</p>;
  if (error) return <p className="text-sm text-rose-400">Error: {error}</p>;
  if (!events) return null;

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-slate-100">Predicciones del pipeline automatico</h2>
      <p className="text-xs text-slate-500">
        Cada prediccion tiene fecha limite fijada ANTES de conocerse el resultado -- no se pueden
        editar una vez creadas (inmutabilidad aplicada a nivel de base de datos, ver
        persistence/db.py).
      </p>

      <div className="space-y-3">
        {events.map((ev) => {
          const style = STATUS_STYLE[ev.prediccion_status ?? ""] ?? "text-slate-400 border-slate-700";
          return (
            <div key={ev.evento_id} className="border border-slate-800 rounded-lg p-4 bg-slate-900/50">
              <div className="flex items-start justify-between gap-3">
                <h3 className="text-sm font-medium text-slate-200">{ev.titular}</h3>
                <span className={`text-xs px-2 py-0.5 rounded-full border shrink-0 ${style}`}>
                  {ev.prediccion_status ?? "SIN EVALUAR"}
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-2">{ev.causa_raiz_geopolitica}</p>
              {ev.hipotesis_falsable && (
                <div className="mt-3 border-t border-slate-800 pt-3 text-xs text-slate-400">
                  <p className="text-slate-300">{ev.hipotesis_falsable.enunciado}</p>
                  <p className="mt-1">
                    Ticker <span className="text-slate-300">{ev.hipotesis_falsable.ticker_validacion}</span>{" "}
                    {ev.hipotesis_falsable.comparador}{" "}
                    <span className="text-slate-300">{ev.hipotesis_falsable.valor_umbral}</span> &middot; revision:{" "}
                    {ev.hipotesis_falsable.fecha_limite_revision}
                    {ev.prediccion_valor_real != null && (
                      <>
                        {" "}
                        &middot; valor real: <span className="text-slate-300">{ev.prediccion_valor_real}</span>
                      </>
                    )}
                  </p>
                </div>
              )}
              <p className="text-[11px] text-slate-600 mt-2">
                Confianza: {ev.nivel_confianza_analisis != null ? `${Math.round(ev.nivel_confianza_analisis * 100)}%` : "—"} &middot;{" "}
                {new Date(ev.created_at).toLocaleString("es-ES")}
              </p>
            </div>
          );
        })}
        {events.length === 0 && (
          <p className="text-slate-500 text-sm">
            Todavia no hay predicciones. Ejecuta <code className="text-emerald-400">python main.py run</code>.
          </p>
        )}
      </div>
    </div>
  );
}
