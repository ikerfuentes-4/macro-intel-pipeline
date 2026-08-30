"""Recopilacion de datos REALES (no generados ni inventados por el LLM) para las 4 bloques de
contexto del predictor de producto: conflictos activos, bancos centrales, cadena de suministro
energetica y sentimiento de mercado. El LLM solo sintetiza y cruza estos datos ya contrastados
(ver `analysis/product_engine.py`); nunca los genera desde cero.

Cada bloque corresponde a una pestana del informe Excel multi-pestana (ver
`analysis/product_report.py`).
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from evaluation.market_data import get_price_with_change
from ingestion.fetchers import fetch_source
from ingestion.sources import SOURCES
from persistence.conflicts import list_active_conflicts
from utils.logging_conf import get_logger

logger = get_logger(__name__)

# Tickers Yahoo Finance reales y liquidos para cada bloque. Se documenta la razon de cada uno
# para que la eleccion sea auditable, no arbitraria.
ENERGY_SUPPLY_CHAIN_TICKERS = {
    "CL=F": "Petroleo WTI",
    "BZ=F": "Petroleo Brent",
    "NG=F": "Gas Natural",
    "HG=F": "Cobre (proxy industrial/cadena de suministro)",
}
RATE_PROXY_TICKERS = {
    "^IRX": "T-Bill 13 semanas EEUU (proxy tipo corto)",
    "^TNX": "Bono EEUU 10 anos",
    "^TYX": "Bono EEUU 30 anos",
}
SENTIMENT_TICKERS = {
    "^VIX": "Indice de volatilidad VIX (miedo/complacencia)",
    "^GSPC": "S&P 500 (risk-on/off EEUU)",
    "^STOXX50E": "Euro Stoxx 50 (risk-on/off Europa)",
    "GC=F": "Oro (activo refugio)",
    "DX-Y.NYB": "Indice del dolar DXY (flujos hacia divisa refugio)",
}


def _fetch_ticker_batch(tickers: dict[str, str]) -> list[dict]:
    """Descarga precio + variacion para varios tickers en paralelo (yfinance es la parte lenta
    de esta recopilacion; sin paralelizar, 8-10 tickers secuenciales anaden varios segundos de
    latencia perceptible al boton 'Analizar' del predictor)."""
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=min(8, len(tickers)) or 1) as pool:
        futures = {pool.submit(get_price_with_change, ticker): (ticker, name) for ticker, name in tickers.items()}
        for future in futures:
            ticker, name = futures[future]
            try:
                data = future.result()
                data["nombre"] = name
                results.append(data)
            except Exception as exc:
                logger.warning("No se pudo obtener %s (%s): %s", ticker, name, exc)
    # orden estable para que el informe/prompt sea reproducible
    order = list(tickers.keys())
    results.sort(key=lambda r: order.index(r["ticker"]))
    return results


def gather_conflicts_tab() -> list[dict]:
    """Pestana 1: Conflictos_Geopoliticos. Reutiliza el registro ya sincronizado desde
    Wikipedia (ver persistence/conflicts.py) -- no vuelve a descargarlo en cada consulta."""
    return list_active_conflicts()


def gather_central_banks_tab() -> dict:
    """Pestana 2: Bancos_Centrales_Tipos. Combina los titulares mas recientes de las fuentes
    oficiales de bancos centrales ya configuradas en ingestion/sources.py (fetch en vivo, no
    cache) con proxies de mercado de tipos de interes reales via yfinance."""
    central_bank_sources = [s for s in SOURCES if s.institution_type == "banco_central"]
    headlines: list[dict] = []
    for source in central_bank_sources:
        try:
            articles = fetch_source(source)
        except Exception as exc:
            logger.warning("No se pudo obtener titulares de %s: %s", source.name, exc)
            continue
        for a in articles[:3]:
            headlines.append({
                "banco": source.name,
                "titular": a.title,
                "publicado": a.published_at,
                "url": a.url,
            })

    return {
        "titulares": headlines,
        "proxies_mercado": _fetch_ticker_batch(RATE_PROXY_TICKERS),
    }


def gather_energy_supply_chain_tab() -> list[dict]:
    """Pestana 3: Cadenas_Suministro_Energia."""
    return _fetch_ticker_batch(ENERGY_SUPPLY_CHAIN_TICKERS)


def gather_fund_sentiment_tab() -> list[dict]:
    """Pestana 4: Sentimiento_Fondos. Proxy de mercado (VIX, indices, oro, DXY), no datos de
    flujos de fondos de pago (EPFR/Bloomberg) -- eso requeriria una API de pago incompatible
    con el objetivo del proyecto de funcionar sin tarjeta de credito."""
    return _fetch_ticker_batch(SENTIMENT_TICKERS)
