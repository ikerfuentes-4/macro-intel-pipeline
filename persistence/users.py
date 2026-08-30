"""Gestion de usuarios (Institutional Prompt, seccion 6). Sin panel de auto-registro: crear un
usuario es una accion de `admin`, igual que en cualquier sistema con control de acceso real.
"""
from __future__ import annotations

from core.auth import hash_password
from persistence.db import SessionLocal, User, init_db
from utils.logging_conf import get_logger

logger = get_logger(__name__)


def create_user(email: str, password: str, role: str = "viewer") -> int:
    init_db()
    with SessionLocal() as db:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            raise ValueError(f"Ya existe un usuario con el email {email!r}.")
        user = User(email=email, hashed_password=hash_password(password), role=role)
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info("Usuario creado: %s (rol=%s)", email, role)
        return user.id


def list_users() -> list[dict]:
    with SessionLocal() as db:
        rows = db.query(User).order_by(User.created_at).all()
        return [{
            "id": r.id, "email": r.email, "role": r.role, "is_active": r.is_active,
            "created_at": r.created_at.isoformat(),
            "last_login_at": r.last_login_at.isoformat() if r.last_login_at else None,
        } for r in rows]


def bootstrap_admin_if_empty(email: str, password: str) -> bool:
    """Crea el primer usuario admin SOLO si la tabla `users` esta vacia -- evita que se pueda
    crear un segundo admin por esta via una vez el sistema ya tiene usuarios reales (a partir
    de ahi, la gestion de usuarios pasa a requerir un admin autenticado)."""
    init_db()
    with SessionLocal() as db:
        if db.query(User).count() > 0:
            return False
    create_user(email, password, role="admin")
    return True
