"""Agrupacion de articulos de distintas fuentes que probablemente cubren el MISMO evento
('Consenso Cruzado', requisito 2). Similitud SEMANTICA por embeddings (`sentence-transformers`,
modelo local, sin API ni coste) -- reemplaza a la version anterior basada en `rapidfuzz` sobre
texto literal del titular.

Por que el cambio: dos medios que cubren el mismo evento real (ej. Reuters y Al Jazeera sobre
el mismo ataque) casi nunca comparten >=55% de las mismas palabras en el titular -- cada
redaccion tiene su propio estilo. Pero SI comparten significado, que es justo lo que un
embedding capta y el texto literal no. Verificado en produccion: con el metodo anterior, 66
fuentes y >3.000 articulos reales solo formaban 12 clusters candidatos y NINGUNO pasaba el
consenso cruzado -- el propio LLM rechazaba los que si se formaban, por agrupar paginas
institucionales genericas que casualmente compartian palabras, no el mismo hecho.

Implementacion: matriz de similitud coseno completa via UNA multiplicacion matricial (BLAS,
vectorizada) en vez de comparar articulo a articulo en un bucle Python -- la primera version de
este cambio usaba un bucle que comparaba cada articulo contra cada cluster existente uno a uno
y con miles de articulos reales tardaba mas de 5 minutos sin terminar; esta version tarda
segundos.

Clustering jerarquico con enlace PROMEDIO (`sklearn.cluster.AgglomerativeClustering`,
`linkage="average"`), no componentes conexas de un grafo de similitud por pares. Se probo
primero con componentes conexas (equivalente a single-linkage) y goteaba un defecto conocido de
ese metodo -- "encadenamiento": un articulo A parecido a B, B parecido a C, C parecido a D...
puede terminar juntando A y D en el mismo cluster aunque no tengan nada que ver entre si,
porque cada salto individual supera el umbral aunque los extremos de la cadena no. Verificado
en produccion: asi se formo un cluster de 362 articulos completamente heterogeneos (una pagina
de biografia de autor, evaluaciones militares de ISW, articulos sobre Kazajistan...). Con
enlace promedio, un articulo solo se une a un cluster si su similitud PROMEDIO con todos sus
miembros supera el umbral, lo que rompe ese encadenamiento.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from functools import lru_cache

import numpy as np
from dateutil import parser as dtparser
from sklearn.cluster import AgglomerativeClustering

from config import settings
from ingestion.fetchers import RawArticle
from utils.logging_conf import get_logger

logger = get_logger(__name__)

# all-MiniLM-L6-v2: ~80MB, referencia estandar para similitud semantica de textos cortos en
# ingles, suficientemente rapido en CPU para miles de articulos por ejecucion sin GPU ni API.
_MODEL_NAME = "all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def _get_model():
    """Carga perezosa y cacheada (proceso completo, no solo esta llamada) -- la primera vez
    descarga el modelo (~80MB); las siguientes lo reutiliza desde disco."""
    from sentence_transformers import SentenceTransformer

    logger.info("Cargando modelo de embeddings '%s' (primera vez: descarga ~80MB)...", _MODEL_NAME)
    return SentenceTransformer(_MODEL_NAME)


_EPOCH = datetime(1970, 1, 1)


def _safe_parse(dt_str: str) -> datetime | None:
    """Devuelve un datetime naive que representa UTC. Si el original trae offset de zona
    horaria, se convierte a UTC antes de descartar el offset -- limitarse a `.replace(tzinfo=
    None)` sin convertir primero desplazaria la hora hasta 12+ horas para fuentes que no
    publican en UTC, lo que rompiba silenciosamente la ventana temporal del clustering."""
    try:
        parsed = dtparser.parse(dt_str)
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except Exception:
        return None


def _embedding_text(art: RawArticle) -> str:
    """Titular + primeros ~300 caracteres del cuerpo -- el titular solo a veces es demasiado
    corto o generico para que el embedding capture bien de que trata el articulo."""
    excerpt = (art.body or "")[:300]
    return f"{art.title}. {excerpt}".strip()


def cluster_articles(articles: list[RawArticle]) -> dict[str, list[RawArticle]]:
    """Agrupa articulos candidatos al mismo evento por similitud semantica (no de texto
    literal) y descarta los que no logran corroboracion multi-fuente (clusters de tamano 1).
    Devuelve {cluster_id: [articulos]}. Misma firma que la version anterior basada en
    rapidfuzz -- nada rio abajo (crosscheck/consensus.py) necesita cambiar."""
    n = len(articles)
    if n == 0:
        return {}

    window_hours = settings.cluster_time_window_hours
    threshold = settings.cluster_semantic_similarity_threshold

    model = _get_model()
    texts = [_embedding_text(a) for a in articles]
    # normalize_embeddings=True: cada vector queda en norma unitaria, asi la matriz de producto
    # escalar de abajo es directamente una matriz de similitud coseno.
    embeddings = np.asarray(
        model.encode(texts, batch_size=64, show_progress_bar=False, normalize_embeddings=True)
    )

    # Matriz n x n de DISTANCIA coseno (1 - similitud) en una sola operacion BLAS -- esto es lo
    # que hace viable procesar miles de articulos en segundos en vez de minutos.
    # AgglomerativeClustering trabaja con distancias, no con similitudes.
    distance = 1.0 - (embeddings @ embeddings.T)
    np.fill_diagonal(distance, 0.0)

    # Horas desde un epoch fijo via resta de datetime pura (NO datetime.timestamp(), que en un
    # datetime naive asume la zona horaria LOCAL de esta maquina -- _safe_parse ya normalizo
    # todo a "naive que representa UTC", asi que restar contra un ancla fija es lo unico
    # correcto aqui).
    published = [_safe_parse(a.published_at) for a in articles]
    hours = np.array(
        [(dt - _EPOCH).total_seconds() / 3600 if dt is not None else np.nan for dt in published]
    )
    with np.errstate(invalid="ignore"):
        delta_hours = np.abs(hours[:, None] - hours[None, :])
    # Si a alguno de los dos no se le pudo parsear la fecha, no se descarta por ventana
    # temporal (mismo criterio que la version anterior: mejor no perder corroboracion real por
    # un timestamp malformado que rechazar de mas).
    unknown_time = np.isnan(delta_hours)
    outside_window = ~unknown_time & (delta_hours > window_hours)
    # Distancia muy por encima del maximo real (2.0 en distancia coseno) para cualquier par
    # fuera de la ventana temporal -- asi el enlace promedio nunca los junta, sin necesidad de
    # un segundo paso de filtrado por tiempo despues del clustering.
    distance[outside_window] = 10.0

    # linkage="average": un articulo solo se incorpora a un cluster si su distancia PROMEDIO a
    # TODOS los miembros existentes esta dentro del umbral -- rompe el encadenamiento descrito
    # arriba, a diferencia de comparar solo contra el vecino mas cercano. distance_threshold en
    # vez de n_clusters: no sabemos de antemano cuantos eventos reales hay, lo determina el
    # propio umbral de similitud configurado.
    clustering = AgglomerativeClustering(
        n_clusters=None,
        metric="precomputed",
        linkage="average",
        distance_threshold=1.0 - threshold,
    )
    labels = clustering.fit_predict(distance)

    groups: dict[int, list[RawArticle]] = {}
    for idx, label in enumerate(labels):
        groups.setdefault(int(label), []).append(articles[idx])

    result: dict[str, list[RawArticle]] = {}
    for members in groups.values():
        if len(members) < 2:
            continue  # sin corroboracion multi-fuente -> se descarta en esta fase
        members.sort(key=lambda a: a.published_at)
        cluster_id = hashlib.sha256(members[0].title.encode("utf-8")).hexdigest()[:16]
        result[cluster_id] = members

    logger.info(
        "Clustering semantico: %d clusters con corroboracion multi-fuente (de %d articulos "
        "crudos, umbral coseno=%.2f)",
        len(result), n, threshold,
    )
    return result
