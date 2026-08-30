"""Obtencion de datos de mercado reales para validar (o refutar) las hipotesis falsables
almacenadas en el Track Record Engine (requisito 4).
"""
from __future__ import annotations

import yfinance as yf

from utils.logging_conf import get_logger

logger = get_logger(__name__)


def get_latest_price(ticker: str) -> float:
    """Ultimo precio de cierre disponible para un ticker de Yahoo Finance. Se usa tanto para
    fijar el valor base de una hipotesis en el momento de emitirla como para su validacion
    posterior en la fecha limite de revision."""
    data = yf.Ticker(ticker).history(period="5d")
    if data.empty:
        raise ValueError(f"Sin datos de mercado disponibles para el ticker '{ticker}'")
    return float(data["Close"].iloc[-1])


def get_price_with_change(ticker: str, lookback_days: int = 5) -> dict:
    """Precio actual y variacion porcentual respecto a `lookback_days` sesiones atras. Se usa
    para alimentar con datos REALES (no generados por el LLM) las pestanas de contexto del
    predictor de producto (energia, tipos de interes, sentimiento) -- ver
    `analysis/product_research.py`."""
    period_days = max(lookback_days, 5) + 5  # margen para fines de semana/festivos
    data = yf.Ticker(ticker).history(period=f"{period_days}d")
    if data.empty:
        raise ValueError(f"Sin datos de mercado disponibles para el ticker '{ticker}'")

    closes = data["Close"]
    current = float(closes.iloc[-1])
    baseline_idx = max(0, len(closes) - 1 - lookback_days)
    baseline = float(closes.iloc[baseline_idx])
    change_pct = ((current - baseline) / baseline * 100) if baseline else 0.0

    return {
        "ticker": ticker,
        "precio_actual": round(current, 4),
        "variacion_pct": round(change_pct, 2),
        "dias_lookback": lookback_days,
    }
