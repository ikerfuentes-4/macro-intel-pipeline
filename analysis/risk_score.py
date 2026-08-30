"""Global Risk Score (componente `conflict_risk`, Fase 1) -- ver metodologia documentada y
aprobada ANTES de este codigo en `docs/risk_score_methodology.md`. Formula 100% deterministica,
sin LLM: usa unicamente el registro de conflictos activos ya sincronizado.
"""
from __future__ import annotations

import math
from collections import defaultdict

from persistence.conflicts import list_active_conflicts

RISK_SCORE_METHODOLOGY_VERSION = "risk-score-v1"

_SEVERITY_WEIGHT = 0.6
_BREADTH_WEIGHT = 0.4
_SEVERITY_LOG_MULTIPLIER = 25
_BREADTH_MULTIPLIER = 25


def _label(score: float) -> str:
    if score <= 0:
        return "SIN_CONFLICTO_ACTIVO"
    if score < 25:
        return "BAJO"
    if score < 50:
        return "MODERADO"
    if score < 75:
        return "ALTO"
    return "SEVERO"


def compute_conflict_risk_by_country() -> list[dict]:
    """Calcula `conflict_risk_score` por pais a partir de `ActiveConflict` (ver formula en
    docs/risk_score_methodology.md). Devuelve solo paises con al menos un conflicto activo que
    los mencione -- un pais ausente de la lista tiene, por definicion, score 0."""
    conflicts = list_active_conflicts()

    deaths_by_country: dict[str, int] = defaultdict(int)
    conflict_count_by_country: dict[str, int] = defaultdict(int)
    conflict_names_by_country: dict[str, set[str]] = defaultdict(set)

    for c in conflicts:
        recent = c.get("muertes_recientes")
        cumulative = c.get("muertes_acumuladas")
        deaths = recent if recent is not None else cumulative
        for country in c["paises"]:
            if country not in conflict_names_by_country or c["nombre"] not in conflict_names_by_country[country]:
                conflict_count_by_country[country] += 1
                conflict_names_by_country[country].add(c["nombre"])
            if deaths is not None:
                deaths_by_country[country] += deaths

    results: list[dict] = []
    for country, num_conflicts in conflict_count_by_country.items():
        total_deaths = deaths_by_country.get(country, 0)

        severity_subscore = min(100.0, _SEVERITY_LOG_MULTIPLIER * math.log10(total_deaths + 1))
        breadth_subscore = min(100.0, _BREADTH_MULTIPLIER * num_conflicts)
        score = round(_SEVERITY_WEIGHT * severity_subscore + _BREADTH_WEIGHT * breadth_subscore)

        results.append({
            "pais": country,
            "conflict_risk_score": score,
            "etiqueta": _label(score),
            "num_conflictos_activos": num_conflicts,
            "muertes_recientes_totales": total_deaths,
            "conflictos": sorted(conflict_names_by_country[country]),
            "methodology_version": RISK_SCORE_METHODOLOGY_VERSION,
        })

    results.sort(key=lambda r: r["conflict_risk_score"], reverse=True)
    return results


# --- energy_risk (Fase 2, parcial) ---
#
# Pesos de criticidad energetica CURADOS a mano (no derivados de una formula ni de una fuente
# unica) -- honesto sobre su naturaleza editorial, igual que los pesos 0.6/0.4 de conflict_risk.
# Combina dos criterios: (a) cuota relevante de produccion/exportacion global de petroleo o gas,
# (b) proximidad a un chokepoint logistico critico (ver geo/region_centroids.py). Lista NO
# exhaustiva -- ampliar aqui si un pais energeticamente relevante falta.
ENERGY_CRITICAL_COUNTRIES: dict[str, float] = {
    "Saudi Arabia": 1.0,   # mayor exportador mundial de petroleo
    "Russia": 1.0,          # mayor exportador de gas natural, gran exportador de petroleo
    "Iran": 0.9,             # gran productor + control de facto sobre el Estrecho de Ormuz
    "Qatar": 0.85,            # mayor exportador de GNL
    "Iraq": 0.8,               # gran productor OPEP
    "United Arab Emirates": 0.8, # gran productor, adyacente a Ormuz
    "Kuwait": 0.7,
    "Yemen": 0.7,              # controla la orilla del Bab-el-Mandeb
    "Libya": 0.6,               # gran productor, oferta volatil
    "Nigeria": 0.6,
    "Venezuela": 0.55,           # mayores reservas probadas, exportacion reducida
    "Egypt": 0.5,                 # control del Canal de Suez
    "Turkey": 0.4,                 # transito de oleoductos + estrechos del Mar Negro
    "Malaysia": 0.35,               # adyacente al Estrecho de Malaca
    "Indonesia": 0.35,
}


def compute_energy_risk_by_country() -> list[dict]:
    """Componente `energy_risk` (parcial, Fase 2): solo paises energeticamente criticos
    (`ENERGY_CRITICAL_COUNTRIES`) que ADEMAS estan afectados por al menos un conflicto activo.
    `energy_risk_score = round(peso_energetico * conflict_risk_score)` -- reutiliza el score de
    conflicto ya calculado en vez de duplicar la logica de agregacion."""
    conflict_scores = {r["pais"]: r for r in compute_conflict_risk_by_country()}

    results: list[dict] = []
    for country, weight in ENERGY_CRITICAL_COUNTRIES.items():
        conflict_row = conflict_scores.get(country)
        if conflict_row is None:
            continue  # energeticamente critico pero sin conflicto activo -> sin energy_risk
        score = round(weight * conflict_row["conflict_risk_score"])
        results.append({
            "pais": country,
            "energy_risk_score": score,
            "etiqueta": _label(score),
            "peso_energetico": weight,
            "conflict_risk_score_base": conflict_row["conflict_risk_score"],
            "methodology_version": RISK_SCORE_METHODOLOGY_VERSION,
        })

    results.sort(key=lambda r: r["energy_risk_score"], reverse=True)
    return results
