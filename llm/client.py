"""Cliente LLM unificado y agnostico de proveedor, con salida JSON forzada y reintento
automatico ante JSON invalido.

Proveedores soportados (ambos con tier gratuito, sin tarjeta de credito):
  - "gemini": Google Gemini via Google AI Studio (SDK `google-genai`). Proveedor por defecto.
  - "groq":   Groq (modelos Llama en infraestructura de inferencia rapida).

Se eligio "modo JSON" (el modelo devuelve texto JSON libre) + validacion Pydantic posterior,
en vez de function-calling nativo, porque el formato de schema de funciones difiere de forma
sustancial entre proveedores (soporte de $ref, uniones, campos nulos, etc.), mientras que
"JSON mode + JSON Schema descrito en el propio prompt" es un patron uniforme y robusto que
funciona igual en cualquier proveedor compatible.
"""
from __future__ import annotations

import json
import re

from config import settings
from llm.circuit_breaker import get_breaker
from utils.logging_conf import get_logger

logger = get_logger(__name__)

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _strip_fences(text: str) -> str:
    """Quita bloques de codigo markdown por si el modelo los añade pese a las instrucciones."""
    return _JSON_FENCE_RE.sub("", text.strip()).strip()


def _build_schema_instructions(schema: dict) -> str:
    return (
        "\n\nDebes responder EXCLUSIVAMENTE con un objeto JSON valido, sin texto adicional, "
        "sin explicaciones y sin bloques de codigo markdown (nada de ```). El JSON debe cumplir "
        "este JSON Schema:\n" + json.dumps(schema, ensure_ascii=False)
    )


def _call_gemini(system_prompt: str, user_content: str) -> str:
    from google import genai
    from google.genai import types

    if not settings.gemini_api_key:
        raise RuntimeError(
            "Falta GEMINI_API_KEY. Consigue una clave gratuita (sin tarjeta) en "
            "https://aistudio.google.com/apikey y configurala en .env"
        )

    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
        ),
    )
    if not response.text:
        raise RuntimeError("Gemini devolvio una respuesta vacia (posible bloqueo de seguridad).")
    return response.text


def _call_groq(system_prompt: str, user_content: str) -> str:
    from groq import Groq

    if not settings.groq_api_key:
        raise RuntimeError(
            "Falta GROQ_API_KEY. Consigue una clave gratuita (sin tarjeta) en "
            "https://console.groq.com/keys y configurala en .env"
        )

    client = Groq(api_key=settings.groq_api_key)
    response = client.chat.completions.create(
        model=settings.groq_model,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    )
    return response.choices[0].message.content


def _call_provider(system_prompt: str, user_content: str) -> str:
    """Cada proveedor tiene su propio circuit breaker (Institutional Prompt, seccion 22): tras
    varios fallos consecutivos de, por ejemplo, Gemini, dejamos de intentar llamarlo durante un
    tiempo en vez de que cada evento del pipeline pague el timeout completo uno por uno."""
    provider = settings.llm_provider
    breaker = get_breaker(provider)
    if provider == "gemini":
        return breaker.call(_call_gemini, system_prompt, user_content)
    if provider == "groq":
        return breaker.call(_call_groq, system_prompt, user_content)
    raise ValueError(f"LLM_PROVIDER desconocido: '{provider}' (usa 'gemini' o 'groq')")


def generate_structured_json(system_prompt: str, user_content: str, schema: dict) -> dict:
    """Invoca al proveedor configurado (Gemini o Groq) forzando salida JSON conforme a
    `schema`, y reintenta una vez si la primera respuesta no es JSON valido, incluyendo el
    error de parseo como contexto adicional para que el modelo se autocorrija."""
    full_system = system_prompt + _build_schema_instructions(schema)

    raw = _call_provider(full_system, user_content)
    try:
        return json.loads(_strip_fences(raw))
    except json.JSONDecodeError as exc:
        logger.warning("Respuesta no era JSON valido, reintentando una vez: %s", exc)
        retry_user = (
            user_content
            + f"\n\nTu respuesta anterior no era JSON valido (error: {exc}). "
              f"Respuesta anterior recibida: {raw[:1000]}\n\n"
              "Corrige el error y devuelve UNICAMENTE el JSON valido, sin nada mas."
        )
        raw_retry = _call_provider(full_system, retry_user)
        return json.loads(_strip_fences(raw_retry))
