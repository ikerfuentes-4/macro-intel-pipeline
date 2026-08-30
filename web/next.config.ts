import type { NextConfig } from "next";

// El backend FastAPI (api/server.py) sigue siendo la unica fuente de datos -- cero cambios
// alli. Estas reescrituras hacen que el navegador solo hable con el origen de Next.js (evita
// CORS por completo) mientras Next.js reenvia la peticion al backend en el servidor.
const API_BASE_URL = process.env.API_BASE_URL || "http://localhost:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${API_BASE_URL}/api/:path*` },
      { source: "/reports/:path*", destination: `${API_BASE_URL}/reports/:path*` },
    ];
  },
};

export default nextConfig;
