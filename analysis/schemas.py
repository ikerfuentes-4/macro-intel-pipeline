"""Esquemas Pydantic que fuerzan la estructura del analisis macroeconomico (requisito 3).

`MacroAnalysis.model_json_schema()` se describe directamente en el prompt que `macro_engine.py`
envia al LLM (Gemini o Groq, via `llm/client.py`) para forzar su salida en modo JSON, y luego
se revalida con Pydantic al recibirla.
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

Direction = Literal["SUBIDA", "BAJADA", "MANTENER"]
AssetVerdict = Literal["GANADOR", "PERDEDOR", "NEUTRAL"]
Magnitude = Literal["BAJA", "MEDIA", "ALTA"]
Comparator = Literal[">", "<", ">=", "<=", "~="]
GeoLevel = Literal["PAIS", "REGION", "CIUDAD", "AREA_MARITIMA"]

ImpactVector = Literal[
    "OFERTA_GLOBAL",
    "COSTES_ENERGETICOS",
    "RUTAS_COMERCIALES",
    "CONFIANZA_MERCADO",
    "POLITICA_MONETARIA",
    "FLUJOS_DE_CAPITAL",
    "TIPO_DE_CAMBIO",
    "INFLACION",
    "CADENA_DE_SUMINISTRO",
]


class RatePrediction(BaseModel):
    instrumento: str = Field(..., description="Ej: 'Fed Funds Rate', 'Tipo de refinanciacion BCE'")
    direccion: Direction
    probabilidad: float = Field(..., ge=0, le=1)
    horizonte_meses: int = Field(..., ge=1, le=36)
    justificacion: str


class AssetReaction(BaseModel):
    clase_activo: str = Field(..., description="Ej: 'Renta fija soberana EEUU', 'Oro', 'USD/JPY'")
    veredicto: AssetVerdict
    magnitud_esperada: Magnitude
    racional: str


class GeoLocation(BaseModel):
    """Geolocalizacion del evento, asignada por el propio LLM a partir de su conocimiento
    geografico (centroide aproximado del pais/region/area afectada). No es geocodificacion
    de precision -no hay llamada a un servicio de geocoding externo-, es una estimacion
    razonable suficiente para posicionar un marcador en el mapa del dashboard."""

    pais_o_region: str = Field(
        ..., description="Pais, region o area principal afectada, ej 'Ucrania', 'Estrecho de Ormuz'"
    )
    latitud: float = Field(..., ge=-90, le=90)
    longitud: float = Field(..., ge=-180, le=180)
    nivel_geografico: GeoLevel = Field(..., description="Granularidad de la ubicacion asignada")


class FalsifiableHypothesis(BaseModel):
    """Hipotesis falsable con metrica MECANICAMENTE verificable: se ancla a un ticker real de
    Yahoo Finance para que `track_record.py` pueda evaluarla sin intervencion humana."""

    enunciado: str
    fecha_limite_revision: date
    ticker_validacion: str = Field(
        ..., description="Ticker Yahoo Finance verificable, ej '^TNX', 'CL=F', 'DX-Y.NYB', '^GSPC'"
    )
    comparador: Comparator
    valor_umbral: float
    valor_base_al_emitir: float | None = Field(
        default=None, description="Valor del ticker en el momento del analisis; si se omite, se captura automaticamente."
    )
    descripcion_metrica: str


class MacroAnalysis(BaseModel):
    evento_id: str
    causa_raiz_geopolitica: str
    ubicacion: GeoLocation
    vectores_impacto: list[ImpactVector]
    prediccion_tipos_interes: RatePrediction
    reacciones_activos: list[AssetReaction]
    hipotesis_falsable: FalsifiableHypothesis
    nivel_confianza_analisis: float = Field(..., ge=0, le=1)
    fuentes_utilizadas: list[str]
    limitaciones_y_sesgos_potenciales: str = Field(
        ..., description="Autocritica obligatoria: escenario contrario considerado y sesgos propios declarados."
    )


MarketDirection = Literal["ALCISTA", "BAJISTA", "LATERAL"]


class ProductForecast(BaseModel):
    """Prediccion EXPLORATORIA bajo demanda para un producto financiero especifico, generada
    cruzando 4 bloques de datos REALES ya recopilados (ver `analysis/product_research.py`):
    conflictos geopoliticos activos, bancos centrales/tipos, cadenas de suministro/energia y
    sentimiento de mercado. A diferencia de `MacroAnalysis`, esto NO pasa por el motor de
    consenso cruzado (no hay 'noticia' que contrastar, es una consulta directa del usuario).

    Se persiste en una tabla separada (`ProductPrediction`, ver `persistence/db.py`) del track
    record del pipeline automatico, precisamente para no mezclar predicciones bajo demanda
    (potencialmente repetibles hasta obtener una respuesta favorable) con las que el pipeline
    genera automaticamente sobre eventos ya contrastados -eso distorsionaria la credibilidad
    estadistica del track record principal. Ver `analysis/product_engine.py`."""

    producto: str
    conflictos_considerados: list[str] = Field(
        ...,
        description="Nombres de los conflictos activos (de los proporcionados en el bloque 1) "
        "realmente relevantes para este producto; lista vacia si ninguno aplica de forma directa",
    )
    resumen_bancos_centrales: str = Field(
        ..., description="Sintesis de la postura de politica monetaria relevante, a partir de los titulares y proxies de tipos proporcionados (bloque 2)"
    )
    resumen_energia_suministro: str = Field(
        ..., description="Sintesis del estado de cadenas de suministro y energia relevante para el producto (bloque 3)"
    )
    resumen_sentimiento: str = Field(
        ..., description="Sintesis del sentimiento de mercado (risk-on/risk-off) a partir de los proxies proporcionados (bloque 4)"
    )
    tesis_inversion: str = Field(
        ...,
        description="Tesis de inversion rigurosa que CRUZA los 4 bloques anteriores -no es un "
        "resumen de cada uno por separado, es la interaccion entre ellos",
    )
    direccion: MarketDirection
    probabilidad: float = Field(..., ge=0, le=1)
    horizonte_meses: int = Field(..., ge=1, le=24)
    escenario_alternativo: str = Field(
        ..., description="Escenario contrario y que evento tendria que ocurrir para que se materialice"
    )
    hipotesis_falsable: FalsifiableHypothesis
    nivel_confianza: float = Field(..., ge=0, le=1)
    limitaciones: str
