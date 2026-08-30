"""Autenticacion y RBAC (Institutional Prompt, seccion 6: 'ningun endpoint accesible sin
sesion autenticada, ni siquiera de solo lectura').

JWT auto-emitido con secreto compartido HS256 -- suficiente para un despliegue de una sola
instancia, y explicitamente NO es SSO corporativo real. La validacion del token esta aislada en
`decode_token()` a proposito: para conectar un IdP real (Okta/Azure AD/cualquier proveedor
OIDC), esa es la UNICA funcion que hay que sustituir -por validar la firma contra el JWKS del
IdP en vez de un secreto compartido-, sin tocar `require_role`, los endpoints, ni el frontend
(que ya trabaja con un Bearer token generico). Eso es lo que significa "SSO-ready" aqui: la
superficie de integracion esta acotada a un unico punto, no que ya este conectado a un
proveedor real -- ninguno existe en este entorno.
"""
from __future__ import annotations

import datetime as dt

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import settings
from persistence.db import SessionLocal, User

# Jerarquia de roles: cada uno hereda los permisos de los anteriores (Institutional Prompt,
# seccion 6). `require_role("analyst")` deja pasar a analyst/reviewer/admin, no solo a analyst.
ROLE_HIERARCHY = ["viewer", "analyst", "reviewer", "admin"]

_security = HTTPBearer(auto_error=False)

# bcrypt trunca en 72 bytes; se recorta explicitamente en vez de dejar que la libreria falle
# con contrasenas largas (ValueError silencioso de otro modo confuso para quien la usa).
_MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8")[:_MAX_PASSWORD_BYTES], bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:_MAX_PASSWORD_BYTES], hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user: User) -> str:
    now = dt.datetime.utcnow()
    payload = {
        "sub": user.email,
        "role": user.role,
        "iat": now,
        "exp": now + dt.timedelta(hours=settings.jwt_expiry_hours),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    """Punto de sustitucion unico para SSO real (ver docstring del modulo)."""
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado. Vuelve a iniciar sesion.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token invalido.")


class CurrentUser:
    __slots__ = ("email", "role")

    def __init__(self, email: str, role: str):
        self.email = email
        self.role = role


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_security),
) -> CurrentUser:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="No autenticado. Incluye la cabecera 'Authorization: Bearer <token>'.",
        )
    payload = decode_token(credentials.credentials)
    return CurrentUser(email=payload["sub"], role=payload.get("role", "viewer"))


def require_role(minimum_role: str):
    """Dependency factory de FastAPI: exige rol >= `minimum_role` en ROLE_HIERARCHY.
    Uso: `@app.post(...); def f(user: CurrentUser = Depends(require_role("reviewer"))): ...`"""
    if minimum_role not in ROLE_HIERARCHY:
        raise ValueError(f"Rol desconocido: {minimum_role!r}")
    min_index = ROLE_HIERARCHY.index(minimum_role)

    def _check(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        try:
            user_index = ROLE_HIERARCHY.index(user.role)
        except ValueError:
            user_index = -1
        if user_index < min_index:
            raise HTTPException(
                status_code=403,
                detail=f"Esta accion requiere el rol '{minimum_role}' o superior (tu rol es '{user.role}').",
            )
        return user

    return _check


def authenticate_user(email: str, password: str) -> User | None:
    """Verifica credenciales contra la tabla `users`. Devuelve None tanto si el usuario no
    existe como si la contrasena es incorrecta -- nunca revela cual de los dos fue (evita
    enumeracion de usuarios validos)."""
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).first()
        if user is None or not user.is_active:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        user.last_login_at = dt.datetime.utcnow()
        db.commit()
        db.refresh(user)
        return user
