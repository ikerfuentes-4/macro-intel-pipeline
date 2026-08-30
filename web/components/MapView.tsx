"use client";

import { useEffect, useRef } from "react";
// maplibre-gl v6 ya no tiene export por defecto -- exports nombrados (verificado contra los
// tipos instalados, no asumido desde memoria de entrenamiento).
import { Map as MapLibreMap, Marker, NavigationControl, Popup, type StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { ActiveConflict, DashboardEvent } from "@/lib/api";

// Estilo raster minimo apuntando a los tiles oscuros de CartoDB (gratuitos, sin API key,
// mismos tiles ya validados en el frontend estatico con Leaflet -- MapLibre soporta fuentes
// raster nativamente, no hace falta un estilo vectorial ni una cuenta en MapTiler/Mapbox).
const CARTO_DARK_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    "carto-dark": {
      type: "raster" as const,
      tiles: [
        "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        "https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        "https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
      ],
      tileSize: 256,
      attribution: "&copy; OpenStreetMap contributors &copy; CARTO",
    },
  },
  layers: [{ id: "carto-dark-layer", type: "raster" as const, source: "carto-dark" }],
};

const STATUS_COLOR: Record<string, string> = {
  PENDIENTE: "#f59e0b",
  CUMPLIDA: "#10b981",
  FALLIDA: "#f43f5e",
  ERROR: "#64748b",
};

export default function MapView({
  conflicts,
  events,
}: {
  conflicts: ActiveConflict[];
  events: DashboardEvent[];
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markersRef = useRef<Marker[]>([]);

  // Inicializa el mapa una sola vez.
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = new MapLibreMap({
      container: containerRef.current,
      style: CARTO_DARK_STYLE,
      center: [10, 20],
      zoom: 1.4,
    });
    map.addControl(new NavigationControl(), "top-right");
    map.on("error", (e) => console.error("MapLibre error:", e.error?.message ?? e.error));
    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Redibuja los marcadores cuando cambian los datos.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const draw = () => {
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];

      // Capa base: TODOS los conflictos activos registrados (puntos neutros, sin analisis IA)
      conflicts.forEach((c) => {
        const el = document.createElement("div");
        el.style.cssText =
          "width:10px;height:10px;border-radius:50%;background:#334155;border:1.5px solid #64748b;cursor:pointer;";
        const marker = new Marker({ element: el })
          .setLngLat([c.longitud, c.latitud])
          .setPopup(
            new Popup({ offset: 12 }).setHTML(
              `<div style="font-size:12px"><strong>${c.nombre}</strong><br/>${c.pais_principal} &middot; desde ${c.inicio_aproximado}<br/><span style="opacity:0.7">CONFLICTO ACTIVO &middot; sin analizar por IA</span></div>`,
            ),
          )
          .addTo(map);
        markersRef.current.push(marker);
      });

      // Capa destacada: eventos ya analizados por el pipeline de 8 agentes.
      events.forEach((ev) => {
        if (!ev.ubicacion) return;
        const color = STATUS_COLOR[ev.prediccion_status ?? ""] ?? "#64748b";
        const el = document.createElement("div");
        el.style.cssText = `width:16px;height:16px;border-radius:50%;background:${color};opacity:0.8;border:2px solid ${color};cursor:pointer;`;
        const marker = new Marker({ element: el })
          .setLngLat([ev.ubicacion.longitud, ev.ubicacion.latitud])
          .setPopup(
            new Popup({ offset: 14, maxWidth: "280px" }).setHTML(
              `<div style="font-size:12px"><strong style="color:#818cf8">ANALIZADO POR IA</strong><br/>${ev.titular}<br/><span style="opacity:0.7">${ev.causa_raiz_geopolitica}</span></div>`,
            ),
          )
          .addTo(map);
        markersRef.current.push(marker);
      });
    };

    if (map.isStyleLoaded()) {
      draw();
    } else {
      map.once("load", draw);
    }

    return () => {
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];
    };
  }, [conflicts, events]);

  return <div ref={containerRef} className="w-full h-full" />;
}
