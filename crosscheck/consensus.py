"""Motor de Consenso Cruzado: usa el LLM como verificador de hechos (no como analista) para
determinar convergencia factual y detectar contradicciones flagrantes ANTES de que el evento
pase al motor de analisis macro (requisito 2 - Anti-Hallucination & Cross-Check Layer).

Separacion deliberada de responsabilidades: este modulo NUNCA opina sobre implicaciones
economicas; solo certifica que los HECHOS estan corroborados. El razonamiento macro vive en
`analysis/macro_engine.py`, sobre un system prompt distinto.

El LLM se invoca a traves de `llm/client.py` (agnostico de proveedor: Gemini o Groq).
"""
from __future__ import annotations

from config import settings
from crosscheck.reliability import diversity_score, weighted_confidence
from ingestion.fetchers import RawArticle
from llm.client import generate_structured_json
from security.prompt_injection import is_safe_for_llm_context
from utils.logging_conf import get_logger

logger = get_logger(__name__)

CONSENSUS_SYSTEM_PROMPT_VERSION = "consensus-v1"

CONSENSUS_SYSTEM_PROMPT = """Eres un verificador de hechos (fact-checker) senior especializado
en geopolitica y economia. Tu unica tarea es contrastar multiples articulos de prensa o
comunicados oficiales sobre un MISMO evento, procedentes de fuentes distintas, y determinar:

1. Que hechos estan corroborados de forma independiente por al menos dos fuentes de TIPO
   institucional distinto (dos agencias de prensa que repiten el mismo cable NO cuentan como
   corroboracion fuerte; se necesita diversidad de naturaleza institucional).
2. Que afirmaciones son opinion, especulacion o ruido mediatico (descartalas de los hechos
   corroborados).
3. Si existen contradicciones flagrantes entre fuentes sobre los HECHOS centrales (no sobre
   matices de interpretacion o enfasis editorial).
4. Una puntuacion de confianza factual (0 a 1) sobre la fiabilidad del evento en su conjunto.

Reglas anti-sesgo, de cumplimiento obligatorio:
- No penalices ni favorezcas una fuente por su alineamiento politico percibido; evalua
  exclusivamente la convergencia factual entre los textos proporcionados.
- Si solo una fuente afirma algo relevante y las demas simplemente no lo mencionan (sin
  contradecirlo), clasificalo como 'no corroborado', nunca como 'falso'.
- Si detectas una contradiccion factual directa (ej. una fuente afirma que el banco central
  subio los tipos y otra que los mantuvo), es una contradiccion flagrante: el evento NO debe
  aprobarse para analisis hasta resolverse (apto_para_analisis = false).
- Actua con el mismo escepticismo independientemente de si el evento favorece narrativas
  optimistas o pesimistas sobre cualquier region, gobierno o mercado.

Responde EXCLUSIVAMENTE invocando la herramienta 'emitir_veredicto_consenso'."""

CONSENSUS_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "resumen_evento": {
            "type": "string",
            "description": "Resumen neutral y factual del evento, sin interpretacion economica.",
        },
        "hechos_corroborados": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Hechos confirmados de forma independiente por >=2 tipos institucionales distintos.",
        },
        "contradicciones_detectadas": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Contradicciones factuales flagrantes entre fuentes, si las hay.",
        },
        "puntuacion_confianza_factual": {"type": "number", "minimum": 0, "maximum": 1},
        "apto_para_analisis": {
            "type": "boolean",
            "description": "false si hay contradicciones flagrantes o corroboracion insuficiente.",
        },
        "motivo_rechazo": {"type": ["string", "null"]},
    },
    "required": [
        "resumen_evento", "hechos_corroborados", "contradicciones_detectadas",
        "puntuacion_confianza_factual", "apto_para_analisis",
    ],
}


def _format_cluster_for_prompt(cluster: list[RawArticle]) -> str:
    """Filtra articulos sospechosos de inyeccion de prompt ANTES de que su texto llegue al
    contexto del LLM (security/prompt_injection.py, Institutional Prompt seccion 6). El
    articulo sigue existiendo en el Raw Data Lake (Principio 4: nunca ocultar datos), solo se
    excluye de este contexto concreto."""
    parts = []
    for a in cluster:
        if not is_safe_for_llm_context(f"{a.title}\n{a.body}", source_name=a.source_name):
            continue
        parts.append(
            f"### Fuente: {a.source_name} (tipo institucional: {a.institution_type}, "
            f"peso de fiabilidad: {a.reliability_weight})\n"
            f"Titulo: {a.title}\n"
            f"Publicado: {a.published_at}\n"
            f"URL: {a.url}\n"
            f"Texto: {a.body[:1500]}\n"
        )
    return "\n".join(parts)


def evaluate_cluster(cluster_id: str, cluster: list[RawArticle]) -> dict | None:
    """Aplica el filtro de diversidad institucional y, si se supera, delega en el LLM la
    verificacion de convergencia factual y contradicciones. Devuelve el veredicto enriquecido
    con metricas de corroboracion, o None si el cluster ni siquiera merece evaluarse."""
    diversity = diversity_score(cluster)
    if diversity < settings.min_institutional_diversity:
        logger.info(
            "Cluster %s descartado: diversidad institucional insuficiente (%d < %d)",
            cluster_id, diversity, settings.min_institutional_diversity,
        )
        return None

    user_content = (
        f"Cluster de {len(cluster)} articulos que probablemente cubren un mismo evento:\n\n"
        + _format_cluster_for_prompt(cluster)
    )

    try:
        verdict = generate_structured_json(
            CONSENSUS_SYSTEM_PROMPT, user_content, CONSENSUS_JSON_SCHEMA
        )
    except Exception as exc:
        logger.warning("Cluster %s: fallo al obtener veredicto de consenso: %s", cluster_id, exc)
        return None

    verdict["cluster_id"] = cluster_id
    verdict["diversidad_institucional"] = diversity
    verdict["fuentes_convergentes"] = sorted({a.source_name for a in cluster})
    verdict["puntuacion_confianza_ponderada_fuentes"] = weighted_confidence(cluster)

    # Cinturon y tirantes: si el LLM detecto contradicciones pero no marco apto=false,
    # forzamos el rechazo de forma determinista (nunca confiamos ciegamente en el LLM).
    if verdict.get("contradicciones_detectadas"):
        verdict["apto_para_analisis"] = False
        verdict.setdefault(
            "motivo_rechazo", "Contradicciones factuales flagrantes detectadas entre fuentes."
        )

    logger.info(
        "Cluster %s: apto=%s, confianza=%.2f, diversidad=%d",
        cluster_id, verdict["apto_para_analisis"], verdict["puntuacion_confianza_factual"], diversity,
    )
    return verdict
