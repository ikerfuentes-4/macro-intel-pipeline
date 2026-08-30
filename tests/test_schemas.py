"""Smoke tests de los esquemas Pydantic. Ejecutar con: pytest"""
from __future__ import annotations

import datetime as dt

from analysis.schemas import (
    AssetReaction,
    FalsifiableHypothesis,
    GeoLocation,
    MacroAnalysis,
    ProductForecast,
    RatePrediction,
)


def test_macro_analysis_valid_payload():
    analysis = MacroAnalysis(
        evento_id="abc123",
        causa_raiz_geopolitica="Fragmentacion de rutas de suministro energetico en el estrecho X.",
        ubicacion=GeoLocation(
            pais_o_region="Estrecho de Ormuz",
            latitud=26.57,
            longitud=56.25,
            nivel_geografico="AREA_MARITIMA",
        ),
        vectores_impacto=["COSTES_ENERGETICOS", "CONFIANZA_MERCADO"],
        prediccion_tipos_interes=RatePrediction(
            instrumento="Fed Funds Rate",
            direccion="MANTENER",
            probabilidad=0.55,
            horizonte_meses=6,
            justificacion="Presion inflacionaria compensada por debilidad de demanda.",
        ),
        reacciones_activos=[
            AssetReaction(
                clase_activo="Petroleo (WTI)",
                veredicto="GANADOR",
                magnitud_esperada="MEDIA",
                racional="Restriccion de oferta percibida.",
            ),
        ],
        hipotesis_falsable=FalsifiableHypothesis(
            enunciado="El WTI cerrara por encima de 90 USD/barril en 3 meses.",
            fecha_limite_revision=dt.date.today() + dt.timedelta(days=90),
            ticker_validacion="CL=F",
            comparador=">",
            valor_umbral=90.0,
            descripcion_metrica="Precio de cierre del futuro CL=F en Yahoo Finance.",
        ),
        nivel_confianza_analisis=0.6,
        fuentes_utilizadas=["Reuters - World News", "Federal Reserve - Press Releases"],
        limitaciones_y_sesgos_potenciales="Se considero el escenario de desescalada rapida; sesgo de recencia declarado.",
    )
    assert analysis.prediccion_tipos_interes.direccion == "MANTENER"
    assert 0 <= analysis.nivel_confianza_analisis <= 1


def test_macro_analysis_json_schema_has_tool_shape():
    schema = MacroAnalysis.model_json_schema()
    assert schema["type"] == "object"
    assert "hipotesis_falsable" in schema["properties"]


def test_product_forecast_valid_payload():
    forecast = ProductForecast(
        producto="Petroleo WTI (CL=F)",
        conflictos_considerados=["Yemeni civil war", "Russo-Ukrainian war"],
        resumen_bancos_centrales="La Fed mantiene tipos, sin presion adicional relevante para el crudo.",
        resumen_energia_suministro="WTI y Brent en niveles elevados por prima de riesgo geopolitico.",
        resumen_sentimiento="VIX moderado, sin senales claras de aversion al riesgo generalizada.",
        tesis_inversion="La combinacion de riesgo de suministro en rutas clave y politica monetaria estable sostiene un sesgo alcista moderado.",
        direccion="ALCISTA",
        probabilidad=0.6,
        horizonte_meses=6,
        escenario_alternativo="Alto el fuego duradero eliminaria la prima de riesgo.",
        hipotesis_falsable=FalsifiableHypothesis(
            enunciado="El WTI cerrara por encima de 85 USD/barril en 6 meses.",
            fecha_limite_revision=dt.date.today() + dt.timedelta(days=180),
            ticker_validacion="CL=F",
            comparador=">",
            valor_umbral=85.0,
            descripcion_metrica="Precio de cierre del futuro CL=F en Yahoo Finance.",
        ),
        nivel_confianza=0.55,
        limitaciones="Excluye fundamentales de oferta/demanda ajenos a los 4 bloques proporcionados.",
    )
    assert forecast.direccion == "ALCISTA"
    assert 0 <= forecast.nivel_confianza <= 1
    assert forecast.hipotesis_falsable.ticker_validacion == "CL=F"
