"""Persistencia de la auditabilidad de la cadena de agentes (Master Build Prompt, Principio 3
y seccion 8): traza cruda de cada agente + vinculos causales aplicados por evento.
"""
from __future__ import annotations

import json

from pydantic import BaseModel

from persistence.db import AgentTrace, EventCausalLink, SessionLocal, init_db
from utils.logging_conf import get_logger

logger = get_logger(__name__)


def save_agent_trace(
    evento_id: str, agent_name: str, agent_order: int, output: BaseModel,
    model_version: str, prompt_version: str,
) -> None:
    """Persiste la salida cruda de un agente, exista o no un Analysis final (si la cadena se
    aborta despues, ej. por veto del Risk/Contradiction Analyst, la traza queda igualmente
    guardada -- Principio 4: nunca ocultar silenciosamente lo que paso)."""
    init_db()
    with SessionLocal() as db:
        db.add(AgentTrace(
            evento_id=evento_id,
            agent_name=agent_name,
            agent_order=agent_order,
            output_json=output.model_dump_json(),
            model_version=model_version,
            prompt_version=prompt_version,
        ))
        db.commit()


def save_causal_links(analysis_id: int, links: list, causal_priors_version: str) -> None:
    """`links`: lista de `CausalLinkApplication` (analysis/agents/market_transmission_analyst.py)."""
    with SessionLocal() as db:
        for link in links:
            db.add(EventCausalLink(
                analysis_id=analysis_id,
                origen=link.origen,
                relacion=link.relacion,
                destino=link.destino,
                causal_priors_version=causal_priors_version,
                justificacion_aplicacion=link.justificacion_aplicacion,
            ))
        db.commit()


def list_agent_traces(evento_id: str) -> list[dict]:
    """Para inspeccionar la cadena completa de un evento: Prediction -> ... -> Sources."""
    with SessionLocal() as db:
        rows = (
            db.query(AgentTrace)
            .filter(AgentTrace.evento_id == evento_id)
            .order_by(AgentTrace.agent_order)
            .all()
        )
        return [{
            "agent_name": r.agent_name,
            "agent_order": r.agent_order,
            "output": json.loads(r.output_json),
            "model_version": r.model_version,
            "prompt_version": r.prompt_version,
            "created_at": r.created_at.isoformat(),
        } for r in rows]


def list_causal_links(analysis_id: int) -> list[dict]:
    with SessionLocal() as db:
        rows = db.query(EventCausalLink).filter(EventCausalLink.analysis_id == analysis_id).all()
        return [{
            "origen": r.origen,
            "relacion": r.relacion,
            "destino": r.destino,
            "causal_priors_version": r.causal_priors_version,
            "justificacion_aplicacion": r.justificacion_aplicacion,
        } for r in rows]
