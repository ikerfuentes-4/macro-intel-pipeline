"""Agente 4/8: Geopolitical Analyst. Identifica la causa raiz estructural (no el titular
superficial) y geolocaliza el evento. Es el PRIMER agente de interpretacion de la cadena: los
demas (Macro, Energy, Market Transmission, Prediction) reciben su salida como contexto."""
from __future__ import annotations

from pydantic import BaseModel, Field

from analysis.agents.base import run_agent
from analysis.schemas import GeoLocation

GEOPOLITICAL_ANALYST_PROMPT_VERSION = "geopolitical-analyst-v1"

GEOPOLITICAL_ANALYST_SYSTEM_PROMPT = """Eres el Geopolitical Analyst dentro de una cadena de
agentes especializados de un sistema de inteligencia macroeconomica. Recibes un evento YA
contrastado por consenso cruzado (no cuestiones los hechos, ya fueron verificados). Tu UNICO
trabajo es identificar la causa raiz ESTRUCTURAL (el factor subyacente, no el titular
superficial) y geolocalizar el evento.

PRINCIPIOS OBLIGATORIOS:
1. Rigor causal: distingue explicitamente entre correlacion y causalidad.
2. Objetividad: no adoptes ninguna postura ideologica, partidista o nacionalista.
3. Geolocalizacion: identifica el pais, region o area (puede ser no nacional, ej. un estrecho
   maritimo) donde se origina o concentra el evento, con coordenadas aproximadas de su
   centroide. Si afecta a multiples paises por igual, elige donde se origino el hecho
   desencadenante, no un promedio geografico sin sentido.

Los agentes siguientes de la cadena (Macro, Energy, Market Transmission, Prediction Analyst)
construiran sobre tu analisis -- se lo mas preciso posible, ellos no vuelven a cuestionar tu
causa raiz.

Responde EXCLUSIVAMENTE invocando la herramienta 'emitir_analisis_geopolitico'."""


class GeopoliticalAnalystOutput(BaseModel):
    causa_raiz_geopolitica: str = Field(..., description="Factor estructural subyacente, no el titular superficial")
    ubicacion: GeoLocation
    actores_relevantes: list[str] = Field(..., description="Paises, organismos o actores no estatales directamente implicados")


def run(user_content: str) -> GeopoliticalAnalystOutput | None:
    return run_agent(
        "geopolitical_analyst", GEOPOLITICAL_ANALYST_SYSTEM_PROMPT, user_content, GeopoliticalAnalystOutput
    )
