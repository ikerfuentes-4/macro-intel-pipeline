"""Motor de sintesis multi-bloque para el predictor de producto: reune datos REALES de 4
bloques (conflictos, bancos centrales, energia/suministro, sentimiento de mercado, ver
`analysis/product_research.py`), le pide al LLM que los cruce en una tesis de inversion con
hipotesis falsable (`analysis/schemas.py:ProductForecast`), y genera el informe Excel
multi-pestana correspondiente (`analysis/product_report.py`).
"""
from __future__ import annotations

from pathlib import Path

from analysis.product_report import build_product_workbook
from analysis.product_research import (
    gather_central_banks_tab,
    gather_conflicts_tab,
    gather_energy_supply_chain_tab,
    gather_fund_sentiment_tab,
)
from analysis.schemas import ProductForecast
from analysis.system_prompt import PRODUCT_FORECAST_SYSTEM_PROMPT
from llm.client import generate_structured_json
from utils.logging_conf import get_logger

logger = get_logger(__name__)

PRODUCT_JSON_SCHEMA = ProductForecast.model_json_schema()


def _format_conflicts(conflicts: list[dict]) -> str:
    if not conflicts:
        return "(sin conflictos activos registrados; ejecuta 'python main.py sync-conflicts')"
    return "\n".join(
        f"- {c['nombre']} ({c['continente']}, paises: {', '.join(c['paises'])}, activo desde {c['inicio_aproximado']})"
        for c in conflicts
    )


def _format_central_banks(data: dict) -> str:
    lines = [f"- [{h['banco']}] {h['titular']} ({h['publicado']})" for h in data["titulares"]]
    lines += [
        f"- Proxy {p['nombre']} ({p['ticker']}): {p['precio_actual']} (var. {p['dias_lookback']}d: {p['variacion_pct']}%)"
        for p in data["proxies_mercado"]
    ]
    return "\n".join(lines) or "(sin datos disponibles)"


def _format_tickers(items: list[dict]) -> str:
    return "\n".join(
        f"- {i['nombre']} ({i['ticker']}): {i['precio_actual']} (var. {i['dias_lookback']}d: {i['variacion_pct']}%)"
        for i in items
    ) or "(sin datos disponibles)"


def forecast_product(producto: str) -> tuple[ProductForecast | None, Path | None]:
    """Orquesta la recopilacion de los 4 bloques, la sintesis del LLM y la generacion del
    informe Excel. Devuelve (forecast, ruta_del_informe); forecast es None si el LLM o la
    validacion fallan (en ese caso tampoco hay informe)."""
    logger.info("Recopilando los 4 bloques de datos reales para '%s'...", producto)
    conflicts = gather_conflicts_tab()
    central_banks = gather_central_banks_tab()
    energy = gather_energy_supply_chain_tab()
    sentiment = gather_fund_sentiment_tab()

    user_content = (
        f"Producto financiero a analizar: {producto}\n\n"
        f"=== BLOQUE 1: CONFLICTOS GEOPOLITICOS ACTIVOS ===\n{_format_conflicts(conflicts)}\n\n"
        f"=== BLOQUE 2: BANCOS CENTRALES Y TIPOS DE INTERES ===\n{_format_central_banks(central_banks)}\n\n"
        f"=== BLOQUE 3: CADENAS DE SUMINISTRO Y ENERGIA ===\n{_format_tickers(energy)}\n\n"
        f"=== BLOQUE 4: SENTIMIENTO DE MERCADO ===\n{_format_tickers(sentiment)}\n\n"
        "Sintetiza cada bloque, cruza las variables entre si y genera la tesis de inversion "
        "completa con su hipotesis falsable para este producto."
    )

    try:
        payload = generate_structured_json(PRODUCT_FORECAST_SYSTEM_PROMPT, user_content, PRODUCT_JSON_SCHEMA)
    except Exception as exc:
        logger.warning("Prediccion de producto '%s' fallo en el LLM: %s", producto, exc)
        return None, None

    payload.setdefault("producto", producto)
    try:
        forecast = ProductForecast(**payload)
    except Exception as exc:
        logger.error("Prediccion de producto '%s': fallo de validacion Pydantic: %s", producto, exc)
        return None, None

    report_path: Path | None = None
    try:
        report_path = build_product_workbook(producto, conflicts, central_banks, energy, sentiment, forecast)
    except Exception as exc:
        logger.error("No se pudo generar el informe Excel para '%s': %s", producto, exc)

    logger.info(
        "Prediccion de producto '%s': %s (%.0f%%, %dm), %d conflictos considerados",
        producto, forecast.direccion, forecast.probabilidad * 100,
        forecast.horizonte_meses, len(forecast.conflictos_considerados),
    )
    return forecast, report_path
