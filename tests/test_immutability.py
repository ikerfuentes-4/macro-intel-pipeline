"""Tests de inmutabilidad y anti-look-ahead-bias (Master Build Prompt, Principio 2 y secciones
11/21). Usan un motor SQLite en memoria aislado -no tocan la base de datos real del proyecto.
"""
from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from persistence.db import Analysis, Base, ImmutabilityError, Prediction


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _make_analysis(session) -> Analysis:
    analysis = Analysis(
        evento_id="TEST-1",
        consensus_cluster_id="cluster-1",
        causa_raiz="causa de prueba",
        raw_json="{}",
        nivel_confianza=0.5,
        model_version="test:v1",
        prompt_version="test-v1",
        information_cutoff=dt.datetime.utcnow(),
    )
    session.add(analysis)
    session.commit()
    return analysis


def test_prediction_content_field_is_immutable(db_session):
    """Modificar un campo de contenido (enunciado, ticker, umbral...) tras la creacion debe
    fallar -- si el sistema cambia de opinion, debe crear una prediccion NUEVA, nunca editar."""
    analysis = _make_analysis(db_session)
    pred = Prediction(
        analysis_id=analysis.id,
        enunciado="Enunciado original",
        ticker_validacion="CL=F",
        comparador=">",
        valor_umbral=90.0,
        fecha_limite_revision="2027-01-01",
        probabilidad=0.6,
        status="PENDIENTE",
    )
    db_session.add(pred)
    db_session.commit()

    pred.enunciado = "Intento de reescribir la prediccion despues de creada"
    with pytest.raises(ImmutabilityError):
        db_session.commit()
    db_session.rollback()


def test_prediction_resolution_fields_are_mutable(db_session):
    """Los campos que rellena la Resolution Engine (status, resultado_valor_real, evaluado_en)
    SI deben poder actualizarse -- si esto fallara, no se podria evaluar ninguna prediccion."""
    analysis = _make_analysis(db_session)
    pred = Prediction(
        analysis_id=analysis.id,
        enunciado="Enunciado",
        ticker_validacion="CL=F",
        comparador=">",
        valor_umbral=90.0,
        fecha_limite_revision="2027-01-01",
        probabilidad=0.6,
        status="PENDIENTE",
    )
    db_session.add(pred)
    db_session.commit()

    pred.status = "CUMPLIDA"
    pred.resultado_valor_real = 95.0
    pred.evaluado_en = dt.datetime.utcnow()
    db_session.commit()  # no debe lanzar ImmutabilityError

    assert pred.status == "CUMPLIDA"


def test_analysis_is_fully_immutable(db_session):
    """`Analysis` no tiene ningun campo de resolucion (eso vive en `Prediction`): CUALQUIER
    UPDATE sobre un Analysis ya creado debe rechazarse."""
    analysis = _make_analysis(db_session)
    analysis.causa_raiz = "Intento de reescribir el analisis"
    with pytest.raises(ImmutabilityError):
        db_session.commit()
    db_session.rollback()


def test_evaluation_query_excludes_predictions_before_horizon(db_session):
    """Anti-look-ahead-bias: la condicion de la query de evaluacion (misma que usa
    `persistence.track_record.evaluate_due_predictions`) nunca debe incluir una prediccion cuyo
    horizonte comprometido (`fecha_limite_revision`) todavia no ha llegado -- eso equivaldria a
    usar el paso del tiempo para 'espiar' un resultado antes de lo prometido en la creacion."""
    analysis = _make_analysis(db_session)
    tomorrow = (dt.date.today() + dt.timedelta(days=1)).isoformat()
    yesterday = (dt.date.today() - dt.timedelta(days=1)).isoformat()

    future_pred = Prediction(
        analysis_id=analysis.id, enunciado="futuro", ticker_validacion="CL=F",
        comparador=">", valor_umbral=1, fecha_limite_revision=tomorrow, status="PENDIENTE",
    )
    past_pred = Prediction(
        analysis_id=analysis.id, enunciado="pasado", ticker_validacion="CL=F",
        comparador=">", valor_umbral=1, fecha_limite_revision=yesterday, status="PENDIENTE",
    )
    db_session.add_all([future_pred, past_pred])
    db_session.commit()

    today = dt.date.today().isoformat()
    due = db_session.query(Prediction).filter(
        Prediction.status == "PENDIENTE", Prediction.fecha_limite_revision <= today
    ).all()

    due_ids = {p.id for p in due}
    assert past_pred.id in due_ids
    assert future_pred.id not in due_ids
