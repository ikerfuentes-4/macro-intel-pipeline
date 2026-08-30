"""Inventario de modelos (Institutional Prompt, seccion 7 -- marco estilo SR 11-7). Registra
cada agente de la cadena de razonamiento como un "modelo" con owner y validacion independiente
propios. `SEED_MODEL_CARDS` refleja los agentes REALES ya construidos (mismo nombre/version que
sus modulos); `owner_email` y `last_independent_validation` se siembran en NULL a proposito --
asignarlos es una decision de la organizacion que usa el sistema, no algo que este codigo pueda
decidir por ella (Principio 7: "ningun modelo sin dueno y sin validacion independiente" no se
cumple solo con tener la tabla, se cumple cuando alguien real rellena esas columnas)."""
from __future__ import annotations

import json

from analysis.agents.energy_analyst import ENERGY_ANALYST_PROMPT_VERSION
from analysis.agents.geopolitical_analyst import GEOPOLITICAL_ANALYST_PROMPT_VERSION
from analysis.agents.macro_analyst import MACRO_ANALYST_PROMPT_VERSION
from analysis.agents.market_transmission_analyst import MARKET_TRANSMISSION_PROMPT_VERSION
from analysis.agents.prediction_analyst import PREDICTION_ANALYST_PROMPT_VERSION
from analysis.agents.risk_contradiction_analyst import RISK_CONTRADICTION_PROMPT_VERSION
from crosscheck.consensus import CONSENSUS_SYSTEM_PROMPT_VERSION
from persistence.db import ModelCard, SessionLocal, init_db
from utils.logging_conf import get_logger

logger = get_logger(__name__)

SEED_MODEL_CARDS: list[dict] = [
    {
        "name": "consensus_analyst", "role_in_chain": "Source Analyst + Event Analyst (1-2/8)",
        "module_path": "crosscheck/consensus.py", "version": CONSENSUS_SYSTEM_PROMPT_VERSION,
        "purpose": "Verifica convergencia factual entre fuentes de un cluster y detecta contradicciones flagrantes antes de que el evento pase a interpretacion.",
        "known_limitations": ["No distingue matices de traduccion entre fuentes en distintos idiomas.", "El umbral de diversidad institucional es un parametro editorial, no derivado estadisticamente."],
    },
    {
        "name": "geopolitical_analyst", "role_in_chain": "Geopolitical Analyst (3/8)",
        "module_path": "analysis/agents/geopolitical_analyst.py", "version": GEOPOLITICAL_ANALYST_PROMPT_VERSION,
        "purpose": "Identifica la causa raiz geopolitica estructural y geolocaliza el evento.",
        "known_limitations": ["La geolocalizacion se corrige contra un catalogo (geo/geocode.py) solo si el lugar es reconocible; lugares muy especificos dependen de la estimacion del modelo."],
    },
    {
        "name": "macro_analyst", "role_in_chain": "Macro Analyst (4/8)",
        "module_path": "analysis/agents/macro_analyst.py", "version": MACRO_ANALYST_PROMPT_VERSION,
        "purpose": "Evalua impacto en politica monetaria y tipos de interes de referencia.",
        "known_limitations": ["Cubre un banco central/instrumento principal por evento, no un analisis multi-banco simultaneo."],
    },
    {
        "name": "energy_analyst", "role_in_chain": "Energy Analyst (5/8)",
        "module_path": "analysis/agents/energy_analyst.py", "version": ENERGY_ANALYST_PROMPT_VERSION,
        "purpose": "Evalua impacto en energia y cadenas de suministro; puede concluir 'no aplica'.",
        "known_limitations": ["No tiene acceso a datos de inventarios fisicos en tiempo real, solo al contexto textual del evento."],
    },
    {
        "name": "market_transmission_analyst", "role_in_chain": "Market Transmission Analyst (6/8)",
        "module_path": "analysis/agents/market_transmission_analyst.py", "version": MARKET_TRANSMISSION_PROMPT_VERSION,
        "purpose": "Selecciona relaciones causales curadas (analysis/causal_priors.py) aplicables y estima reaccion de clases de activos.",
        "known_limitations": ["Limitado al catalogo curado vigente; un mecanismo real no catalogado se declara pero no se cuantifica."],
    },
    {
        "name": "prediction_analyst", "role_in_chain": "Prediction Analyst (7/8)",
        "module_path": "analysis/agents/prediction_analyst.py", "version": PREDICTION_ANALYST_PROMPT_VERSION,
        "purpose": "Sintetiza la cadena completa en la hipotesis falsable final (ticker, comparador, umbral, fecha).",
        "known_limitations": ["Es el punto de mayor impacto de la cadena: un sesgo en agentes previos se propaga aqui sin re-verificacion independiente de los hechos."],
    },
    {
        "name": "risk_contradiction_analyst", "role_in_chain": "Risk/Contradiction Analyst (8/8)",
        "module_path": "analysis/agents/risk_contradiction_analyst.py", "version": RISK_CONTRADICTION_PROMPT_VERSION,
        "purpose": "Revisa la cadena completa en busca de inconsistencias internas entre agentes; tiene poder de veto.",
        "known_limitations": ["Revisa coherencia logica, no vuelve a verificar los hechos originales (eso ya lo hizo consensus_analyst)."],
    },
]


def sync_model_inventory() -> int:
    """Sincroniza `SEED_MODEL_CARDS` a la tabla `model_cards` (upsert por `name`). Actualiza
    purpose/version/known_limitations desde el codigo; NUNCA toca owner_email ni
    last_independent_validation de una fila existente -- esos campos son responsabilidad
    humana, no se resiembran."""
    init_db()
    with SessionLocal() as db:
        for card in SEED_MODEL_CARDS:
            existing = db.query(ModelCard).filter(ModelCard.name == card["name"]).first()
            if existing:
                existing.role_in_chain = card["role_in_chain"]
                existing.module_path = card["module_path"]
                existing.version = card["version"]
                existing.purpose = card["purpose"]
                existing.known_limitations = json.dumps(card["known_limitations"], ensure_ascii=False)
            else:
                db.add(ModelCard(
                    name=card["name"], role_in_chain=card["role_in_chain"],
                    module_path=card["module_path"], version=card["version"],
                    purpose=card["purpose"],
                    known_limitations=json.dumps(card["known_limitations"], ensure_ascii=False),
                ))
        db.commit()
    return len(SEED_MODEL_CARDS)


def list_model_inventory() -> list[dict]:
    with SessionLocal() as db:
        rows = db.query(ModelCard).order_by(ModelCard.name).all()
        return [{
            "name": r.name, "role_in_chain": r.role_in_chain, "module_path": r.module_path,
            "version": r.version, "purpose": r.purpose,
            "known_limitations": json.loads(r.known_limitations),
            "owner_email": r.owner_email,
            "last_independent_validation": r.last_independent_validation.isoformat() if r.last_independent_validation else None,
            "validated_by": r.validated_by,
            "governance_status": "VALIDATED" if r.last_independent_validation else "AWAITING_INDEPENDENT_VALIDATION",
            "updated_at": r.updated_at.isoformat(),
        } for r in rows]


def update_model_card_governance(name: str, owner_email: str | None, validated_by: str | None, mark_validated_now: bool) -> bool:
    """Solo esto (owner + validacion) se actualiza a mano -- ver docstring de sync_model_inventory."""
    import datetime as dt
    with SessionLocal() as db:
        card = db.query(ModelCard).filter(ModelCard.name == name).first()
        if card is None:
            return False
        if owner_email is not None:
            card.owner_email = owner_email
        if mark_validated_now:
            card.last_independent_validation = dt.datetime.utcnow()
            card.validated_by = validated_by
        card.updated_at = dt.datetime.utcnow()
        db.commit()
        return True
