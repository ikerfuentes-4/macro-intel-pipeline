"use client";

import { useEffect, useState } from "react";
import { api, type ActiveConflict, type DashboardEvent } from "@/lib/api";
import MapView from "@/components/MapView";

export default function GeopoliticsPage() {
  const [conflicts, setConflicts] = useState<ActiveConflict[]>([]);
  const [events, setEvents] = useState<DashboardEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.conflicts(), api.events()])
      .then(([c, e]) => {
        setConflicts(c);
        setEvents(e);
      })
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-100">Geopolitics</h2>
        <div className="flex items-center gap-4 text-xs">
          <span className="flex items-center gap-1.5 text-slate-400">
            <span className="w-2.5 h-2.5 rounded-full bg-slate-600 border border-slate-500 inline-block" />
            Conflicto activo (registro, sin analizar)
          </span>
          <span className="flex items-center gap-1.5 text-slate-400">
            <span className="w-2.5 h-2.5 rounded-full bg-indigo-500 inline-block" />
            Analizado por IA
          </span>
        </div>
      </div>

      {error && <p className="text-sm text-rose-400">Error cargando datos: {error}</p>}

      <div className="h-[calc(100vh-220px)] min-h-[420px] rounded-lg overflow-hidden border border-slate-800">
        {loading ? (
          <div className="w-full h-full flex items-center justify-center text-slate-500 text-sm">Cargando mapa...</div>
        ) : (
          <MapView conflicts={conflicts} events={events} />
        )}
      </div>
    </div>
  );
}
