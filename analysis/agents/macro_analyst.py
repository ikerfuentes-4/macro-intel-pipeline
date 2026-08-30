"""Agente 3/8: Macro Analyst. Evalua UNICAMENTE el impacto en politica monetaria y tipos de
interes -- deliberadamente estrecho, para no repetir el trabajo del Geopolitical/Energy/Market
Transmission Analyst (Master Build Prompt seccion 8: prompts especializados, no uno gigante)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from analysis.agents.base import run_agent
from analysis.schemas import RatePrediction

MACRO_ANALYST_PROMPT_VERSION = "macro-analyst-v1"

MACRO_ANALYST_SYSTEM_PROMPT = """Eres el Macro Analyst dentro de una cadena de agentes
especializados. Recibes un evento ya contrastado y la causa raiz geopolitica ya identificada
por el Geopolitical Analyst (no la cuestiones). Tu UNICO trabajo es evaluar el impacto de este
evento en la politica monetaria y los tipos de interes de referencia.

PRINCIPIOS OBLIGATORIOS:
1. Cuantificacion honesta: evita probabilidades extremas (0.99/0.01) salvo certeza casi
   absoluta con precedente historico directo. Rango tipico: 0.35-0.75.
2. Si el evento no tiene mecanismo de transmision plausible hacia politica monetaria, dilo
   explicitamente en 'vector_politica_monetaria' en vez de forzar una conexion artificial --
   usa direccion='MANTENER' con probabilidad moderada y justificacion honesta de la ausencia
   de mecanismo claro.
3. Identifica el instrumento y banco central mas directamente relevante (ej. Fed Funds Rate
   para eventos con impacto en EEUU/dolar, tipo de refinanciacion BCE para eventos en la
   eurozona) -- no generalices a "los bancos centrales" sin especificar cual.

Responde EXCLUSIVAMENTE invocando la herramienta 'emitir_analisis_macro_tipos'."""


class MacroAnalystOutput(BaseModel):
    vector_politica_monetaria: str = Field(
        ..., description="Mecanismo por el que este evento presiona (o no) la politica monetaria del banco central relevante"
    )
    prediccion_tipos_interes: RatePrediction


def run(user_content: str) -> MacroAnalystOutput | None:
    return run_agent("macro_analyst", MACRO_ANALYST_SYSTEM_PROMPT, user_content, MacroAnalystOutput)
