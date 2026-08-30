"""Log de auditoria con integridad criptografica (Institutional Prompt, Principio 10 y seccion
24). Cada entrada encadena el hash de la anterior: alterar o borrar una fila antigua deja
`entry_hash` de todas las filas posteriores sin corresponder al recalculo, algo que
`verify_audit_chain()` detecta. Esto es lo que separa un log de auditoria (registro legal) de
un log de depuracion (informativo): aqui la propiedad que importa es "esto no se puede
manipular sin que se note", no solo "esto quedo escrito".
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json

from persistence.db import AuditLog, SessionLocal, init_db
from utils.logging_conf import get_logger

logger = get_logger(__name__)

GENESIS_HASH = "0" * 64  # hash "anterior" de la primera entrada de la cadena


def _compute_entry_hash(
    prev_hash: str, actor_email: str, actor_role: str, action: str,
    entity_type: str, entity_id: str, details_json: str, created_at_iso: str,
) -> str:
    payload = "|".join([prev_hash, actor_email, actor_role, action, entity_type, entity_id, details_json, created_at_iso])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def record_audit_event(
    actor_email: str, actor_role: str, action: str,
    entity_type: str, entity_id: str, details: dict | None = None,
) -> None:
    """Anade una entrada a la cadena de auditoria. Se llama tras cada accion sensible: login,
    aprobacion/rechazo de una prediccion, cambio del kill switch, edicion de un model card."""
    init_db()
    details_json = json.dumps(details or {}, ensure_ascii=False, sort_keys=True)

    with SessionLocal() as db:
        last = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
        prev_hash = last.entry_hash if last else GENESIS_HASH

        now = dt.datetime.utcnow()
        created_at_iso = now.isoformat()
        entry_hash = _compute_entry_hash(
            prev_hash, actor_email, actor_role, action, entity_type, entity_id, details_json, created_at_iso,
        )

        db.add(AuditLog(
            actor_email=actor_email,
            actor_role=actor_role,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            details_json=details_json,
            prev_hash=prev_hash,
            entry_hash=entry_hash,
            created_at=now,
        ))
        db.commit()

    logger.info("audit: %s %s %s#%s por %s (%s)", action, entity_type, entity_type, entity_id, actor_email, actor_role)


def list_audit_log(limit: int = 100) -> list[dict]:
    with SessionLocal() as db:
        rows = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(limit).all()
        return [{
            "id": r.id,
            "actor_email": r.actor_email,
            "actor_role": r.actor_role,
            "action": r.action,
            "entity_type": r.entity_type,
            "entity_id": r.entity_id,
            "details": json.loads(r.details_json),
            "created_at": r.created_at.isoformat(),
        } for r in rows]


def verify_audit_chain() -> dict:
    """Recorre TODA la cadena de auditoria y recalcula cada `entry_hash` a partir del
    `prev_hash` y el contenido de la fila. Si alguna fila fue alterada o borrada tras el hecho,
    el recalculo no coincide y se reporta el punto exacto de la rotura -- esto es lo que hace
    el log 'verificable', no solo 'guardado'."""
    with SessionLocal() as db:
        rows = db.query(AuditLog).order_by(AuditLog.id.asc()).all()

    if not rows:
        return {"valid": True, "entries_checked": 0, "broken_at_id": None}

    expected_prev = GENESIS_HASH
    for row in rows:
        if row.prev_hash != expected_prev:
            return {"valid": False, "entries_checked": row.id, "broken_at_id": row.id, "reason": "prev_hash no coincide con la entrada anterior"}
        recomputed = _compute_entry_hash(
            row.prev_hash, row.actor_email, row.actor_role, row.action,
            row.entity_type, row.entity_id, row.details_json, row.created_at.isoformat(),
        )
        if recomputed != row.entry_hash:
            return {"valid": False, "entries_checked": row.id, "broken_at_id": row.id, "reason": "entry_hash no coincide con el contenido de la fila"}
        expected_prev = row.entry_hash

    return {"valid": True, "entries_checked": len(rows), "broken_at_id": None}
