"""Metricas cuantitativas del track record (Master Build Prompt, seccion 8 y 13: 'nunca
mostrar unicamente una tasa de acierto'). Compartido entre `track_record.py` (pipeline
automatico) y `product_track_record.py` (predictor de producto) -- misma formula, cada uno con
su propio conjunto de datos, nunca mezclados.
"""
from __future__ import annotations

# Bandas de probabilidad para el grafico de calibracion: compara la probabilidad DECLARADA por
# el sistema contra la frecuencia REAL de acierto en esa banda. Es lo que distingue "acierta
# mucho" de "sabe cuanto sabe" -- Principio 5 del Master Build Prompt (confidence != probability)
# aplicado a la evaluacion, no solo a la generacion.
CALIBRATION_BANDS: list[tuple[float, float, str]] = [
    (0.0, 0.5, "0-50%"),
    (0.5, 0.6, "50-60%"),
    (0.6, 0.7, "60-70%"),
    (0.7, 0.8, "70-80%"),
    (0.8, 0.9, "80-90%"),
    (0.9, 1.01, "90-100%"),  # 1.01 para incluir 1.0 exacto sin salirse del ultimo bucket
]

# Por debajo de esto, ninguna metrica de calibracion es estadisticamente fiable -- se marca
# explicitamente en vez de dejar que un "100% de acierto" sobre 3 predicciones parezca senal.
MIN_SAMPLE_FOR_RELIABLE_METRICS = 30


def brier_score(probabilidad: float, cumplida: bool) -> float:
    """(probabilidad_declarada - resultado_real)^2. 0 = perfecto: 1 = lo peor posible."""
    outcome = 1.0 if cumplida else 0.0
    return (probabilidad - outcome) ** 2


def compute_scoring(resolved: list[tuple[float | None, bool]]) -> dict:
    """`resolved`: lista de (probabilidad_declarada, cumplida) de predicciones ya
    CUMPLIDA/FALLIDA. Las predicciones sin `probabilidad` registrada (generadas antes de este
    campo existir) se excluyen del Brier score/calibracion pero se cuentan aparte -- nunca se
    inventa una probabilidad retroactiva para poder puntuarlas (Principio 4)."""
    scored = [(p, c) for p, c in resolved if p is not None]
    n_sin_probabilidad = len(resolved) - len(scored)

    brier_values = [brier_score(p, c) for p, c in scored]
    brier_medio = sum(brier_values) / len(brier_values) if brier_values else None

    calibracion = []
    for lo, hi, label in CALIBRATION_BANDS:
        in_band = [(p, c) for p, c in scored if lo <= p < hi]
        if not in_band:
            continue
        probabilidad_media = sum(p for p, _ in in_band) / len(in_band)
        tasa_acierto_real = sum(1 for _, c in in_band if c) / len(in_band)
        calibracion.append({
            "banda": label,
            "n": len(in_band),
            "probabilidad_media": round(probabilidad_media, 3),
            "tasa_acierto_real": round(tasa_acierto_real, 3),
        })

    return {
        "brier_score_medio": round(brier_medio, 4) if brier_medio is not None else None,
        "calibracion": calibracion,
        "predicciones_sin_probabilidad_registrada": n_sin_probabilidad,
        "muestra_pequena": len(scored) < MIN_SAMPLE_FOR_RELIABLE_METRICS,
        "muestra_minima_recomendada": MIN_SAMPLE_FOR_RELIABLE_METRICS,
    }
