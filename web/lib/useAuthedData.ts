"use client";

// Hook compartido para las paginas que antes hacian SSR directo contra la API (Server
// Component + `await api.x()` en el propio render). Desde que api/server.py exige JWT en cada
// endpoint (Institutional Prompt, seccion 6), ese SSR ya no funciona: el proceso Node del
// servidor no tiene el token, que vive solo en localStorage del navegador (ver lib/auth.ts).
// Estas paginas pasan a ser Client Components que cargan sus datos en el navegador, igual que
// ya hacian geopolitics/predictor -- se sigue el patron ya existente, no se inventa uno nuevo.
import { useEffect, useState } from "react";

interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

export function useAuthedData<T>(loader: () => Promise<T>, deps: unknown[] = []): AsyncState<T> {
  const [state, setState] = useState<AsyncState<T>>({ data: null, loading: true, error: null });

  useEffect(() => {
    let cancelled = false;
    setState((s) => ({ ...s, loading: true, error: null }));
    loader()
      .then((data) => {
        if (!cancelled) setState({ data, loading: false, error: null });
      })
      .catch((err) => {
        if (!cancelled) setState({ data: null, loading: false, error: err instanceof Error ? err.message : String(err) });
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return state;
}
