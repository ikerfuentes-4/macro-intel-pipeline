"""Conectores de ingesta. Implementacion base via RSS/Atom (feedparser + requests), pensada
para extenderse con conectores API (NewsAPI, FRED, Bloomberg, etc.) siguiendo el mismo contrato
de salida (`RawArticle`).
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import feedparser
import requests

from config import settings
from ingestion.sources import SourceConfig
from utils.logging_conf import get_logger

logger = get_logger(__name__)


@dataclass
class RawArticle:
    source_name: str
    institution_type: str
    reliability_weight: float
    title: str
    url: str
    published_at: str
    body: str


_TITLE_SUFFIX_RE = re.compile(r"\s[-–]\s")


def _looks_like_real_headline(title: str) -> bool:
    """Filtra entradas 'basura' de RSS que no son un titular real -- algunas paginas de indice
    institucional (via `_google_news_proxy`, ver ingestion/sources.py) aparecen con un titulo
    practicamente vacio mas el nombre del sitio, ej. '- IEA – International Energy Agency'
    o '- RBI'. Sin este filtro, decenas de entradas asi -casi sin contenido real- colapsaban en
    un unico cluster falso en crosscheck/clustering.py: el embedding de un texto casi vacio es
    practicamente indistinguible del de otro texto casi vacio, aunque no tengan nada que ver.
    Un titulo que EMPIEZA por guion (ej. '- Bureau of Labor Statistics (.gov)') es siempre este
    caso -Google News sin titular real que devolver-, sin importar su longitud total."""
    if title.startswith("- ") or title.startswith("– "):
        return False
    # Se descarta el posible sufijo ' - Publicador' (formato habitual de Google News) antes de
    # medir, para no penalizar titulares reales que simplemente terminan asi.
    head = _TITLE_SUFFIX_RE.split(title, maxsplit=1)[0].strip()
    return len(head) >= 12


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": settings.user_agent})
    return s


def fetch_source(source: SourceConfig, session: requests.Session | None = None) -> list[RawArticle]:
    """Descarga y parsea un feed RSS/Atom individual. Nunca lanza excepcion hacia arriba:
    un fallo de una fuente no debe tumbar el resto de la ingesta."""
    session = session or _session()
    articles: list[RawArticle] = []
    try:
        resp = session.get(source.url, timeout=settings.fetch_timeout)
        resp.raise_for_status()
        parsed = feedparser.parse(resp.content)
    except Exception as exc:  # red, timeout, feed caido, etc.
        logger.warning("Fallo al obtener %s: %s", source.name, exc)
        return articles

    skipped_junk = 0
    for entry in parsed.entries:
        title = entry.get("title", "").strip()
        link = entry.get("link", "").strip()
        if not title or not link:
            continue
        if not _looks_like_real_headline(title):
            skipped_junk += 1
            continue
        published = entry.get("published", entry.get("updated", ""))
        body = entry.get("summary", entry.get("description", "")).strip()
        articles.append(
            RawArticle(
                source_name=source.name,
                institution_type=source.institution_type,
                reliability_weight=source.reliability_weight,
                title=title,
                url=link,
                published_at=published or datetime.now(timezone.utc).isoformat(),
                body=body,
            )
        )
    # Si el MISMO titular exacto aparece varias veces en una unica descarga de una unica
    # fuente, no son varios articulos reales -- es un artefacto del feed (tipico de Google
    # News repitiendo el enlace generico de un sitio poco activo en cada busqueda). Se
    # colapsan a una sola entrada; sin esto, decenas de duplicados identicos formaban clusters
    # falsos en crosscheck/clustering.py con "corroboracion" que en realidad era la misma
    # fuente hablandose a si misma.
    seen_titles: set[str] = set()
    deduped: list[RawArticle] = []
    duplicates = 0
    for art in articles:
        if art.title in seen_titles:
            duplicates += 1
            continue
        seen_titles.add(art.title)
        deduped.append(art)
    articles = deduped

    parts = [f"{len(articles)} items obtenidos"]
    if skipped_junk:
        parts.append(f"{skipped_junk} descartados por titulo no informativo")
    if duplicates:
        parts.append(f"{duplicates} descartados por titulo duplicado exacto")
    logger.info("%s: %s", source.name, ", ".join(parts))
    return articles


def fetch_all(sources: list[SourceConfig]) -> list[RawArticle]:
    """Recorre todas las fuentes configuradas de forma secuencial y cortes (con pausa entre
    peticiones) para no sobrecargar los servidores de origen."""
    session = _session()
    all_articles: list[RawArticle] = []
    for src in sources:
        all_articles.extend(fetch_source(src, session))
        time.sleep(0.5)
    logger.info("Ingesta total: %d articulos crudos de %d fuentes", len(all_articles), len(sources))
    return all_articles
