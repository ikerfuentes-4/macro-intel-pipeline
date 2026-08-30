"""Registro de conflictos armados activos, sincronizado desde la lista publica y mantenida
de Wikipedia "List of ongoing armed conflicts" (via la API oficial de MediaWiki -gratuita, sin
clave, sin registro-). Es una capa de referencia FACTUAL, separada del pipeline de analisis
LLM: no pasa por el motor de consenso cruzado ni por el motor macro, porque no son "noticias
del dia" sino un inventario estructural de conflictos en curso.

Por que Wikipedia y no una lista escrita a mano: los conflictos activos cambian (empiezan,
escalan, terminan) y el conocimiento de un LLM tiene una fecha de corte fija. Wikipedia se
edita continuamente por una comunidad amplia y cita fuentes (ACLED, prensa) para cada fila;
en la version consultada al construir este modulo, la propia tabla ya reflejaba eventos de
2026 (ej. "2026 Iran war", "2026 Lebanon war"), confirmando que es mas fiable que una lista
fija basada en el conocimiento congelado de un modelo.

Limitacion asumida: un conflicto que abarca varios paises se geolocaliza en el centroide del
PRIMER pais de su lista de ubicaciones (el listado completo de paises se conserva aparte). No
es precision cartografica, es suficiente para un marcador de referencia en el mapa.
"""
from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup

from config import settings
from geo.country_centroids import COUNTRY_CENTROIDS
from utils.logging_conf import get_logger

logger = get_logger(__name__)

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
PAGE_TITLE = "List of ongoing armed conflicts"
SOURCE_URL = f"https://en.wikipedia.org/wiki/{PAGE_TITLE.replace(' ', '_')}"

# Las primeras 4 tablas de la pagina son, por orden, las de guerras mayores (10.000+ muertes),
# guerras menores (1.000-9.999), conflictos (100-999) y escaramuzas (1-99). Las tablas
# posteriores son rankings/resumenes, no listados de conflictos individuales.
MAX_SEVERITY_TABLES = 4


def _extract_primary_name(conflict_cell) -> str:
    """La celda de conflicto es una lista arbol (treelist): el <li> de primer nivel es el
    conflicto principal; los anidados son sub-conflictos/escaladas. Se usa solo el principal
    para el nombre mostrado en el mapa."""
    treelist = conflict_cell.find("div", class_="treelist")
    if treelist:
        top_ul = treelist.find("ul")
        top_li = top_ul.find("li", recursive=False) if top_ul else None
        if top_li:
            link = top_li.find("a")
            if link:
                return link.get_text(strip=True)
            return top_li.get_text(strip=True).split("(")[0].strip()
    links = conflict_cell.find_all("a")
    if links:
        return links[0].get_text(strip=True)
    return conflict_cell.get_text(strip=True)[:80]


def _parse_fatality_figure(raw: str) -> int | None:
    """Extrae una cifra de muertes de un texto de Wikipedia (ej. '254,000-263,000+[3][4]' o
    '10,111[5][10]'). Si es un rango, se toma el limite INFERIOR -- estimacion conservadora,
    consistente con el principio de no sobreestimar cuando hay incertidumbre. Devuelve None si
    no hay cifra parseable (no se inventa un valor)."""
    cleaned = re.sub(r"\[\d+\]", "", raw)  # quita referencias [3][4]
    match = re.search(r"[\d,]+", cleaned)
    if not match:
        return None
    try:
        return int(match.group(0).replace(",", ""))
    except ValueError:
        return None


def _first_known_centroid(countries: list[str]) -> tuple[str, float, float] | None:
    for country in countries:
        if country in COUNTRY_CENTROIDS:
            lat, lon = COUNTRY_CENTROIDS[country]
            return country, lat, lon
    return None


def fetch_active_conflicts() -> list[dict]:
    """Descarga y parsea las tablas de conflictos activos de Wikipedia. Devuelve una lista de
    dicts listos para persistir, con el pais principal ya geolocalizado via
    `COUNTRY_CENTROIDS`. Los conflictos cuyo(s) pais(es) no esten en el diccionario de
    centroides se omiten (con warning en el log) en vez de inventar una coordenada."""
    headers = {"User-Agent": settings.user_agent}
    resp = requests.get(
        WIKIPEDIA_API,
        params={"action": "parse", "page": PAGE_TITLE, "prop": "text", "format": "json"},
        headers=headers, timeout=20,
    )
    resp.raise_for_status()
    html = resp.json()["parse"]["text"]["*"]
    soup = BeautifulSoup(html, "lxml")

    tables = soup.find_all("table", class_="wikitable")[:MAX_SEVERITY_TABLES]
    conflicts: list[dict] = []
    omitted = 0

    for table in tables:
        for row in table.find_all("tr")[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) < 4:
                continue

            start_year_text = cells[0].get_text(strip=True)
            conflict_cell = cells[1]
            continent = cells[2].get_text(strip=True)
            location_cell = cells[3]
            # Columnas 4 y 6 (si existen): muertes acumuladas y del ultimo anio reportado.
            # Se usan para el Global Risk Score (ver docs/risk_score_methodology.md) en vez de
            # un proxy de "cuenta de conflictos" sin magnitud -- dato real, no inventado.
            muertes_acumuladas = _parse_fatality_figure(cells[4].get_text(strip=True)) if len(cells) > 4 else None
            muertes_recientes = _parse_fatality_figure(cells[-1].get_text(strip=True)) if len(cells) > 5 else None

            primary_name = _extract_primary_name(conflict_cell)
            countries = [a.get_text(strip=True) for a in location_cell.find_all("a")]
            if not countries:
                countries = [location_cell.get_text(strip=True)]

            centroid = _first_known_centroid(countries)
            if centroid is None:
                omitted += 1
                logger.warning(
                    "Conflicto '%s': ningun pais de %s tiene centroide conocido, se omite del mapa",
                    primary_name, countries,
                )
                continue

            pais_principal, lat, lon = centroid
            conflicts.append({
                "nombre": primary_name,
                "continente": continent,
                "paises": countries,
                "pais_principal": pais_principal,
                "latitud": lat,
                "longitud": lon,
                "inicio_aproximado": start_year_text,
                "muertes_acumuladas": muertes_acumuladas,
                "muertes_recientes": muertes_recientes,
                "fuente_url": SOURCE_URL,
            })

    logger.info(
        "Registro de conflictos: %d sincronizados desde Wikipedia (%d omitidos sin centroide)",
        len(conflicts), omitted,
    )
    return conflicts
