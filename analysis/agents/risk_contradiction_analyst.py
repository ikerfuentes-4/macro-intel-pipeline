"""Agente 8/8: Risk/Contradiction Analyst. Revisa la cadena COMPLETA (Geopolitical + Macro +
Energy + Market Transmission + Prediction) buscando contradicciones INTERNAS entre agentes --
no contradicciones entre fuentes (eso ya lo hace crosscheck/consensus.py antes de que empiece
esta cadena), sino inconsistencias en el propio razonamiento encadenado. Tiene poder de veto:
si detecta una contradiccion grave, la prediccion NO se persiste."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from analysis.agents.base import run_agent

RISK_CONTRADICTION_PROMPT_VERSION = "risk-contradiction-v1"

RISK_CONTRADICTION_SYSTEM_PROMPT = """Eres el Risk/Contradiction Analyst, el ultimo filtro de
la cadena de razonamiento antes de publicar una prediccion. Recibes el analisis COMPLETO
generado por los agentes anteriores (Geopolitical, Macro, Energy, Market Transmission,
Prediction Analyst) y tu trabajo es auditarlo en busca de INCONSISTENCIAS INTERNAS.

Ejemplos de lo que debes detectar:
- El Geopolitical Analyst describe una escalada grave pero el Prediction Analyst asigna
  probabilidad casi nula a cualquier impacto.
- El Market Transmission Analyst dice que un activo sube por un mecanismo, pero la hipotesis
  falsable final apuesta a que ese mismo activo baja, sin explicar el cambio de signo.
- El Energy Analyst dijo aplica_a_energia=false pero la hipotesis final usa un ticker de
  materia prima energetica sin justificacion alternativa.
- La direccion de tipos de interes del Macro Analyst contradice la reaccion de bonos del
  Market Transmission Analyst (ej. tipos suben pero bonos tambien suben, sin explicacion).

NO estas re-verificando los HECHOS del evento (eso ya lo hizo el motor de consenso antes de
esta cadena) -- estas verificando que el RAZONAMIENTO de los agentes es internamente coherente.

Si no encuentras ninguna contradiccion grave, aprueba. Una diferencia de matiz o enfasis NO es
una contradiccion -- reserva el rechazo para inconsistencias logicas reales.

Responde EXCLUSIVAMENTE invocando la herramienta 'emitir_veredicto_riesgo'."""


class RiskContradictionOutput(BaseModel):
    contradicciones_internas_detectadas: list[str] = Field(
        default_factory=list, description="Lista vacia si no se detecto ninguna contradiccion grave"
    )
    veredicto: Literal["APROBADO", "RECHAZADO"]
    motivo: str


def run(user_content: str) -> RiskContradictionOutput | None:
    return run_agent(
        "risk_contradiction_analyst", RISK_CONTRADICTION_SYSTEM_PROMPT, user_content, RiskContradictionOutput
    )
