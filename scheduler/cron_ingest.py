"""Punto de entrada dedicado para cron / Windows Task Scheduler: ejecuta el ciclo completo de
ingesta + consenso + analisis. Pensado para programarse varias veces al dia.

Uso:
    python scheduler/cron_ingest.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import run_pipeline  # noqa: E402

if __name__ == "__main__":
    run_pipeline()
