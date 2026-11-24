"""Evaluation metrics use synthetic fixtures exclusively in this test module."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.evaluation.engine import EvaluationError, EvaluationSample, evaluate_samples


def test_binary_metrics_and_calibration() -> None:
    samples = [
        EvaluationSample(90, 1, cell_id="a"),
        EvaluationSample(70, 1, cell_id="a"),
        EvaluationSample(60, 0, cell_id="b"),
        EvaluationSample(10, 0, cell_id="b"),
    ]
    result = evaluate_samples(samples, threshold=65)
    assert result["status"] == "COMPLETED"
    metrics = result["metrics"]
    assert metrics["true_positives"] == 2
    assert metrics["false_positives"] == 0
    assert metrics["true_negatives"] == 2
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1"] == 1.0
    assert metrics["false_positive_rate"] == 0.0
    assert metrics["roc_auc"] == 1.0
    assert metrics["brier_score"] is not None
    assert metrics["expected_calibration_error"] is not None


def test_insufficient_data_is_explicit() -> None:
    result = evaluate_samples([EvaluationSample(80, 1)])
    assert result["status"] == "INSUFFICIENT_DATA"
    assert result["metrics"]["roc_auc"] is None
    assert any("both classes" in warning.lower() for warning in result["warnings"])


def test_spatial_and_time_slices_are_reported() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    samples = [
        EvaluationSample(90, 1, cell_id="a", observed_at=start),
        EvaluationSample(20, 0, cell_id="a", observed_at=start + timedelta(days=1)),
        EvaluationSample(80, 1, cell_id="b", observed_at=start + timedelta(days=2)),
        EvaluationSample(10, 0, cell_id="b", observed_at=start + timedelta(days=3)),
    ]
    result = evaluate_samples(
        samples, threshold=50, include_spatial=True, time_split=True
    )
    assert result["slices"]["spatial"]["group_count"] == 2
    assert result["slices"]["spatial"]["macro_f1"] == 1.0
    assert result["slices"]["time_split"]["early_count"] == 2
    assert result["slices"]["time_split"]["late_count"] == 2


def test_invalid_sample_scores_are_rejected() -> None:
    with pytest.raises(EvaluationError):
        EvaluationSample(101, 1)
    with pytest.raises(EvaluationError):
        EvaluationSample(50, 2)


def test_tied_scores_use_average_ranks_and_spatial_counts_are_explicit() -> None:
    result = evaluate_samples(
        [
            EvaluationSample(50, 1, cell_id="a"),
            EvaluationSample(50, 0, cell_id="a"),
            EvaluationSample(50, 1, cell_id="b"),
            EvaluationSample(50, 0, cell_id="b"),
        ],
        threshold=50,
        include_spatial=True,
    )
    assert result["metrics"]["roc_auc"] == 0.5
    assert result["slices"]["spatial"]["groups_with_positive_and_negative"] == 2
    assert result["slices"]["spatial"]["groups_with_defined_f1"] == 2
