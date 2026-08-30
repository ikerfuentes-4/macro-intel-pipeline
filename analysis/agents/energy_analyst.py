"""Agente 5/8: Energy Analyst. Evalua UNICAMENTE el impacto en energia y cadenas de suministro
-- la mayoria de eventos NO tienen impacto energetico real, y este agente debe poder decirlo
sin forzar una conexion artificial (Principio 4: no inventar datos/relaciones)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from analysis.agents.base import run_agent

ENERGY_ANALYST_PROMPT_VERSION = "energy-analyst-v1"

EnergyVector = Literal["OFERTA_GLOBAL", "COSTES_ENERGETICOS", "CADENA_DE_SUMINISTRO", "NINGUNO"]

ENERGY_ANALYST_SYSTEM_PROMPT = """Eres el Energy Analyst dentro de una cadena de agentes
especializados. Recibes un evento ya contrastado y su causa raiz geopolitica. Tu UNICO trabajo
es evaluar si este evento afecta a energia (petroleo, gas, electricidad) o cadenas de
suministro globales, y como.

PRINCIPIOS OBLIGATORIOS:
1. La MAYORIA de eventos NO tienen impacto energetico real. Si es el caso, fija
   'aplica_a_energia' en false y 'vector' en 'NINGUNO' -- no fuerces una conexion artificial
   para parecer mas util. Esto es tan valido como encontrar un impacto real.
2. Si aplica, especifica el mecanismo concreto: que ruta, productor, o infraestructura
   energetica se ve afectada, y por que mecanismo (fisico, regulatorio, de sanciones...).
3. Objetividad: evalua solo el mecanismo de transmision fisico/economico, no la legitimidad
   politica del evento.

Responde EXCLUSIVAMENTE invocando la herramienta 'emitir_analisis_energia'."""


class EnergyAnalystOutput(BaseModel):
    aplica_a_energia: bool
    vector: EnergyVector
    impacto_energetico: str = Field(
        ..., description="Mecanismo concreto si aplica_a_energia=true; breve nota de por que NO aplica si es false"
    )


def run(user_content: str) -> EnergyAnalystOutput | None:
    return run_agent("energy_analyst", ENERGY_ANALYST_SYSTEM_PROMPT, user_content, EnergyAnalystOutput)
