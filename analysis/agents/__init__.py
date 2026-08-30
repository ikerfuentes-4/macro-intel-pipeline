"""Cadena de agentes especializados (Master Build Prompt, seccion 8: 'no utilices un unico
prompt gigantesco para todo').

Mapeo respecto a la cadena de 8 agentes del documento -- honesto, no se duplica trabajo ya
hecho por otros modulos:

    1. Source Analyst      -> crosscheck/consensus.py (verifica fuentes individuales)
    2. Event Analyst       -> crosscheck/clustering.py + crosscheck/consensus.py (agrupa en eventos)
    3. Macro Analyst       -> analysis/agents/macro_analyst.py            [NUEVO]
    4. Geopolitical Analyst-> analysis/agents/geopolitical_analyst.py     [NUEVO]
    5. Energy Analyst      -> analysis/agents/energy_analyst.py          [NUEVO]
    6. Market Transmission -> analysis/agents/market_transmission_analyst.py [NUEVO]
    7. Prediction Analyst  -> analysis/agents/prediction_analyst.py      [NUEVO]
    8. Risk/Contradiction  -> analysis/agents/risk_contradiction_analyst.py [NUEVO] (mas la
                              deteccion determinista de contradicciones ya en crosscheck/)

Orquestado por `analysis/macro_engine.py`. Cada agente devuelve un contrato Pydantic propio y
NUNCA depende de texto libre para logica interna (seccion 28, AI OUTPUT CONTRACT).
"""
