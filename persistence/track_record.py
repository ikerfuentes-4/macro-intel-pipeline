"""Track Record Engine: persistencia de analisis validados y evaluacion periodica y automatica
de sus predicciones contra datos de mercado reales (requisito 4).
"""
from __future__ import annotations

import datetime as dt
import json

from analysis.causal_priors import CAUSAL_PRIORS_VERSION
from analysis.schemas import MacroAnalysis
from analysis.system_prompt import MACRO_SYSTEM_PROMPT_VERSION
from core.versions import model_version
from evaluation.market_data import get_latest_price
from persistence.comparators import COMPARATORS
from persistence.db import Analysis, ConsensusEvent, Prediction, SessionLocal, init_db
from persistence.reasoning_trace import save_causal_links
from persistence.scoring import compute_scoring
from utils.logging_conf import get_logger

logger = get_logger(__name__)


def save_consensus(verdict: dict) -> None:
    with SessionLocal() as db:
        existing = db.query(ConsensusEvent).filter_by(cluster_id=verdict["cluster_id"]).first()
        if existing:
            return
        db.add(ConsensusEvent(
            cluster_id=verdict["cluster_id"],
            resumen_evento=verdict["resumen_evento"],
            diversidad_institucional=verdict["diversidad_institucional"],
            puntuacion_confianza=verdict["puntuacion_confianza_factual"],
            apto_para_analisis=verdict["apto_para_analisis"],
            raw_json=json.dumps(verdict, ensure_ascii=False),
        ))
        db.commit()


def save_analysis(analysis: MacroAnalysis, cluster_id: str, causal_links: list | None = None) -> int:
    """Persiste el analisis y crea la Prediction asociada, capturando el valor de mercado base
    en el momento de emitir la hipotesis (necesario para poder evaluarla objetivamente despues).
    Si se pasan `causal_links` (del Market Transmission Analyst, ver analysis/macro_engine.py),
    tambien se persisten como `EventCausalLink` para que el grafo causal sea consultable.

    `information_cutoff` se fija a "ahora" porque el pipeline opera sobre datos recien
    ingeridos (no hay una nocion de 'datos disponibles hasta X' distinta del momento de
    generacion en esta version) -- es el ancla temporal que impide, por diseno, que una
    reevaluacion futura use datos que no existian cuando se emitio la prediccion (Principio 2)."""
    now = dt.datetime.utcnow()
    with SessionLocal() as db:
        hyp = analysis.hipotesis_falsable
        baseline = hyp.valor_base_al_emitir
        if baseline is None:
            try:
                baseline = get_latest_price(hyp.ticker_validacion)
            except Exception as exc:
                logger.warning(
                    "No se pudo capturar valor base para %s: %s", hyp.ticker_validacion, exc
                )
                baseline = None

        row = Analysis(
            evento_id=analysis.evento_id,
            consensus_cluster_id=cluster_id,
            causa_raiz=analysis.causa_raiz_geopolitica,
            raw_json=analysis.model_dump_json(),
            nivel_confianza=analysis.nivel_confianza_analisis,
            model_version=model_version(),
            prompt_version=MACRO_SYSTEM_PROMPT_VERSION,
            information_cutoff=now,
        )
        db.add(row)
        db.flush()  # asigna row.id sin cerrar la transaccion

        pred = Prediction(
            analysis_id=row.id,
            enunciado=hyp.enunciado,
            ticker_validacion=hyp.ticker_validacion,
            comparador=hyp.comparador,
            valor_umbral=hyp.valor_umbral,
            valor_base_al_emitir=baseline,
            fecha_limite_revision=hyp.fecha_limite_revision.isoformat(),
            probabilidad=analysis.prediccion_tipos_interes.probabilidad,
            model_version=model_version(),
            prompt_version=MACRO_SYSTEM_PROMPT_VERSION,
            information_cutoff=now,
            status="PENDIENTE",
        )
        db.add(pred)
        db.commit()
        analysis_row_id = row.id
        logger.info("Analisis %s guardado (prediction id=%s)", analysis.evento_id, pred.id)

    if causal_links:
        save_causal_links(analysis_row_id, causal_links, CAUSAL_PRIORS_VERSION)

    return analysis_row_id


def evaluate_due_predictions() -> list[dict]:
    """Debe ejecutarse periodicamente (cron / Task Scheduler, ver scheduler/cron_evaluate.py).
    Contrasta cada prediccion cuya fecha_limite_revision ya paso con el dato de mercado real y
    fija su veredicto (CUMPLIDA/FALLIDA/ERROR) de forma determinista y auditable."""
    init_db()
    today = dt.date.today().isoformat()
    results: list[dict] = []

    with SessionLocal() as db:
        due = (
            db.query(Prediction)
            .filter(
                Prediction.status == "PENDIENTE",
                Prediction.fecha_limite_revision <= today,
                Prediction.review_status == "APPROVED",  # nunca resolver algo que no fue publicado
            )
            .all()
        )
        for pred in due:
            try:
                current_value = get_latest_price(pred.ticker_validacion)
            except Exception as exc:
                logger.error(
                    "Prediccion %s: error obteniendo %s: %s", pred.id, pred.ticker_validacion, exc
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
                "prediction_id": pred.id,
                "enunciado": pred.enunciado,
                "status": pred.status,
                "valor_real": current_value,
                "valor_umbral": pred.valor_umbral,
            })
            logger.info(
                "Prediccion %s evaluada: %s (real=%.4f vs umbral=%.4f %s)",
                pred.id, pred.status, current_value, pred.valor_umbral, pred.comparador,
            )

    return results


def list_events_for_dashboard(include_pending_review: bool = False) -> list[dict]:
    """Ensambla, para cada analisis, su consenso y su prediccion asociados en un unico dict
    listo para servir al dashboard geoespacial (requisito de visualizacion). No se anaden
    columnas nuevas a la base: `ubicacion` y el resto del analisis ya viven en `raw_json` desde
    que `MacroAnalysis` los incluye; aqui solo se deserializan y se combinan.

    Por defecto SOLO incluye predicciones con `review_status == 'APPROVED'` (Institutional
    Prompt, Principio 8): el dashboard publico nunca muestra una prediccion que un `reviewer`
    humano no haya aprobado. `include_pending_review=True` es para la cola de revision interna
    (requiere rol `reviewer`, ver api/server.py), no para el dashboard general."""
    with SessionLocal() as db:
        query = (
            db.query(Analysis, ConsensusEvent, Prediction)
            .join(ConsensusEvent, Analysis.consensus_cluster_id == ConsensusEvent.cluster_id)
            .outerjoin(Prediction, Prediction.analysis_id == Analysis.id)
        )
        if not include_pending_review:
            query = query.filter(Prediction.review_status == "APPROVED")
        rows = query.order_by(Analysis.created_at.desc()).all()

        events: list[dict] = []
        for analysis, consensus, prediction in rows:
            full_analysis = json.loads(analysis.raw_json)
            consensus_data = json.loads(consensus.raw_json)

            events.append({
                "evento_id": analysis.evento_id,
                "cluster_id": analysis.consensus_cluster_id,
                "titular": consensus.resumen_evento,
                "fuentes_contrastadas": consensus_data.get("fuentes_convergentes", []),
                "diversidad_institucional": consensus.diversidad_institucional,
                "ubicacion": full_analysis.get("ubicacion"),
                "causa_raiz_geopolitica": full_analysis.get("causa_raiz_geopolitica"),
                "vectores_impacto": full_analysis.get("vectores_impacto", []),
                "prediccion_tipos_interes": full_analysis.get("prediccion_tipos_interes"),
                "reacciones_activos": full_analysis.get("reacciones_activos", []),
                "hipotesis_falsable": full_analysis.get("hipotesis_falsable"),
                "nivel_confianza_analisis": full_analysis.get("nivel_confianza_analisis"),
                "limitaciones_y_sesgos_potenciales": full_analysis.get("limitaciones_y_sesgos_potenciales"),
                "prediccion_status": prediction.status if prediction else None,
                "prediccion_valor_real": prediction.resultado_valor_real if prediction else None,
                "review_status": prediction.review_status if prediction else None,
                "created_at": analysis.created_at.isoformat(),
            })
        return events


def track_record_summary() -> dict:
    """Metricas agregadas del track record. Incluye Brier score y calibracion por bandas
    ademas de la tasa de acierto simple (Master Build Prompt seccion 8/13: 'nunca mostrar
    unicamente una tasa de acierto') -- ver persistence/scoring.py para la formula.

    Solo cuenta predicciones con `review_status == 'APPROVED'`: una prediccion nunca aprobada
    (rechazada o aun pendiente de revision) no es parte del track record publico, aunque exista
    en la base de datos (Institutional Prompt, Principio 8)."""
    with SessionLocal() as db:
        base = db.query(Prediction).filter(Prediction.review_status == "APPROVED")
        evaluated = base.filter(Prediction.status.in_(["CUMPLIDA", "FALLIDA"]))
        total = evaluated.count()
        aciertos = base.filter(Prediction.status == "CUMPLIDA").count()
        fallos = base.filter(Prediction.status == "FALLIDA").count()
        pendientes = base.filter(Prediction.status == "PENDIENTE").count()
        errores = base.filter(Prediction.status == "ERROR").count()

        resolved_pairs = [
            (p.probabilidad, p.status == "CUMPLIDA")
            for p in evaluated.all()
        ]
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
