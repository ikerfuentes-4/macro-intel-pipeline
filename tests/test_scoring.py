"""Tests de la formula de Brier score y calibracion (Master Build Prompt, seccion 8/13)."""
from __future__ import annotations

from persistence.scoring import brier_score, compute_scoring


def test_brier_score_perfect_prediction_is_zero():
    assert brier_score(probabilidad=1.0, cumplida=True) == 0.0
    assert brier_score(probabilidad=0.0, cumplida=False) == 0.0


def test_brier_score_worst_prediction_is_one():
    assert brier_score(probabilidad=1.0, cumplida=False) == 1.0
    assert brier_score(probabilidad=0.0, cumplida=True) == 1.0


def test_brier_score_known_value():
    # (0.7 - 1)^2 = 0.09
    assert round(brier_score(probabilidad=0.7, cumplida=True), 4) == 0.09


def test_compute_scoring_excludes_missing_probability_from_brier():
    resolved = [(0.6, True), (None, False), (0.4, False)]
    result = compute_scoring(resolved)
    assert result["predicciones_sin_probabilidad_registrada"] == 1
    assert result["brier_score_medio"] is not None


def test_compute_scoring_small_sample_flag():
    resolved = [(0.6, True)] * 5
    result = compute_scoring(resolved)
    assert result["muestra_pequena"] is True

    resolved_large = [(0.6, True)] * 40
    result_large = compute_scoring(resolved_large)
    assert result_large["muestra_pequena"] is False
