"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { clearSession, getToken, getUser, type SessionUser } from "@/lib/auth";

// Gate de sesion minimo pero real: si no hay token, todo excepto /login redirige alli. No
// intenta ser un sistema de permisos por pagina (eso lo aplica cada endpoint via require_role
// en api/server.py) -- esto solo evita que se vea una pantalla rota llena de errores 401 antes
// de que el usuario haya iniciado sesion.
export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);
  const [user, setUser] = useState<SessionUser | null>(null);

  useEffect(() => {
    const token = getToken();
    if (!token && pathname !== "/login") {
      router.replace("/login");
      return;
    }
    setUser(getUser());
    setReady(true);
  }, [pathname, router]);

  if (pathname === "/login") return <>{children}</>;
  if (!ready) return null;

  return (
    <>
      <div className="border-b border-slate-800 bg-slate-900/40">
        <div className="max-w-7xl mx-auto px-4 py-1.5 flex items-center justify-end gap-3 text-xs text-slate-500">
          {user && (
            <>
              <span>
                {user.email} &middot; <span className="text-slate-400 uppercase">{user.role}</span>
              </span>
              <button
                onClick={() => {
                  clearSession();
                  router.replace("/login");
                }}
                className="text-slate-500 hover:text-slate-300 underline underline-offset-2"
              >
                Cerrar sesion
              </button>
            </>
          )}
        </div>
      </div>
      {children}
    </>
  );
}
