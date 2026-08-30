"""Infraestructura compartida de la cadena de agentes: LLM en modo JSON -> validacion Pydantic,
nunca texto libre para logica interna (Master Build Prompt, seccion 28 "AI OUTPUT CONTRACT").
"""
from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from llm.client import generate_structured_json
from utils.logging_conf import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


def run_agent(agent_name: str, system_prompt: str, user_content: str, output_schema: type[T]) -> T | None:
    """Invoca un agente de la cadena. `generate_structured_json` ya reintenta una vez si el
    JSON no es valido; si sigue fallando (o la validacion Pydantic falla), se devuelve None en
    vez de propagar una excepcion -- el orquestador (`analysis/macro_engine.py`) decide si un
    fallo de este agente concreto aborta la cadena completa o continua de forma degradada."""
    try:
        payload = generate_structured_json(system_prompt, user_content, output_schema.model_json_schema())
        return output_schema(**payload)
    except Exception as exc:
        logger.warning("Agente '%s' fallo: %s", agent_name, exc)
        return None
