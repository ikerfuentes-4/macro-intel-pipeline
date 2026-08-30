"""Comparadores compartidos para evaluar hipotesis falsables contra datos de mercado reales.
Usado tanto por el track record del pipeline automatico (persistence/track_record.py) como por
el del predictor de producto (persistence/product_track_record.py), para no duplicar la logica
de evaluacion en dos sitios.
"""
from __future__ import annotations

COMPARATORS = {
    ">": lambda real, umbral: real > umbral,
    "<": lambda real, umbral: real < umbral,
    ">=": lambda real, umbral: real >= umbral,
    "<=": lambda real, umbral: real <= umbral,
    "~=": lambda real, umbral: abs(real - umbral) / max(abs(umbral), 1e-9) < 0.02,
}
