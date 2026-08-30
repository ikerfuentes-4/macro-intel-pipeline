# Metodología: catálogo de relaciones causales curadas

**Fuente de verdad ejecutable:** [`analysis/causal_priors.py`](../analysis/causal_priors.py) —
este documento explica el *porqué*, no duplica el catálogo (evita que se desincronicen).

## Problema que resuelve

Pedirle a un LLM que invente, en cada llamada, una "fuerza" numérica para una relación causal
(ej. `strength: 0.72`) es pseudo-cuantificación: parece riguroso pero no está anclado a nada
verificable. Ese número puede cambiar entre dos llamadas idénticas sin ningún motivo real, y no
hay forma de auditar de dónde salió.

## Solución: separar "qué aplica" (juicio del LLM) de "cuánto vale" (dato curado)

Cada relación del catálogo tiene una fuerza **cualitativa** (`ALTA` / `MEDIA` / `BAJA`) asignada
por su robustez en la literatura macroeconómica estándar — no por la intuición del modelo en
esa llamada concreta. El LLM decide **cuáles** de estas relaciones aplican a un evento dado (eso
sí es juicio contextual legítimo) y puede citarlas explícitamente en su razonamiento, pero no
inventa la fuerza del mecanismo desde cero.

## Criterio de inclusión en el catálogo

Una relación entra al catálogo si:

1. Tiene un mecanismo de transmisión económico explicable en una frase (no es solo correlación
   histórica sin mecanismo).
2. Se puede señalar al menos un precedente histórico documentado donde se observó.
3. Se declara explícitamente cuándo el mecanismo **puede fallar o invertirse** (ningún prior es
   incondicional — ver la columna de justificación de cada entrada).

## Nivel de fuerza: qué significa cada uno

- **ALTA**: mecanismo mayormente mecánico/matemático (ej. tipos↑ → precio de bonos↓) o con
  precedente repetido y consistente en múltiples episodios históricos distintos.
- **MEDIA**: mecanismo real y documentado, pero con dirección o magnitud que depende
  significativamente del contexto (de dónde viene el shock, si ya estaba descontado, etc.).
- **BAJA**: no se usa actualmente en el catálogo inicial — reservado para relaciones plausibles
  pero con evidencia mixta; añadir con precaución y siempre con la justificación de por qué se
  incluye pese a la incertidumbre.

## Cómo ampliar el catálogo

Añade una entrada a `CAUSAL_PRIORS` en `analysis/causal_priors.py` siguiendo el mismo formato
(origen, relación, destino, fuerza, justificación con al menos una razón de por qué podría NO
cumplirse). Sube `CAUSAL_PRIORS_VERSION` (ej. `v1` → `v2`) cuando el cambio sea material —
añadir una relación nueva sí lo es; corregir una errata tipográfica no.

## Limitación conocida (Fase 1)

Este catálogo vive como constante en código, no como tabla `relationships` en base de datos con
`relationship_id`, `evidence_ids[]` por evento y grafo consultable (eso es lo que describe la
sección 9 del Master Build Prompt en su forma completa). Es la versión "lean" suficiente para
que el LLM tenga un ancla real en vez de inventar números — la tabla `relationships` con grafo
navegable por evento es una extensión natural de Fase 2, cuando el volumen de eventos analizados
justifique poder preguntar "qué eventos pasados usaron esta relación y con qué resultado".
