"""Raw Data Lake: almacenamiento inmutable, append-only, de cada lote de ingesta en formato
JSON Lines, ANTES de cualquier procesamiento/filtrado. Sirve como evidencia auditable de que
los datos usados en el analisis existian tal cual en el momento de la captura (requisito 1).
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from config import settings
from ingestion.fetchers import RawArticle
from utils.logging_conf import get_logger

logger = get_logger(__name__)


def persist_batch(articles: list[RawArticle]) -> Path:
    """Escribe el lote crudo en `data/raw_lake/<YYYY-MM-DD>/batch_<HHMMSS>.jsonl`."""
    now = datetime.now(timezone.utc)
    out_dir = settings.data_lake_dir / now.strftime("%Y-%m-%d")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"batch_{now.strftime('%H%M%S')}.jsonl"

    with out_path.open("w", encoding="utf-8") as f:
        for article in articles:
            record = asdict(article)
            record["_ingested_at_utc"] = now.isoformat()
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    logger.info("Data lake: %d articulos crudos guardados en %s", len(articles), out_path)
    return out_path
