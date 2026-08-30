"""Ponderacion por fiabilidad institucional y calculo de diversidad de fuentes de un cluster
de noticias (requisito 2).
"""
from __future__ import annotations

from ingestion.fetchers import RawArticle

# Peso base por tipo de institucion (independiente del peso especifico de cada fuente,
# definido en ingestion/sources.py). Se usa como referencia/documentacion; el peso efectivo
# que se aplica es el `reliability_weight` propio de cada SourceConfig.
INSTITUTION_TYPE_BASE_WEIGHT: dict[str, float] = {
    "banco_central": 0.95,
    "organismo_multilateral": 0.85,
    "dato_primario": 0.95,
    "agencia_prensa": 0.75,
    "think_tank": 0.65,
    "defensa_seguridad": 0.75,
}


def diversity_score(cluster: list[RawArticle]) -> int:
    """Numero de tipos institucionales DISTINTOS representados en el cluster.
    Dos agencias de prensa cuentan como diversidad 1, no 2: evita que multiples medios que
    repiten el mismo cable simulen corroboracion independiente."""
    return len({article.institution_type for article in cluster})


def weighted_confidence(cluster: list[RawArticle]) -> float:
    """Media de los pesos de fiabilidad de las fuentes que componen el cluster."""
    if not cluster:
        return 0.0
    weights = [article.reliability_weight for article in cluster]
    return sum(weights) / len(weights)
