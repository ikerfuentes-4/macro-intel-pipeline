"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { setSession, type SessionUser } from "@/lib/auth";

// Login "minimo pero real" (Institutional Prompt, seccion 6): habla directo con
// /api/auth/login en vez de pasar por lib/api.ts a proposito -- ese cliente ya asume que hay
// un token que adjuntar, y aqui todavia no lo hay.
export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (loading || !email.trim() || !password) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), password }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(body.detail || `Error HTTP ${res.status}`);
      }
      const user: SessionUser = { email: body.email, role: body.role };
      setSession(body.access_token, user);
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-sm mx-auto mt-16 space-y-6">
      <div className="text-center space-y-1">
        <h1 className="text-lg font-semibold text-slate-100">Macro Intelligence Engine</h1>
        <p className="text-xs text-slate-500">Acceso restringido &mdash; toda accion queda registrada en el log de auditoria.</p>
      </div>

      <div className="border border-slate-800 rounded-xl bg-slate-900/50 p-5 space-y-4">
        <div>
          <label className="block text-xs uppercase tracking-wide text-slate-500 mb-1">Email</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
            autoFocus
            className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-indigo-500"
            placeholder="tu@empresa.com"
          />
        </div>
        <div>
          <label className="block text-xs uppercase tracking-wide text-slate-500 mb-1">Contrasena</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
            className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
          />
        </div>

        {error && <p className="text-xs text-rose-400">{error}</p>}

        <button
          onClick={submit}
          disabled={loading}
          className="w-full px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium text-white transition-colors"
        >
          {loading ? "Verificando…" : "Entrar"}
        </button>
      </div>

      <p className="text-center text-xs text-slate-600">
        No hay cuenta? Pide a un administrador que la cree con{" "}
        <code className="text-slate-500">python main.py create-admin</code> o{" "}
        <code className="text-slate-500">persistence.users.create_user</code>.
      </p>
    </div>
  );
}
