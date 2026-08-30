"""Punto de entrada dedicado para cron / Windows Task Scheduler: evalua las predicciones
vencidas contra datos de mercado reales y actualiza el track record. Pensado para programarse
una vez al dia (ej. tras el cierre de mercado).

Uso:
    python scheduler/cron_evaluate.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import run_evaluation  # noqa: E402

if __name__ == "__main__":
    run_evaluation()
