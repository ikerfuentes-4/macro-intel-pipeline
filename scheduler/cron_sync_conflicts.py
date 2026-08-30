"""Punto de entrada dedicado para cron / Windows Task Scheduler: sincroniza el registro de
conflictos activos desde Wikipedia. La lista cambia con poca frecuencia (dias/semanas), asi que
basta con programarlo una vez al dia o incluso semanalmente.

Uso:
    python scheduler/cron_sync_conflicts.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import run_sync_conflicts  # noqa: E402

if __name__ == "__main__":
    run_sync_conflicts()
