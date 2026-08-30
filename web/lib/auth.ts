// Sesion minima pero real (Institutional Prompt, seccion 6): el backend exige un JWT en TODO
// endpoint de datos desde api/server.py, asi que este frontend necesita login + Bearer token,
// no una capa cosmetica. Guardado en localStorage a proposito: es un panel interno de uso desde
// un solo navegador por analista, no una app publica que necesite cookies httpOnly reforzadas
// contra XSS de terceros -- si esto se expone alguna vez a internet publica, mover el token a una
// cookie httpOnly firmada por un backend-for-frontend es el siguiente paso obligado.

const TOKEN_KEY = "mie_token";
const USER_KEY = "mie_user";

export interface SessionUser {
  email: string;
  role: "viewer" | "analyst" | "reviewer" | "admin";
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function getUser(): SessionUser | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as SessionUser;
  } catch {
    return null;
  }
}

export function setSession(token: string, user: SessionUser): void {
  window.localStorage.setItem(TOKEN_KEY, token);
  window.localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession(): void {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(USER_KEY);
}

// Jerarquia identica a ROLE_HIERARCHY en core/auth.py -- se duplica aqui a proposito (una
// constante compartida via paquete requeriria un monorepo real) SOLO para decidir que mostrar
// en la UI; la autorizacion de verdad la sigue haciendo el backend en cada request, esto nunca
// es la barrera de seguridad.
const ROLE_HIERARCHY = ["viewer", "analyst", "reviewer", "admin"] as const;

export function hasRole(user: SessionUser | null, minimum: SessionUser["role"]): boolean {
  if (!user) return false;
  return ROLE_HIERARCHY.indexOf(user.role) >= ROLE_HIERARCHY.indexOf(minimum);
}
