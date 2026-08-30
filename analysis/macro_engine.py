"""Motor de analisis macroeconomico: orquesta la cadena de agentes especializados (Master
Build Prompt, seccion 8) sobre un evento ya validado por consenso cruzado (que cubre los roles
de Source Analyst + Event Analyst, ver `crosscheck/consensus.py`):

    Geopolitical Analyst -> Macro Analyst -> Energy Analyst -> Market Transmission Analyst
        -> Prediction Analyst -> Risk/Contradiction Analyst (poder de veto)

Cada agente ve el contexto acumulado de los anteriores (no solo el evento original) y su
salida cruda se persiste en `AgentTrace` exista o no un `MacroAnalysis` final -- si el
Risk/Contradiction Analyst veta, la cadena entera queda igualmente auditable (Principio 3).
"""
from __future__ import annotations

import uuid

from analysis.agents import (
    energy_analyst,
    geopolitical_analyst,
    macro_analyst,
    market_transmission_analyst,
    prediction_analyst,
    risk_contradiction_analyst,
)
from analysis.agents.market_transmission_analyst import CausalLinkApplication
from analysis.schemas import MacroAnalysis
from core.versions import model_version as get_model_version
from geo.geocode import resolve_coordinates
from persistence.reasoning_trace import save_agent_trace
from utils.logging_conf import get_logger

logger = get_logger(__name__)


def _consensus_context(consensus_verdict: dict) -> str:
    return (
        "Resumen del evento (ya contrastado por consenso cruzado multi-fuente):\n"
        f"{consensus_verdict['resumen_evento']}\n\n"
        "Hechos corroborados de forma independiente:\n- "
        + "\n- ".join(consensus_verdict["hechos_corroborados"]) + "\n\n"
        f"Fuentes que corroboran el evento: {', '.join(consensus_verdict['fuentes_convergentes'])}\n"
        f"Diversidad institucional del consenso: {consensus_verdict['diversidad_institucional']} tipos distintos\n"
        f"Confianza factual del consenso: {consensus_verdict['puntuacion_confianza_factual']}"
    )


def analyze_event(consensus_verdict: dict) -> tuple[MacroAnalysis, list[CausalLinkApplication]] | tuple[None, None]:
    """Devuelve (analisis, vinculos_causales_aplicados), o (None, None) si la cadena se aborta
    (fallo de un agente, o veto del Risk/Contradiction Analyst)."""
    evento_id = str(uuid.uuid4())[:8]
    mv = get_model_version()
    context = _consensus_context(consensus_verdict)

    geo = geopolitical_analyst.run(context)
    if geo is None:
        logger.warning("Evento %s: Geopolitical Analyst fallo, cadena abortada", evento_id)
        return None, None
    save_agent_trace(evento_id, "geopolitical_analyst", 3, geo, mv, geopolitical_analyst.GEOPOLITICAL_ANALYST_PROMPT_VERSION)
    context += (
        f"\n\n=== GEOPOLITICAL ANALYST ===\nCausa raiz: {geo.causa_raiz_geopolitica}\n"
        f"Ubicacion: {geo.ubicacion.pais_o_region}\nActores: {', '.join(geo.actores_relevantes)}"
    )

    macro = macro_analyst.run(context)
    if macro is None:
        logger.warning("Evento %s: Macro Analyst fallo, cadena abortada", evento_id)
        return None, None
    save_agent_trace(evento_id, "macro_analyst", 4, macro, mv, macro_analyst.MACRO_ANALYST_PROMPT_VERSION)
    context += (
        f"\n\n=== MACRO ANALYST ===\nVector politica monetaria: {macro.vector_politica_monetaria}\n"
        f"Prediccion: {macro.prediccion_tipos_interes.instrumento} "
        f"{macro.prediccion_tipos_interes.direccion} (p={macro.prediccion_tipos_interes.probabilidad})"
    )

    energy = energy_analyst.run(context)
    if energy is None:
        logger.warning("Evento %s: Energy Analyst fallo, cadena abortada", evento_id)
        return None, None
    save_agent_trace(evento_id, "energy_analyst", 5, energy, mv, energy_analyst.ENERGY_ANALYST_PROMPT_VERSION)
    context += (
        f"\n\n=== ENERGY ANALYST ===\nAplica a energia: {energy.aplica_a_energia}\n"
        f"Vector: {energy.vector}\nImpacto: {energy.impacto_energetico}"
    )

    market = market_transmission_analyst.run(context)
    if market is None:
        logger.warning("Evento %s: Market Transmission Analyst fallo, cadena abortada", evento_id)
        return None, None
    save_agent_trace(evento_id, "market_transmission_analyst", 6, market, mv, market_transmission_analyst.MARKET_TRANSMISSION_PROMPT_VERSION)
    reacciones_texto = "\n".join(
        f"- {r.clase_activo}: {r.veredicto} ({r.magnitud_esperada}) -- {r.racional}"
        for r in market.reacciones_activos
    )
    context += f"\n\n=== MARKET TRANSMISSION ANALYST ===\nReacciones de activos:\n{reacciones_texto}"

    prediction = prediction_analyst.run(context)
    if prediction is None:
        logger.warning("Evento %s: Prediction Analyst fallo, cadena abortada", evento_id)
        return None, None
    save_agent_trace(evento_id, "prediction_analyst", 7, prediction, mv, prediction_analyst.PREDICTION_ANALYST_PROMPT_VERSION)
    context += (
        f"\n\n=== PREDICTION ANALYST (sintesis final) ===\nHipotesis: {prediction.hipotesis_falsable.enunciado}\n"
        f"Ticker: {prediction.hipotesis_falsable.ticker_validacion} {prediction.hipotesis_falsable.comparador} "
        f"{prediction.hipotesis_falsable.valor_umbral}\nConfianza: {prediction.nivel_confianza_analisis}"
    )

    risk = risk_contradiction_analyst.run(context)
    if risk is None:
        logger.warning("Evento %s: Risk/Contradiction Analyst fallo, cadena abortada", evento_id)
        return None, None
    save_agent_trace(evento_id, "risk_contradiction_analyst", 8, risk, mv, risk_contradiction_analyst.RISK_CONTRADICTION_PROMPT_VERSION)

    if risk.veredicto == "RECHAZADO":
        logger.info(
            "Evento %s: RECHAZADO por Risk/Contradiction Analyst (%s). Traza completa guardada.",
            evento_id, risk.motivo,
        )
        return None, None

    # Correccion geografica determinista (ver geo/geocode.py) antes de ensamblar el resultado.
    lat, lon, fuente = resolve_coordinates(geo.ubicacion.pais_o_region, geo.ubicacion.latitud, geo.ubicacion.longitud)
    if fuente == "catalogo":
        geo.ubicacion.latitud = lat
        geo.ubicacion.longitud = lon

    try:
        analysis = MacroAnalysis(
            evento_id=evento_id,
            causa_raiz_geopolitica=geo.causa_raiz_geopolitica,
            ubicacion=geo.ubicacion,
            vectores_impacto=prediction.vectores_impacto,
            prediccion_tipos_interes=macro.prediccion_tipos_interes,
            reacciones_activos=market.reacciones_activos,
            hipotesis_falsable=prediction.hipotesis_falsable,
            nivel_confianza_analisis=prediction.nivel_confianza_analisis,
            fuentes_utilizadas=consensus_verdict["fuentes_convergentes"],
            limitaciones_y_sesgos_potenciales=prediction.limitaciones_y_sesgos_potenciales,
        )
    except Exception as exc:
        logger.error("Evento %s: fallo al ensamblar MacroAnalysis final: %s", evento_id, exc)
        return None, None

    logger.info(
        "Evento %s: cadena de 8 agentes completa (APROBADO por Risk/Contradiction Analyst), "
        "confianza=%.2f, prediccion=%s %s",
        evento_id, analysis.nivel_confianza_analisis,
        analysis.prediccion_tipos_interes.instrumento, analysis.prediccion_tipos_interes.direccion,
    )
    return analysis, market.relaciones_causales_aplicadas
