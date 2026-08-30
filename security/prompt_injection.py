"""Defensa Tier 1 contra inyeccion de prompt en contenido ingerido (Institutional Prompt,
seccion 6). Todo texto que entra al sistema desde una fuente externa (un articulo de una fuente
"de confianza" incluida) es, a efectos de seguridad, INPUT NO CONFIABLE: nada impide que un
feed comprometido o un articulo malicioso contenga texto disenado para manipular el
razonamiento de un agente ("ignora las instrucciones anteriores...", intentos de fingir ser un
system prompt, etc.).

Esto es un filtro HEURISTICO por patrones -- Tier 1, barato y rapido, NO sustituye un
clasificador de moderacion dedicado (Tier 2, seccion 23 del Institutional Prompt: 'red-teaming
del propio LLM'). Su trabajo es atrapar los intentos obvios y baratos; un atacante sofisticado
podria evadirlo. Se documenta esa limitacion explicitamente en vez de sobrevender su alcance.

Los articulos flagueados NO se eliminan del Raw Data Lake (Principio 4: nunca ocultar datos
silenciosamente) -- se excluyen del CONTEXTO que ve el LLM y quedan marcados para revision.
"""
from __future__ import annotations

import re

from utils.logging_conf import get_logger

logger = get_logger(__name__)

# Patrones deliberadamente amplios (falsos positivos son aceptables aqui: el coste de excluir
# un articulo legitimo del contexto de un agente es bajo; el coste de una inyeccion exitosa no).
_INJECTION_PATTERNS = [
    re.compile(r"ignor[ae]\s+(las?\s+)?instruccion", re.IGNORECASE),
    re.compile(r"ignore\s+(all\s+|previous\s+|the\s+)?instructions", re.IGNORECASE),
    re.compile(r"system\s*prompt", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+", re.IGNORECASE),
    re.compile(r"actua\s+como\s+si\s+fueras", re.IGNORECASE),
    re.compile(r"\bdisregard\s+(all\s+)?prior\b", re.IGNORECASE),
    re.compile(r"<\|.*?\|>"),  # tokens de control tipo <|system|>, <|im_start|>, etc.
    re.compile(r"\[INST\]|\[/INST\]"),  # formato de instrucciones de algunos modelos open-source
]

# Un bloque de texto anormalmente largo sin puntuacion es un patron tipico de intento de
# desbordar/ahogar el contexto del agente con ruido -- umbral generoso para no penalizar
# titulares/citas largas legitimas.
_MAX_UNBROKEN_RUN = 2000


def scan_text(text: str) -> list[str]:
    """Devuelve la lista de motivos por los que el texto se considera sospechoso. Lista vacia
    significa 'sin senales detectadas' (no 'garantizado limpio')."""
    reasons: list[str] = []
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            reasons.append(f"patron sospechoso: {pattern.pattern[:40]}")

    longest_run = max((len(seg) for seg in re.split(r"[.!?\n]", text)), default=0)
    if longest_run > _MAX_UNBROKEN_RUN:
        reasons.append(f"bloque de texto sin puntuacion de {longest_run} caracteres (posible intento de desbordar contexto)")

    return reasons


def is_safe_for_llm_context(text: str, source_name: str = "") -> bool:
    """True si el texto puede incluirse en el contexto de un agente de IA. Registra (log +
    posible evento de auditoria futuro) cualquier senal detectada, incluso si de todas formas
    se permite -- la deteccion es informativa ademas de bloqueante."""
    reasons = scan_text(text)
    if reasons:
        logger.warning(
            "prompt_injection: contenido sospechoso de '%s' excluido del contexto LLM: %s",
            source_name, "; ".join(reasons),
        )
        return False
    return True
