"""Modelos ORM (SQLAlchemy 2.0) del Track Record Engine (requisito 4), ampliados con los
principios del Master Build Prompt: versionado inmutable de cada prediccion (seccion 14),
inmutabilidad aplicada a nivel de base de datos -no solo por convencion- (seccion 2/11), y
`system_runs` para trazabilidad de cada ejecucion (seccion 19/23).

Compatible con SQLite (por defecto, cero configuracion) y PostgreSQL (produccion) via
`DATABASE_URL`. SQLite es suficiente para un track record personal auditable; Postgres
recomendado si se expone un dashboard publico concurrente (Fase 2, ver docs/).
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    event,
    inspect,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from config import settings


class Base(DeclarativeBase):
    pass


class ImmutabilityError(Exception):
    """Se lanza cuando se intenta modificar un campo de contenido de una prediccion ya creada.
    Master Build Prompt, Principio 2 y seccion 11: 'una vez creada una prediccion, NO modificar
    sus variables originales'. Aplicado aqui a nivel de ORM (evento `before_update`), no solo
    documentado como regla -- un bug futuro que intente un UPDATE fallara con esta excepcion en
    vez de corromper silenciosamente el track record."""


class ConsensusEvent(Base):
    """Veredicto del motor de consenso cruzado para un cluster de noticias (aprobado o no)."""

    __tablename__ = "consensus_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    cluster_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    resumen_evento: Mapped[str] = mapped_column(Text)
    diversidad_institucional: Mapped[int] = mapped_column(Integer)
    puntuacion_confianza: Mapped[float] = mapped_column(Float)
    apto_para_analisis: Mapped[bool] = mapped_column(Boolean)
    raw_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)


class Analysis(Base):
    """Analisis macro generado por el LLM para un evento ya validado por consenso.
    `model_version`/`prompt_version`/`information_cutoff` congelados en creacion (Principio 2:
    anti-look-ahead-bias -- un cambio futuro de prompt/modelo nunca reescribe este registro)."""

    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    evento_id: Mapped[str] = mapped_column(String(64), index=True)
    consensus_cluster_id: Mapped[str] = mapped_column(String(64))
    causa_raiz: Mapped[str] = mapped_column(Text)
    raw_json: Mapped[str] = mapped_column(Text)
    nivel_confianza: Mapped[float] = mapped_column(Float)

    model_version: Mapped[str] = mapped_column(String(60), default="")
    prompt_version: Mapped[str] = mapped_column(String(30), default="")
    information_cutoff: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    predictions: Mapped[list["Prediction"]] = relationship(back_populates="analysis")


class Prediction(Base):
    """Hipotesis falsable extraida de un analisis, con su resultado tras evaluacion automatica.

    INMUTABLE una vez creada: los campos de contenido (enunciado, ticker_validacion,
    comparador, valor_umbral, probabilidad, etc.) estan protegidos por un guard a nivel de ORM
    (ver `_guard_immutable_update` al final de este modulo) que rechaza cualquier UPDATE sobre
    ellos. Solo status/resultado_valor_real/evaluado_en son mutables -son precisamente los
    campos que la Resolution Engine debe poder rellenar al vencer el horizonte."""

    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"))

    enunciado: Mapped[str] = mapped_column(Text)
    ticker_validacion: Mapped[str] = mapped_column(String(20))
    comparador: Mapped[str] = mapped_column(String(4))
    valor_umbral: Mapped[float] = mapped_column(Float)
    valor_base_al_emitir: Mapped[float | None] = mapped_column(Float, nullable=True)
    fecha_limite_revision: Mapped[str] = mapped_column(String(20))  # ISO date
    probabilidad: Mapped[float | None] = mapped_column(Float, nullable=True)  # para Brier score

    model_version: Mapped[str] = mapped_column(String(60), default="")
    prompt_version: Mapped[str] = mapped_column(String(30), default="")
    information_cutoff: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)

    # PENDIENTE -> CUMPLIDA | FALLIDA | ERROR (evaluado por scheduler/cron_evaluate.py)
    # Estos campos (mas los 4 de revision de abajo) son los UNICOS mutables tras la creacion.
    status: Mapped[str] = mapped_column(String(20), default="PENDIENTE", index=True)
    resultado_valor_real: Mapped[float | None] = mapped_column(Float, nullable=True)
    evaluado_en: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)

    # Institutional Prompt, Principio 8: "toda prediccion publicada tiene un humano
    # responsable". La IA propone en PENDING_REVIEW; nunca cuenta para el dashboard/track
    # record publico hasta que un usuario con rol `reviewer` la aprueba explicitamente.
    review_status: Mapped[str] = mapped_column(String(20), default="PENDING_REVIEW", index=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    analysis: Mapped["Analysis"] = relationship(back_populates="predictions")


class ActiveConflict(Base):
    """Conflicto armado activo, sincronizado desde Wikipedia (ver
    `ingestion/conflict_registry.py`). Capa de referencia FACTUAL, no generada por el LLM y
    fuera del track record auditado: no tiene analisis macro asociado a menos que coincida con
    un evento que el pipeline de noticias haya analizado por separado."""

    __tablename__ = "active_conflicts"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(255))
    continente: Mapped[str] = mapped_column(String(60))
    pais_principal: Mapped[str] = mapped_column(String(120))
    paises_json: Mapped[str] = mapped_column(Text)  # lista completa de paises afectados
    latitud: Mapped[float] = mapped_column(Float)
    longitud: Mapped[float] = mapped_column(Float)
    inicio_aproximado: Mapped[str] = mapped_column(String(20))
    muertes_acumuladas: Mapped[int | None] = mapped_column(Integer, nullable=True)
    muertes_recientes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fuente_url: Mapped[str] = mapped_column(Text)
    synced_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)


class ProductPrediction(Base):
    """Hipotesis falsable generada por el predictor de producto bajo demanda (ver
    `analysis/product_engine.py`). Tabla DELIBERADAMENTE separada de `Prediction` (pipeline
    automatico): son epistemologicamente distintas -bajo demanda del usuario, potencialmente
    repetibles hasta obtener una respuesta favorable, vs. generadas automaticamente sobre
    eventos ya contrastados por consenso cruzado, con fecha limite fijada de antemano- y NUNCA
    se combinan en un unico track record para no distorsionar su credibilidad estadistica. Se
    evaluan y resumen por separado (ver `persistence/product_track_record.py`). Misma
    inmutabilidad aplicada que `Prediction` (ver guard al final del modulo)."""

    __tablename__ = "product_predictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    producto: Mapped[str] = mapped_column(String(120))
    raw_json: Mapped[str] = mapped_column(Text)  # ProductForecast completo
    report_path: Mapped[str | None] = mapped_column(Text, nullable=True)  # informe .xlsx generado

    enunciado: Mapped[str] = mapped_column(Text)
    ticker_validacion: Mapped[str] = mapped_column(String(20))
    comparador: Mapped[str] = mapped_column(String(4))
    valor_umbral: Mapped[float] = mapped_column(Float)
    valor_base_al_emitir: Mapped[float | None] = mapped_column(Float, nullable=True)
    fecha_limite_revision: Mapped[str] = mapped_column(String(20))
    probabilidad: Mapped[float | None] = mapped_column(Float, nullable=True)

    model_version: Mapped[str] = mapped_column(String(60), default="")
    prompt_version: Mapped[str] = mapped_column(String(30), default="")
    information_cutoff: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="PENDIENTE", index=True)
    resultado_valor_real: Mapped[float | None] = mapped_column(Float, nullable=True)
    evaluado_en: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)

    # Ver docstring del mismo bloque en Prediction -- misma semantica de revision humana.
    review_status: Mapped[str] = mapped_column(String(20), default="PENDING_REVIEW", index=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)


class AgentTrace(Base):
    """Salida cruda de CADA agente de la cadena de razonamiento para un evento (Master Build
    Prompt, seccion 8 + Principio 3 "todo debe ser auditable"). Permite inspeccionar
    exactamente que dijo el Geopolitical/Macro/Energy/Market Transmission/Prediction/Risk
    Analyst por separado, no solo el resultado final combinado en `Analysis.raw_json`."""

    __tablename__ = "agent_traces"

    id: Mapped[int] = mapped_column(primary_key=True)
    evento_id: Mapped[str] = mapped_column(String(64), index=True)
    agent_name: Mapped[str] = mapped_column(String(60))
    agent_order: Mapped[int] = mapped_column(Integer)  # 1-8, orden en la cadena
    output_json: Mapped[str] = mapped_column(Text)
    model_version: Mapped[str] = mapped_column(String(60))
    prompt_version: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)


class EventCausalLink(Base):
    """Vinculo entre un `Analysis` y las relaciones causales CURADAS (ver
    analysis/causal_priors.py) que el Market Transmission Analyst identifico como aplicables a
    ese evento concreto. Hace consultable el grafo causal (Master Build Prompt seccion 9,
    tabla `relationships`): 'que eventos pasados usaron esta relacion y con que resultado'."""

    __tablename__ = "event_causal_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"))
    origen: Mapped[str] = mapped_column(String(255))
    relacion: Mapped[str] = mapped_column(String(120))
    destino: Mapped[str] = mapped_column(String(255))
    causal_priors_version: Mapped[str] = mapped_column(String(30))
    justificacion_aplicacion: Mapped[str] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)


class SystemRun(Base):
    """Trazabilidad de cada ejecucion del sistema (Master Build Prompt, seccion 19/23:
    'cada ejecucion debe tener run_id, started_at, finished_at, status, records_processed,
    errors'). Se usa via el context manager `persistence.system_runs.track_system_run`."""

    __tablename__ = "system_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_type: Mapped[str] = mapped_column(String(30), index=True)  # pipeline_run | evaluate | sync_conflicts | product_predict
    started_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="RUNNING")  # RUNNING | SUCCESS | FAILED
    records_processed: Mapped[int] = mapped_column(Integer, default=0)
    errors_json: Mapped[str] = mapped_column(Text, default="[]")
    warnings_json: Mapped[str] = mapped_column(Text, default="[]")


class User(Base):
    """Identidad de acceso (Institutional Prompt, seccion 6). Password con hash bcrypt, nunca
    en texto plano. `role` es la unica fuente de verdad para RBAC -- ver core/auth.py."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    # viewer < analyst < reviewer < admin (jerarquia comprobada en core/auth.py)
    role: Mapped[str] = mapped_column(String(20), default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    last_login_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class AuditLog(Base):
    """Registro de auditoria con integridad criptografica (Institutional Prompt, Principio 10 y
    seccion 24): cada entrada incluye el hash de la entrada anterior (`prev_hash`), formando una
    cadena -- alterar o borrar una entrada antigua rompe visiblemente `entry_hash` de todas las
    posteriores. Verificable con `persistence.audit.verify_audit_chain()`. Esto es lo que separa
    un log de auditoria de un log de depuracion: aqui la integridad es la propiedad que importa,
    no solo el contenido."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_email: Mapped[str] = mapped_column(String(255), index=True)
    actor_role: Mapped[str] = mapped_column(String(20))
    action: Mapped[str] = mapped_column(String(60), index=True)
    entity_type: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[str] = mapped_column(String(64))
    details_json: Mapped[str] = mapped_column(Text, default="{}")
    prev_hash: Mapped[str] = mapped_column(String(64))
    entry_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)


class ModelCard(Base):
    """Inventario de modelos (Institutional Prompt, seccion 7 -- marco estilo SR 11-7). Un
    'modelo' aqui es cualquier agente de la cadena de IA o motor deterministico con impacto en
    una prediccion publicada. `owner` y `last_independent_validation` empiezan NULL a proposito:
    asignarlos es una decision organizativa real, no algo que el codigo pueda rellenar solo."""

    __tablename__ = "model_cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    role_in_chain: Mapped[str] = mapped_column(String(120))
    module_path: Mapped[str] = mapped_column(String(255))
    version: Mapped[str] = mapped_column(String(30))
    purpose: Mapped[str] = mapped_column(Text)
    known_limitations: Mapped[str] = mapped_column(Text, default="[]")  # JSON list[str]
    owner_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_independent_validation: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    validated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)


class SystemControl(Base):
    """Fila unica de control global (Institutional Prompt, seccion 7: kill switch). Cuando
    `predictions_publishing_enabled=False`, ninguna prediccion nueva puede pasar de
    PENDING_REVIEW a APPROVED, sin importar quien lo intente -- ver core/auth.py y
    api/server.py:review_prediction."""

    __tablename__ = "system_control"

    id: Mapped[int] = mapped_column(primary_key=True)
    predictions_publishing_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    disabled_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    disabled_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    disabled_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


engine = create_engine(settings.database_url, echo=False)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

# Campos que la Resolution Engine Y el flujo de revision humana pueden modificar tras la
# creacion de una prediccion. Todo lo demas queda congelado (Principio 2 y seccion 11).
_PREDICTION_MUTABLE_FIELDS = {
    "status", "resultado_valor_real", "evaluado_en",
    "review_status", "reviewed_by", "reviewed_at", "review_note",
}


def _guard_immutable_update(mapper, connection, target) -> None:
    """Listener `before_update`: si algun campo fuera de `_PREDICTION_MUTABLE_FIELDS` cambio,
    aborta el UPDATE. Se registra sobre `Prediction` y `ProductPrediction` (ver mas abajo)."""
    state = inspect(target)
    for attr in state.attrs:
        if attr.key in _PREDICTION_MUTABLE_FIELDS:
            continue
        if attr.history.has_changes():
            raise ImmutabilityError(
                f"{target.__class__.__name__}(id={target.id}): intento de modificar el campo "
                f"inmutable '{attr.key}' tras su creacion. Si el sistema cambio de opinion, "
                "crea una prediccion NUEVA en vez de editar esta."
            )


event.listen(Prediction, "before_update", _guard_immutable_update)
event.listen(ProductPrediction, "before_update", _guard_immutable_update)


# Analysis no tiene ningun campo mutable: cualquier UPDATE se rechaza.
def _guard_analysis_immutable(mapper, connection, target) -> None:
    state = inspect(target)
    for attr in state.attrs:
        if attr.history.has_changes():
            raise ImmutabilityError(
                f"Analysis(id={target.id}): los analisis son inmutables por completo tras su "
                f"creacion (campo '{attr.key}' modificado). Genera un Analysis nuevo."
            )


event.listen(Analysis, "before_update", _guard_analysis_immutable)


def init_db() -> None:
    """Crea las tablas si no existen (util para SQLite en Fase 1, tests con motor en memoria,
    e instalaciones nuevas). La evolucion del esquema en una base de datos YA poblada -anadir
    columnas, etc.- se gestiona con Alembic (`alembic upgrade head`), no aqui: dos sistemas de
    migracion a la vez es peor que uno solo, incluso si el otro era mas simple."""
    Base.metadata.create_all(engine)
