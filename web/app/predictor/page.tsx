"use client";

import { useEffect, useState } from "react";
import { api, type ProductForecast, type TrackRecordSummary } from "@/lib/api";
import Chip from "@/components/Chip";

const DIRECTION_ARROW: Record<string, string> = { ALCISTA: "▲", BAJISTA: "▼", LATERAL: "►" };
const DIRECTION_COLOR: Record<string, string> = {
  ALCISTA: "text-emerald-400",
  BAJISTA: "text-rose-400",
  LATERAL: "text-amber-400",
};

function pct(x: number | null | undefined): string {
  return x == null ? "—" : `${Math.round(x * 100)}%`;
}

export default function PredictorPage() {
  const [producto, setProducto] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ProductForecast | null>(null);
  const [productSummary, setProductSummary] = useState<TrackRecordSummary | null>(null);

  const loadProductSummary = () => {
    api.productSummary().then(setProductSummary).catch(() => {});
  };

  useEffect(() => {
    loadProductSummary();
  }, []);

  const submit = async () => {
    const value = producto.trim();
    if (!value || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const forecast = await api.predictProduct(value);
      setResult(forecast);
      loadProductSummary();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-5">
      <h2 className="text-lg font-semibold text-slate-100">Predictor de producto</h2>

      <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-xs text-amber-300">
        Herramienta exploratoria bajo demanda: cruza en tiempo real 4 bloques de datos reales
        (conflictos, bancos centrales, energia/suministro, sentimiento). Su hipotesis falsable se
        guarda en <strong>un track record separado</strong> del pipeline automatico (
        {productSummary && productSummary.total_evaluadas > 0
          ? `${productSummary.aciertos} cumplidas / ${productSummary.fallos} fallidas`
          : "aun sin hipotesis evaluadas"}
        ) — nunca se mezclan.
      </div>

      <div>
        <label className="block text-xs uppercase tracking-wide text-slate-500 mb-1">Producto financiero</label>
        <div className="flex gap-2">
          <input
            type="text"
            value={producto}
            onChange={(e) => setProducto(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
            placeholder="ej. Oro (GC=F), EUR/USD, Petroleo WTI, Bonos EEUU 10 anos, Nikkei 225…"
            className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-indigo-500"
          />
          <button
            onClick={submit}
            disabled={loading}
            className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium text-white transition-colors"
          >
            {loading ? "Analizando…" : "Analizar"}
          </button>
        </div>
      </div>

      {loading && <p className="text-sm text-slate-500">Generando prediccion (4 bloques de datos + LLM, ~60-90s)…</p>}
      {error && <p className="text-sm text-rose-400">Error: {error}</p>}

      {result && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-5 space-y-4">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-lg font-semibold text-slate-100">{result.producto}</h3>
            <span className={`text-base font-medium ${DIRECTION_COLOR[result.direccion] ?? ""}`}>
              {DIRECTION_ARROW[result.direccion] ?? ""} {result.direccion}
            </span>
          </div>

          {result.report_url && (
            <a
              href={result.report_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 text-xs px-3 py-1.5 rounded-lg bg-emerald-600/20 text-emerald-300 border border-emerald-600/40 hover:bg-emerald-600/30 transition-colors"
            >
              📊 Descargar informe Excel (5 pestanas)
            </a>
          )}

          <div className="rounded-lg border border-indigo-500/30 bg-indigo-500/10 p-3">
            <p className="text-[11px] uppercase tracking-wide text-indigo-300 mb-1">
              Tesis de inversion (cruce de los 4 bloques)
            </p>
            <p className="text-sm text-slate-200">{result.tesis_inversion}</p>
          </div>

          <div>
            <p className="text-[11px] uppercase tracking-wide text-slate-500 mb-1">Conflictos considerados</p>
            <div>
              {result.conflictos_considerados.length > 0 ? (
                result.conflictos_considerados.map((c) => (
                  <Chip key={c} tone="indigo">
                    {c}
                  </Chip>
                ))
              ) : (
                <span className="text-xs text-slate-500">Ninguno directamente relevante</span>
              )}
            </div>
          </div>

          <div className="text-sm text-slate-400">
            <span className="text-slate-200 font-medium">{pct(result.probabilidad)}</span> de probabilidad &middot;
            horizonte {result.horizonte_meses} meses
          </div>

          <div className="grid gap-2">
            <div className="border border-slate-800 rounded-md p-2">
              <p className="text-[10px] uppercase tracking-wide text-slate-500">Bancos centrales</p>
              <p className="text-xs text-slate-400">{result.resumen_bancos_centrales}</p>
            </div>
            <div className="border border-slate-800 rounded-md p-2">
              <p className="text-[10px] uppercase tracking-wide text-slate-500">Energia / suministro</p>
              <p className="text-xs text-slate-400">{result.resumen_energia_suministro}</p>
            </div>
            <div className="border border-slate-800 rounded-md p-2">
              <p className="text-[10px] uppercase tracking-wide text-slate-500">Sentimiento de mercado</p>
              <p className="text-xs text-slate-400">{result.resumen_sentimiento}</p>
            </div>
          </div>

          <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
            <p className="text-[11px] uppercase tracking-wide text-slate-500 mb-1">Escenario alternativo</p>
            <p className="text-xs text-slate-400">{result.escenario_alternativo}</p>
          </div>

          <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3">
            <p className="text-[11px] uppercase tracking-wide text-slate-500 mb-1">
              Hipotesis falsable (track record del predictor)
            </p>
            <p className="text-slate-300 text-sm">{result.hipotesis_falsable.enunciado}</p>
            <p className="text-xs text-slate-500 mt-1">
              Ticker <span className="text-slate-300">{result.hipotesis_falsable.ticker_validacion}</span>{" "}
              {result.hipotesis_falsable.comparador}{" "}
              <span className="text-slate-300">{result.hipotesis_falsable.valor_umbral}</span> &middot; revision:{" "}
              {result.hipotesis_falsable.fecha_limite_revision}
            </p>
          </div>

          <div>
            <p className="text-[11px] uppercase tracking-wide text-slate-500 mb-1">
              Confianza: {pct(result.nivel_confianza)}
            </p>
            <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
              <div className="h-full bg-indigo-500" style={{ width: `${(result.nivel_confianza || 0) * 100}%` }} />
            </div>
          </div>

          <p className="text-xs text-slate-500 italic">{result.limitaciones}</p>
        </div>
      )}
    </div>
  );
}
