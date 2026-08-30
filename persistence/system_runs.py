"""Context manager para envolver cada ejecucion del sistema con trazabilidad (Master Build
Prompt, seccion 19 "AUTOMATION" y seccion 23 "OBSERVABILITY"): run_id, started_at, finished_at,
status, records_processed, errors, warnings -- todo registrado en `SystemRun` (ver
persistence/db.py), no solo en logs de consola que se pierden entre ejecuciones.
"""
from __future__ import annotations

import datetime as dt
import json
from contextlib import contextmanager
from dataclasses import dataclass, field

from persistence.db import SessionLocal, SystemRun, init_db
from utils.logging_conf import get_logger

logger = get_logger(__name__)


def list_recent_system_runs(limit: int = 30) -> list[dict]:
    """Para la pestana 'System' del dashboard (Master Build Prompt, seccion 17): estado de
    pipelines, errores y ultima actualizacion, ya persistido en vez de solo en logs de consola."""
    with SessionLocal() as db:
        rows = (
            db.query(SystemRun)
            .order_by(SystemRun.started_at.desc())
            .limit(limit)
            .all()
        )
        return [{
            "id": r.id,
            "run_type": r.run_type,
            "started_at": r.started_at.isoformat(),
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "status": r.status,
            "records_processed": r.records_processed,
            "errors": json.loads(r.errors_json),
            "warnings": json.loads(r.warnings_json),
        } for r in rows]


@dataclass
class RunRecorder:
    """Handle mutable que se pasa al bloque `with` para que el codigo del run reporte
    progreso/errores sin tener que gestionar la sesion de base de datos el mismo."""

    records_processed: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        self.errors.append(message)
        logger.error(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)
        logger.warning(message)

    def set_records_processed(self, n: int) -> None:
        self.records_processed = n


@contextmanager
def track_system_run(run_type: str):
    """Uso:

        with track_system_run("pipeline_run") as run:
            ... trabajo ...
            run.set_records_processed(42)
            run.add_warning("feed X sin resultados")

    Si el bloque lanza una excepcion, el run se marca FAILED (con la excepcion en `errors`) y
    la excepcion se re-lanza -- este wrapper nunca oculta un fallo silenciosamente (Principio 4)."""
    init_db()
    recorder = RunRecorder()
    with SessionLocal() as db:
        run = SystemRun(run_type=run_type, status="RUNNING")
        db.add(run)
        db.commit()
        db.refresh(run)
        run_id = run.id

    logger.info("system_run #%d (%s) iniciado", run_id, run_type)

    try:
        yield recorder
        status = "SUCCESS" if not recorder.errors else "FAILED"
    except Exception as exc:
        recorder.errors.append(f"{type(exc).__name__}: {exc}")
        status = "FAILED"
        with SessionLocal() as db:
            run = db.get(SystemRun, run_id)
            run.finished_at = dt.datetime.utcnow()
            run.status = status
            run.records_processed = recorder.records_processed
            run.errors_json = json.dumps(recorder.errors, ensure_ascii=False)
            run.warnings_json = json.dumps(recorder.warnings, ensure_ascii=False)
            db.commit()
        logger.error("system_run #%d (%s) FALLIDO: %s", run_id, run_type, exc)
        raise

    with SessionLocal() as db:
        run = db.get(SystemRun, run_id)
        run.finished_at = dt.datetime.utcnow()
        run.status = status
        run.records_processed = recorder.records_processed
        run.errors_json = json.dumps(recorder.errors, ensure_ascii=False)
        run.warnings_json = json.dumps(recorder.warnings, ensure_ascii=False)
        db.commit()

    logger.info(
        "system_run #%d (%s) %s: %d registros, %d errores, %d avisos",
        run_id, run_type, status, recorder.records_processed, len(recorder.errors), len(recorder.warnings),
    )
