"""Persistencia y evaluacion de las hipotesis falsables del predictor de producto
(`analysis/product_engine.py`). Deliberadamente separado de `persistence/track_record.py` -ver
el docstring de `ProductPrediction` en `persistence/db.py` para la justificacion completa: NO
se combina con el track record del pipeline automatico.
"""
from __future__ import annotations

import datetime as dt

from analysis.schemas import ProductForecast
from analysis.system_prompt import PRODUCT_FORECAST_SYSTEM_PROMPT_VERSION
from core.versions import model_version
from evaluation.market_data import get_latest_price
from persistence.comparators import COMPARATORS
from persistence.db import ProductPrediction, SessionLocal, init_db
from persistence.scoring import compute_scoring
from utils.logging_conf import get_logger

logger = get_logger(__name__)


def save_product_prediction(forecast: ProductForecast, report_path: str | None) -> int:
    """Persiste la hipotesis falsable del predictor de producto, capturando el valor de
    mercado base en el momento de emitirla (igual que `track_record.save_analysis`)."""
    init_db()
    hyp = forecast.hipotesis_falsable
    baseline = hyp.valor_base_al_emitir
    if baseline is None:
        try:
            baseline = get_latest_price(hyp.ticker_validacion)
        except Exception as exc:
            logger.warning("No se pudo capturar valor base para %s: %s", hyp.ticker_validacion, exc)
            baseline = None

    now = dt.datetime.utcnow()
    with SessionLocal() as db:
        row = ProductPrediction(
            producto=forecast.producto,
            raw_json=forecast.model_dump_json(),
            report_path=report_path,
            enunciado=hyp.enunciado,
            ticker_validacion=hyp.ticker_validacion,
            comparador=hyp.comparador,
            valor_umbral=hyp.valor_umbral,
            valor_base_al_emitir=baseline,
            fecha_limite_revision=hyp.fecha_limite_revision.isoformat(),
            probabilidad=forecast.probabilidad,
            model_version=model_version(),
            prompt_version=PRODUCT_FORECAST_SYSTEM_PROMPT_VERSION,
            information_cutoff=now,
            status="PENDIENTE",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        logger.info("Prediccion de producto '%s' guardada (id=%s)", forecast.producto, row.id)
        return row.id


def evaluate_due_product_predictions() -> list[dict]:
    """Igual que `track_record.evaluate_due_predictions` pero sobre `ProductPrediction`.
    Pensado para ejecutarse junto a la evaluacion del pipeline (`python main.py evaluate`)."""
    init_db()
    today = dt.date.today().isoformat()
    results: list[dict] = []

    with SessionLocal() as db:
        due = (
            db.query(ProductPrediction)
            .filter(
                ProductPrediction.status == "PENDIENTE",
                ProductPrediction.fecha_limite_revision <= today,
                ProductPrediction.review_status == "APPROVED",
            )
            .all()
        )
        for pred in due:
            try:
                current_value = get_latest_price(pred.ticker_validacion)
            except Exception as exc:
                logger.error(
                    "Prediccion de producto %s: error obteniendo %s: %s", pred.id, pred.ticker_validacion, exc
                )
                pred.status = "ERROR"
                db.commit()
                continue

            success = COMPARATORS[pred.comparador](current_value, pred.valor_umbral)
            pred.status = "CUMPLIDA" if success else "FALLIDA"
            pred.resultado_valor_real = current_value
            pred.evaluado_en = dt.datetime.utcnow()
            db.commit()

            results.append({
                "product_prediction_id": pred.id,
                "producto": pred.producto,
                "status": pred.status,
                "valor_real": current_value,
                "valor_umbral": pred.valor_umbral,
            })
            logger.info(
                "Prediccion de producto %s ('%s') evaluada: %s (real=%.4f vs umbral=%.4f %s)",
                pred.id, pred.producto, pred.status, current_value, pred.valor_umbral, pred.comparador,
            )

    return results


def product_track_record_summary() -> dict:
    """Metricas agregadas del predictor de producto (incluye Brier score y calibracion, ver
    persistence/scoring.py), SIEMPRE reportadas por separado del track record del pipeline
    automatico. Solo cuenta predicciones con `review_status == 'APPROVED'` (Principio 8)."""
    with SessionLocal() as db:
        base = db.query(ProductPrediction).filter(ProductPrediction.review_status == "APPROVED")
        aciertos = base.filter(ProductPrediction.status == "CUMPLIDA").count()
        fallos = base.filter(ProductPrediction.status == "FALLIDA").count()
        pendientes = base.filter(ProductPrediction.status == "PENDIENTE").count()
        errores = base.filter(ProductPrediction.status == "ERROR").count()
        total = aciertos + fallos

        resolved = base.filter(ProductPrediction.status.in_(["CUMPLIDA", "FALLIDA"])).all()
        resolved_pairs = [(p.probabilidad, p.status == "CUMPLIDA") for p in resolved]
        scoring = compute_scoring(resolved_pairs)

        return {
            "total_evaluadas": total,
            "aciertos": aciertos,
            "fallos": fallos,
            "pendientes": pendientes,
            "errores": errores,
            "tasa_acierto": (aciertos / total) if total else None,
            **scoring,
        }
