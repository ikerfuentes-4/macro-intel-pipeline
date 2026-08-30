#!/bin/sh
# Bucle de automatizacion minimo para el servicio "scheduler" de docker-compose.yml (Master
# Build Prompt, seccion 19 "AUTOMATION"). Para produccion real con necesidades de scheduling
# mas finas (horarios distintos por tarea, reintentos con backoff, alertas), sustituye esto por
# cron dentro del contenedor, Celery beat, o un CronJob si migras a Kubernetes -- esta es la
# version minima que cumple la automatizacion sin anadir una dependencia nueva al proyecto.
set -e

INTERVAL="${PIPELINE_INTERVAL_SECONDS:-14400}"  # 4 horas por defecto

echo "scheduler: ciclo cada ${INTERVAL}s (PIPELINE_INTERVAL_SECONDS)"

while true; do
  echo "scheduler: python main.py run"
  python main.py run || echo "scheduler: pipeline_run fallo, se reintenta en el siguiente ciclo"

  echo "scheduler: python main.py evaluate"
  python main.py evaluate || echo "scheduler: evaluate fallo, se reintenta en el siguiente ciclo"

  echo "scheduler: python main.py sync-conflicts"
  python main.py sync-conflicts || echo "scheduler: sync-conflicts fallo, se reintenta en el siguiente ciclo"

  sleep "$INTERVAL"
done
