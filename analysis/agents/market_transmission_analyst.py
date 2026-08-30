"""Agente 6/8: Market Transmission Analyst. Traduce la interpretacion de los agentes previos
(Geopolitical, Macro, Energy) en reacciones de clases de activos, seleccionando ademas del
catalogo de relaciones causales CURADAS (analysis/causal_priors.py) cuales aplican a este
evento -- nunca inventa una relacion causal ni una 'fuerza' desde cero (ver
docs/causal_priors.md para la justificacion metodologica completa)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from analysis.agents.base import run_agent
from analysis.causal_priors import CAUSAL_PRIORS_VERSION, format_causal_priors_for_prompt
from analysis.schemas import AssetReaction

MARKET_TRANSMISSION_PROMPT_VERSION = "market-transmission-v1"

MARKET_TRANSMISSION_SYSTEM_PROMPT = f"""Eres el Market Transmission Analyst dentro de una
cadena de agentes especializados. Recibes un evento ya contrastado, su causa raiz geopolitica,
su vector de politica monetaria y su vector energetico (de los agentes anteriores). Tu UNICO
trabajo es traducir todo eso en reacciones esperadas de clases de activos.

CATALOGO DE RELACIONES CAUSALES CURADAS (version {CAUSAL_PRIORS_VERSION}):
Selecciona SOLO las relaciones de este catalogo que realmente conectan con este evento
concreto. No inventes una relacion nueva ni una 'fuerza' propia -- si necesitas un mecanismo
que no esta aqui, dilo explicitamente en la justificacion en vez de inventarlo:

{format_causal_priors_for_prompt()}

PRINCIPIOS OBLIGATORIOS:
1. Cada relacion causal que cites en 'relaciones_causales_aplicadas' DEBE corresponder
   literalmente (origen/relacion/destino) a una entrada del catalogo de arriba.
2. Para cada clase de activo, el 'racional' debe referenciar el mecanismo causal concreto, no
   una intuicion generica de "sube por incertidumbre".
3. Cubre al menos: renta variable, renta fija, una divisa relevante, y una materia prima si el
   Energy Analyst identifico impacto energetico.

Responde EXCLUSIVAMENTE invocando la herramienta 'emitir_transmision_mercado'."""


class CausalLinkApplication(BaseModel):
    origen: str = Field(..., description="Debe coincidir con el 'origen' de una entrada del catalogo curado")
    relacion: str
    destino: str
    justificacion_aplicacion: str = Field(..., description="Por que esta relacion del catalogo aplica a ESTE evento concreto")


class MarketTransmissionOutput(BaseModel):
    relaciones_causales_aplicadas: list[CausalLinkApplication]
    reacciones_activos: list[AssetReaction]


def run(user_content: str) -> MarketTransmissionOutput | None:
    return run_agent(
        "market_transmission_analyst", MARKET_TRANSMISSION_SYSTEM_PROMPT, user_content, MarketTransmissionOutput
    )
