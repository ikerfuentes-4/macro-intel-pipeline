# Metodología: Global Risk Score (versión Fase 1)

**Fuente de verdad ejecutable:** [`analysis/risk_score.py`](../analysis/risk_score.py) — este
documento se escribió y aprobó *antes* de implementar el código, tal como exige la sección 18
del Master Build Prompt ("no inventes una fórmula arbitraria; primero diseña y documenta una
metodología explicable").

## Alcance de esta versión

Esta Fase 1 calcula **únicamente el componente de riesgo de conflicto armado** (`conflict_risk`)
por país, a partir del registro de conflictos activos ya sincronizado (`ActiveConflict`, ver
`ingestion/conflict_registry.py`). **No** incluye todavía riesgo económico, energético o
comercial por separado (los otros componentes que pide la sección 18) — añadirlos requiere
fuentes de datos dedicadas que hoy no tenemos contrastadas (ver "Extensión futura" abajo). Un
score que mezclara riesgo de conflicto con riesgo económico sin desglosar cada componente
violaría el propio principio de "todas las variables usadas deben ser visibles" — mejor un
score parcial pero transparente que uno completo pero opaco.

## Por qué NO se usa `nivel_confianza_analisis` del pipeline de IA

Podría parecer natural incorporar la confianza de los análisis macro generados por IA sobre un
país al score de riesgo. Se descarta deliberadamente: **confianza y magnitud de riesgo son
variables distintas** (Principio 5 del propio Master Build Prompt — "confidence ≠ probability").
Un análisis de alta confianza sobre un evento de bajo impacto no debería inflar el riesgo, y uno
de baja confianza sobre un evento grave no debería descontarlo. Mezclarlas sería repetir el
mismo error que el principio 5 pide evitar. El score de Fase 1 usa solo datos factuales del
registro de conflictos, no juicios de un LLM.

## Inputs (100% deterministas, sin LLM)

Para cada país, sobre el conjunto de conflictos activos donde aparece en su lista de países
afectados:

1. **`muertes_recientes_totales`**: suma de las muertes del año más reciente reportado por
   Wikipedia (columna `2025/2026 fatalities` de la tabla fuente) para cada conflicto que toca
   el país. Si un conflicto no tiene esa cifra pero sí muertes acumuladas, se usa esa como
   respaldo. Si no hay ninguna cifra parseable, ese conflicto no aporta al numerador (no se
   inventa un número — Principio 4).
2. **`num_conflictos`**: número de conflictos activos DISTINTOS que tocan al país.

## Fórmula

```
severity_subscore = min(100, 25 * log10(muertes_recientes_totales + 1))
breadth_subscore  = min(100, 25 * num_conflictos)

conflict_risk_score = round(0.6 * severity_subscore + 0.4 * breadth_subscore)
```

- **Escala logarítmica en severidad**: las muertes anuales por conflicto abarcan varios órdenes
  de magnitud (decenas vs. decenas de miles); una escala lineal haría que un solo conflicto muy
  letal saturara el score y todo lo demás pareciera insignificante en comparación. `log10`
  comprime ese rango mantenimiento el orden relativo.
- **Peso 0.6/0.4 a favor de severidad sobre amplitud**: un país con un conflicto muy letal es,
  razonablemente, un riesgo mayor que uno tocado por varios conflictos de baja intensidad — pero
  la amplitud (estar involucrado en varios frentes) sigue sumando porque indica inestabilidad
  estructural. Estos pesos son una decisión editorial explícita, no derivada de un ajuste
  estadístico — se documentan aquí precisamente para que sean cuestionables y ajustables.
- **Techo en 100** en ambos subscores: evita que un solo país con cifras extremas distorsione la
  escala comparativa del resto (ej. no queremos que Sudán con `muertes_recientes_totales` en
  cientos de miles haga que todos los demás países se vean como "cero riesgo" por comparación).

## Interpretación de la escala

| Rango | Etiqueta |
|---|---|
| 0 | Sin conflicto activo registrado |
| 1-24 | Riesgo de conflicto bajo |
| 25-49 | Riesgo de conflicto moderado |
| 50-74 | Riesgo de conflicto alto |
| 75-100 | Riesgo de conflicto severo |

## Versionado

`RISK_SCORE_METHODOLOGY_VERSION` en `analysis/risk_score.py` — se sube cuando cambie la fórmula
o los pesos, para que un score calculado con `v1` nunca se compare directamente con uno de `v2`
sin dejarlo explícito (mismo principio de versionado que `model_version`/`prompt_version`).

## `energy_risk` (implementado, Fase 2 parcial)

`analysis/risk_score.py:compute_energy_risk_by_country()`. Formula:

```
energy_risk_score = round(peso_energetico_del_pais * conflict_risk_score_del_pais)
```

`peso_energetico_del_pais` viene de `ENERGY_CRITICAL_COUNTRIES`, una lista **curada a mano**
(no derivada de una formula ni de una unica fuente de datos) que combina dos criterios: cuota
relevante de producción/exportación mundial de petróleo o gas, y proximidad a un chokepoint
logístico crítico (ver `geo/region_centroids.py`). Un país fuera de esa lista tiene
`energy_risk` cero aunque tenga conflictos activos — es intencional: `energy_risk` mide
exposición energética global, no riesgo de conflicto en general (para eso está `conflict_risk`).
Se marca explícitamente como subjetiva/editorial en el propio código, igual que los pesos
0.6/0.4 de `conflict_risk` — es una decisión declarada, no una fórmula pretendidamente objetiva.

## Extensión futura (aún no implementada)

- **`economic_risk`**: a partir de indicadores macro reales por país (inflación, deuda/PIB) —
  requiere una fuente de datos primaria contrastada con series NUMÉRICAS (no solo titulares de
  prensa como las que ya se ingieren de FMI/Banco Mundial). La opción más directa sin coste ni
  tarjeta de crédito sería la API gratuita de FRED (requiere una clave gratuita propia, igual
  que Gemini/Groq) — deliberadamente no integrada todavía para no añadir un requisito de
  configuración nuevo sin que el usuario lo pida explícitamente.
- **`trade_risk`**: aranceles y disputas comerciales activas — no hay hoy una fuente dedicada
  en `ingestion/sources.py`; añadir esto correctamente requeriría el mismo proceso de
  investigación y verificación en vivo que se aplicó a las fuentes existentes, no inventar un
  proxy débil solo por completar la sección.

El score compuesto final (`global_risk_score`) solo debería combinarse cuando `economic_risk` y
`trade_risk` existan con la misma rigurosidad que `conflict_risk`/`energy_risk` — mientras
tanto, el dashboard muestra cada componente etiquetado por separado, nunca un "riesgo global"
que mezcle datos reales con componentes ausentes.
