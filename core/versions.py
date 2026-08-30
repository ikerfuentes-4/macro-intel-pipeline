"""Registro central de versionado (Master Build Prompt, seccion 14 "MODEL VERSIONING").

Cada prediccion debe saber EXACTAMENTE que modelo y que version de prompt la produjeron, para
que un cambio de modelo o de prompt en el futuro no contamine retroactivamente resultados ya
generados con una version anterior. `model_version()` se calcula en el momento de la llamada
(no es una constante) porque depende de `settings`, que puede cambiar entre ejecuciones si el
usuario cambia de proveedor en `.env`; las versiones de PROMPT si son constantes de codigo,
porque viven junto al texto del prompt que versionan -- bumpéalas a mano cuando cambies el
contenido de un system prompt de forma material (no en cada typo).
"""
from __future__ import annotations

from config import settings

# Version del propio pipeline de datos (ingesta/consenso/geocoding). Bump cuando cambie algo
# que afecte a que datos ve el LLM (nueva fuente, cambio de umbral de diversidad, etc.).
DATA_PIPELINE_VERSION = "data-pipeline-v1"


def model_version() -> str:
    """Identificador reproducible de que modelo genero una respuesta: '<proveedor>:<modelo>'.
    Se resuelve en el momento de la llamada a partir de `settings`, no se cachea, para que
    reflejar un cambio de LLM_PROVIDER/GEMINI_MODEL/GROQ_MODEL en `.env` sea automatico."""
    if settings.llm_provider == "gemini":
        return f"gemini:{settings.gemini_model}"
    if settings.llm_provider == "groq":
        return f"groq:{settings.groq_model}"
    return f"{settings.llm_provider}:unknown"
