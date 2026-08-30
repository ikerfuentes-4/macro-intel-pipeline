"""Circuit breaker para las integraciones externas (Institutional Prompt, seccion 22:
'circuit breakers en cada integracion externa; tras N fallos consecutivos, el sistema deja de
intentar y alerta, en vez de reintentar indefinidamente'). Implementacion minima de proposito
general, sin dependencia nueva -- un proveedor de LLM caido no debe convertirse en decenas de
llamadas fallidas sucesivas (cada una con su propio timeout) que retrasan todo el pipeline.
"""
from __future__ import annotations

import datetime as dt
import threading

from utils.logging_conf import get_logger

logger = get_logger(__name__)


class CircuitOpenError(Exception):
    """Se lanza cuando el circuito esta ABIERTO: no se intenta la llamada, se falla rapido."""


class CircuitBreaker:
    """Estados: CLOSED (normal) -> OPEN (tras `failure_threshold` fallos seguidos, deja de
    intentar durante `cooldown_seconds`) -> HALF_OPEN (pasado el cooldown, permite UNA llamada
    de prueba) -> CLOSED si esa prueba tiene exito, o vuelve a OPEN si falla."""

    def __init__(self, name: str, failure_threshold: int = 5, cooldown_seconds: int = 60):
        self.name = name
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._consecutive_failures = 0
        self._opened_at: dt.datetime | None = None
        self._lock = threading.Lock()

    def _state(self) -> str:
        if self._opened_at is None:
            return "CLOSED"
        elapsed = (dt.datetime.utcnow() - self._opened_at).total_seconds()
        return "HALF_OPEN" if elapsed >= self.cooldown_seconds else "OPEN"

    def call(self, fn, *args, **kwargs):
        with self._lock:
            state = self._state()
            if state == "OPEN":
                raise CircuitOpenError(
                    f"Circuito '{self.name}' ABIERTO tras {self._consecutive_failures} fallos "
                    f"consecutivos. Reintentando en {self.cooldown_seconds}s desde la apertura."
                )

        try:
            result = fn(*args, **kwargs)
        except Exception:
            with self._lock:
                self._consecutive_failures += 1
                if self._consecutive_failures >= self.failure_threshold:
                    self._opened_at = dt.datetime.utcnow()
                    logger.error(
                        "Circuito '%s' ABIERTO: %d fallos consecutivos.",
                        self.name, self._consecutive_failures,
                    )
            raise
        else:
            with self._lock:
                if self._consecutive_failures > 0:
                    logger.info("Circuito '%s': recuperado, contador de fallos reiniciado.", self.name)
                self._consecutive_failures = 0
                self._opened_at = None
            return result

    def status(self) -> dict:
        return {
            "name": self.name,
            "state": self._state(),
            "consecutive_failures": self._consecutive_failures,
            "failure_threshold": self.failure_threshold,
        }


# Un breaker por proveedor de LLM -- un fallo sostenido de Gemini no debe abrir el circuito de
# Groq, son integraciones independientes.
_BREAKERS: dict[str, CircuitBreaker] = {}


def get_breaker(name: str) -> CircuitBreaker:
    if name not in _BREAKERS:
        _BREAKERS[name] = CircuitBreaker(name)
    return _BREAKERS[name]


def all_breaker_statuses() -> list[dict]:
    return [b.status() for b in _BREAKERS.values()]
