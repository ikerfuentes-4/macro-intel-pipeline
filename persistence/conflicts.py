"""Persistencia del registro de conflictos activos: capa de referencia factual, separada del
Track Record Engine (`persistence/track_record.py`), que solo audita predicciones generadas
por el pipeline de noticias.
"""
from __future__ import annotations

import json

from ingestion.conflict_registry import fetch_active_conflicts
from persistence.db import ActiveConflict, SessionLocal, init_db
from utils.logging_conf import get_logger

logger = get_logger(__name__)


def sync_active_conflicts() -> int:
    """Descarga el snapshot actual de conflictos activos y REEMPLAZA el registro completo
    (borra e reinserta): no acumula historico de versiones, siempre refleja la ultima
    sincronizacion. Devuelve el numero de conflictos sincronizados."""
    init_db()
    conflicts = fetch_active_conflicts()

    with SessionLocal() as db:
        db.query(ActiveConflict).delete()
        for c in conflicts:
            db.add(ActiveConflict(
                nombre=c["nombre"],
                continente=c["continente"],
                pais_principal=c["pais_principal"],
                paises_json=json.dumps(c["paises"], ensure_ascii=False),
                latitud=c["latitud"],
                longitud=c["longitud"],
                inicio_aproximado=c["inicio_aproximado"],
                muertes_acumuladas=c.get("muertes_acumuladas"),
                muertes_recientes=c.get("muertes_recientes"),
                fuente_url=c["fuente_url"],
            ))
        db.commit()

    logger.info("Sincronizados %d conflictos activos en la base de datos", len(conflicts))
    return len(conflicts)


def list_active_conflicts() -> list[dict]:
    """Devuelve el registro de conflictos activos tal como esta en base de datos (no
    sincroniza; usa `sync_active_conflicts()` para refrescar)."""
    with SessionLocal() as db:
        rows = db.query(ActiveConflict).order_by(ActiveConflict.nombre).all()
        return [{
            "id": r.id,
            "nombre": r.nombre,
            "continente": r.continente,
            "pais_principal": r.pais_principal,
            "paises": json.loads(r.paises_json),
            "latitud": r.latitud,
            "longitud": r.longitud,
            "inicio_aproximado": r.inicio_aproximado,
            "muertes_acumuladas": r.muertes_acumuladas,
            "muertes_recientes": r.muertes_recientes,
            "fuente_url": r.fuente_url,
        } for r in rows]
