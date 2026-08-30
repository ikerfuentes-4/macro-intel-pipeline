"""Capa de correccion geografica: en vez de confiar ciegamente en las coordenadas que el LLM
estima para `MacroAnalysis.ubicacion`, se contrastan contra un catalogo deterministico de
centroides (paises + regiones/areas no nacionales, cada uno con sus alias en espanol). Mismo
principio anti-alucinacion que el resto del pipeline: cuando existe un dato verificable, se usa
ese dato en vez de la estimacion del modelo; el LLM solo decide QUE lugar es relevante (juicio
contextual que si requiere comprension del evento), no las coordenadas exactas (dato factual).

Esto es lo que soluciona el problema de "conflictos que no se ubican bien en el mapa": antes,
un desajuste entre el nombre que el LLM elegia y sus propias coordenadas (o una estimacion poco
precisa) colocaba el marcador en un punto incorrecto. Ahora, si el nombre es reconocible
-directamente, via alias en espanol, o por similitud difusa (ej. una errata o variante menor-,
se sobreescribe con el centroide verificado.
"""
from __future__ import annotations

import unicodedata

from rapidfuzz import fuzz, process

from geo.aliases import COUNTRY_ALIASES
from geo.country_centroids import COUNTRY_CENTROIDS
from geo.region_aliases import REGION_ALIASES
from geo.region_centroids import REGION_CENTROIDS
from utils.logging_conf import get_logger

logger = get_logger(__name__)

FUZZY_SCORE_CUTOFF = 82  # 0-100; por debajo de esto, se descarta la coincidencia como ruido

# Catalogo combinado: nombre canonico -> (lat, lon)
_CATALOG: dict[str, tuple[float, float]] = {**COUNTRY_CENTROIDS, **REGION_CENTROIDS}

# alias normalizado -> nombre canonico
_ALIASES: dict[str, str] = {**COUNTRY_ALIASES, **REGION_ALIASES}


def _normalize(text: str) -> str:
    """Minusculas y sin acentos, para comparar 'Líbano' con 'libano' de forma robusta."""
    decomposed = unicodedata.normalize("NFKD", text.strip().lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def resolve_coordinates(pais_o_region: str, llm_lat: float, llm_lon: float) -> tuple[float, float, str]:
    """Devuelve (latitud, longitud, fuente), donde fuente es 'catalogo' si se encontro una
    coincidencia verificada (exacta, alias en espanol, o difusa por encima del umbral) o 'llm'
    si se conserva la estimacion original del modelo por no encontrar nada fiable."""
    normalized = _normalize(pais_o_region)

    # 1. Coincidencia exacta con la clave canonica (normalizada)
    for canonical, coords in _CATALOG.items():
        if _normalize(canonical) == normalized:
            return coords[0], coords[1], "catalogo"

    # 2. Alias en espanol (exacto)
    if normalized in _ALIASES:
        canonical = _ALIASES[normalized]
        coords = _CATALOG.get(canonical)
        if coords:
            return coords[0], coords[1], "catalogo"

    # 3. Coincidencia difusa contra claves canonicas + alias (typos, variantes menores)
    all_candidates = {**{_normalize(k): k for k in _CATALOG}, **_ALIASES}
    match = process.extractOne(normalized, all_candidates.keys(), scorer=fuzz.WRatio, score_cutoff=FUZZY_SCORE_CUTOFF)
    if match:
        matched_key = match[0]
        canonical = all_candidates[matched_key]
        coords = _CATALOG.get(canonical) or _CATALOG.get(_ALIASES.get(canonical, ""))
        if coords:
            logger.info("Geocoding: '%s' resuelto por similitud difusa a '%s' (score=%.0f)", pais_o_region, canonical, match[1])
            return coords[0], coords[1], "catalogo"

    logger.info("Geocoding: '%s' sin coincidencia en catalogo, se conserva estimacion del LLM", pais_o_region)
    return llm_lat, llm_lon, "llm"
