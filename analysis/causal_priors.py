"""Catalogo curado de relaciones causales macro/geopoliticas bien documentadas (Master Build
Prompt, seccion 9 "CAUSAL CHAIN"). Fuente unica de verdad: la documentacion humana vive en
`docs/causal_priors.md` (por que existe cada relacion, cuando NO aplica); este modulo es la
version consumible por el system prompt.

Por que existe esto: sin un catalogo curado, pedirle al LLM que invente una 'strength' (ej.
0.72) para una relacion causal en cada llamada es pseudo-cuantificacion -- parece riguroso pero
no esta anclado a nada. Aqui cada relacion tiene una fuerza cualitativa (ALTA/MEDIA/BAJA)
justificada por su robustez en la literatura macro estandar, no por la intuicion del LLM en esa
llamada concreta. El LLM elige CUALES de estas relaciones aplican a un evento dado y por que
-juicio contextual, que si le corresponde-, no CUANTO vale cada una desde cero.

Version: v1 (ver core/versions.py sobre por que las versiones de contenido importan).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Strength = Literal["ALTA", "MEDIA", "BAJA"]

CAUSAL_PRIORS_VERSION = "causal-priors-v1"


@dataclass(frozen=True)
class CausalPrior:
    origen: str
    relacion: str
    destino: str
    fuerza: Strength
    justificacion: str


CAUSAL_PRIORS: list[CausalPrior] = [
    CausalPrior(
        "Riesgo geopolitico en ruta/productor de petroleo", "presiona al alza", "Precio del petroleo (WTI/Brent)",
        "ALTA", "Mecanismo de prima de riesgo de oferta, ampliamente documentado (crisis del 73, Golfo 1990-91, 2022).",
    ),
    CausalPrior(
        "Precio del petroleo", "presiona al alza", "Expectativas de inflacion",
        "ALTA", "El petroleo es insumo directo de energia y transporte; se transmite a IPC con retardo corto (semanas-meses).",
    ),
    CausalPrior(
        "Expectativas de inflacion elevadas", "presiona a", "Bancos centrales a mantener/subir tipos",
        "ALTA", "Mandato de estabilidad de precios es el objetivo primario de la mayoria de bancos centrales del G10.",
    ),
    CausalPrior(
        "Tipos de interes oficiales al alza", "presiona a la baja", "Precio de bonos (rendimientos al alza)",
        "ALTA", "Relacion matematica directa via valoracion de flujos descontados; no es correlacion, es mecanico.",
    ),
    CausalPrior(
        "Aversion al riesgo geopolitico/de mercado (VIX alto)", "presiona al alza", "Demanda de oro",
        "MEDIA", "Oro como activo refugio historico; la fuerza varia segun si la aversion es por inflacion (favorece oro) o por deflacion/crisis de liquidez (puede no favorecerlo).",
    ),
    CausalPrior(
        "Aversion al riesgo global", "presiona al alza", "Demanda de dolar estadounidense (DXY)",
        "MEDIA", "Efecto 'flight to safety' hacia el dolar como moneda de reserva; puede ser contrarrestado si el shock se origina EN EEUU.",
    ),
    CausalPrior(
        "Escalada de conflicto armado en pais productor/exportador clave", "reduce", "Confianza inversora en su moneda/deuda soberana",
        "ALTA", "Prima de riesgo pais sube casi mecanicamente con la percepcion de inestabilidad.",
    ),
    CausalPrior(
        "Sanciones economicas a un pais productor de energia", "reduce", "Oferta global disponible de esa materia prima",
        "ALTA", "Efecto directo de restriccion de oferta, aunque el impacto en PRECIO depende de si otros productores compensan (OPEP+ spare capacity, etc.).",
    ),
    CausalPrior(
        "Disrupcion en una ruta maritima clave (Ormuz, Suez, Mar Rojo)", "presiona al alza", "Costes de flete y seguros de transporte",
        "ALTA", "Efecto mecanico de desvio de ruta/mayor riesgo operativo; historicamente bien documentado (Mar Rojo 2023-24).",
    ),
    CausalPrior(
        "Tension militar entre potencias nucleares/grandes economias", "presiona a la baja", "Indices bursatiles globales",
        "MEDIA", "Efecto de aversion al riesgo bien documentado, pero la magnitud varia mucho segun si el mercado ya tenia la tension descontada.",
    ),
    CausalPrior(
        "Politica monetaria mas restrictiva en EEUU (Fed)", "presiona al alza", "Dolar estadounidense frente a divisas emergentes",
        "ALTA", "Diferencial de tipos de interes es uno de los determinantes mas robustos de flujos de capital hacia el dolar.",
    ),
    CausalPrior(
        "Deficit fiscal creciente y mayor emision de deuda soberana", "presiona al alza", "Rendimientos exigidos en bonos de ese pais",
        "MEDIA", "Efecto de oferta/prima de termino; la fuerza depende del apetito inversor existente y de si el banco central esta comprando deuda.",
    ),
]


def format_causal_priors_for_prompt() -> str:
    """Serializa el catalogo en texto legible para insertarlo en un system prompt."""
    lines = [
        f"- {p.origen} -> [{p.fuerza}] {p.relacion} -> {p.destino}. ({p.justificacion})"
        for p in CAUSAL_PRIORS
    ]
    return "\n".join(lines)
