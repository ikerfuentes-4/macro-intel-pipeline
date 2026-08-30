"""Flujo de revision humana (Institutional Prompt, Principio 8: 'la IA propone; una persona con
autoridad delegada dispone'). Toda `Prediction`/`ProductPrediction` nace en PENDING_REVIEW y NO
cuenta para el dashboard publico ni el track record hasta que un usuario con rol `reviewer` la
aprueba explicitamente -- ver `list_events_for_dashboard`/`track_record_summary`, que ahora
filtran por `review_status == 'APPROVED'`.
"""
from __future__ import annotations

import datetime as dt

from persistence.audit import record_audit_event
from persistence.db import Prediction, ProductPrediction, SessionLocal, init_db
from persistence.system_control import is_publishing_enabled
from utils.logging_conf import get_logger

logger = get_logger(__name__)

_MODEL_BY_KIND = {"pipeline": Prediction, "product": ProductPrediction}


def list_pending_review(kind: str) -> list[dict]:
    model = _MODEL_BY_KIND[kind]
    init_db()
    with SessionLocal() as db:
        rows = db.query(model).filter(model.review_status == "PENDING_REVIEW").order_by(model.id.desc()).all()
        return [{
            "id": r.id,
            "enunciado": r.enunciado,
            "ticker_validacion": r.ticker_validacion,
            "comparador": r.comparador,
            "valor_umbral": r.valor_umbral,
            "fecha_limite_revision": r.fecha_limite_revision,
            "probabilidad": r.probabilidad,
        } for r in rows]


def review_prediction(
    kind: str, prediction_id: int, decision: str, actor_email: str, note: str | None,
    actor_role: str = "reviewer",
) -> dict:
    """`decision`: 'APPROVED' o 'REJECTED'. Una aprobacion se bloquea si el kill switch esta
    activo (Institutional Prompt seccion 7) -- un rechazo SIEMPRE se permite, porque frenar
    publicacion nunca debe depender de que el kill switch este apagado."""
    if decision not in ("APPROVED", "REJECTED"):
        raise ValueError("decision debe ser 'APPROVED' o 'REJECTED'")

    if decision == "APPROVED" and not is_publishing_enabled():
        raise PermissionError(
            "El kill switch de publicacion de predicciones esta activo. "
            "Un admin debe desactivarlo antes de poder aprobar."
        )

    model = _MODEL_BY_KIND[kind]
    init_db()
    with SessionLocal() as db:
        row = db.get(model, prediction_id)
        if row is None:
            raise LookupError(f"{kind} #{prediction_id} no existe")
        if row.review_status != "PENDING_REVIEW":
            raise ValueError(f"{kind} #{prediction_id} ya fue revisada (estado actual: {row.review_status})")

        row.review_status = decision
        row.reviewed_by = actor_email
        row.reviewed_at = dt.datetime.utcnow()
        row.review_note = note
        db.commit()

    record_audit_event(
        actor_email=actor_email, actor_role=actor_role, action=f"prediction_{decision.lower()}",
        entity_type=kind, entity_id=str(prediction_id), details={"note": note},
    )
    logger.info("%s #%d: revision=%s por %s", kind, prediction_id, decision, actor_email)
    return {"id": prediction_id, "review_status": decision, "reviewed_by": actor_email}
