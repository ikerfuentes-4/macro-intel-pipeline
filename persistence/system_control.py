"""Kill switch (Institutional Prompt, seccion 7): interruptor global que un `admin` puede
activar para detener la PUBLICACION de nuevas predicciones (aprobacion humana bloqueada) sin
tener que apagar el servicio completo -- distingue "el sistema deja de publicar" de "el sistema
deja de responder", que en un incidente real son decisiones distintas con distinto radio de
impacto.
"""
from __future__ import annotations

import datetime as dt

from persistence.db import SessionLocal, SystemControl, init_db
from utils.logging_conf import get_logger

logger = get_logger(__name__)


def _get_or_create_control(db) -> SystemControl:
    control = db.query(SystemControl).first()
    if control is None:
        control = SystemControl(predictions_publishing_enabled=True)
        db.add(control)
        db.commit()
        db.refresh(control)
    return control


def get_kill_switch_status() -> dict:
    init_db()
    with SessionLocal() as db:
        control = _get_or_create_control(db)
        return {
            "predictions_publishing_enabled": control.predictions_publishing_enabled,
            "disabled_by": control.disabled_by,
            "disabled_at": control.disabled_at.isoformat() if control.disabled_at else None,
            "disabled_reason": control.disabled_reason,
        }


def set_kill_switch(enabled: bool, actor_email: str, reason: str | None = None) -> dict:
    """`enabled=False` activa el kill switch (bloquea publicacion); `enabled=True` lo
    desactiva (restaura el funcionamiento normal)."""
    init_db()
    with SessionLocal() as db:
        control = _get_or_create_control(db)
        control.predictions_publishing_enabled = enabled
        control.disabled_by = None if enabled else actor_email
        control.disabled_at = None if enabled else dt.datetime.utcnow()
        control.disabled_reason = None if enabled else reason
        db.commit()
        logger.warning(
            "KILL SWITCH: publicacion de predicciones %s por %s%s",
            "HABILITADA" if enabled else "DESHABILITADA", actor_email,
            f" ({reason})" if reason else "",
        )
        return get_kill_switch_status()


def is_publishing_enabled() -> bool:
    return get_kill_switch_status()["predictions_publishing_enabled"]
