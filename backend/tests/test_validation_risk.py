"""Leakage-safe risk backtest and ranking-metric tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import get_settings
from app.models import IncidentCategory, IncidentSeverity, IncidentStatus
from app.validation.risk import _ranking_metrics, run_risk_backtest


def _settings():
    return get_settings().model_copy(
        update={
            "validation_history_hours": 168,
            "validation_target_hours": 24,
            "validation_max_folds": 3,
            "validation_top_k": 5,
            "validation_resolution": 9,
        }
    )


def _records(days: int = 12) -> list[dict]:
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    records = []
    for day in range(days):
        for cell_index in range(12):
            # Deterministic uneven activity so both labels occur.
            count = 1 + ((day + cell_index) % 4)
            for item in range(count):
                observed = start + timedelta(
                    days=day, hours=(cell_index * 2 + item) % 24
                )
                records.append(
                    {
                        "external_id": f"r-{day}-{cell_index}-{item}",
                        "observed_at": observed.isoformat(),
                        "complaint_type": "Street Condition",
                        "descriptor": "fixture",
                        "latitude": 40.680 + cell_index * 0.002,
                        "longitude": -73.990 + (cell_index % 4) * 0.002,
                        "status": IncidentStatus.OPEN.value,
                        "category": IncidentCategory.ROADS.value,
                        "severity": (
                            IncidentSeverity.HIGH.value
                            if cell_index % 3 == 0
                            else IncidentSeverity.MEDIUM.value
                        ),
                    }
                )
    return records


def test_ranking_metrics_returns_correct_auc_and_pr_auc() -> None:
    labels = {"a": 1, "b": 0, "c": 1, "d": 0}
    perfect = _ranking_metrics(
        {"a": 4, "c": 3, "b": 2, "d": 1}, labels, top_k=2
    )
    inverted = _ranking_metrics(
        {"b": 4, "d": 3, "a": 2, "c": 1}, labels, top_k=2
    )
    tied = _ranking_metrics(
        {"a": 1, "b": 1, "c": 1, "d": 1}, labels, top_k=2
    )
    assert perfect["roc_auc"] == 1.0
    assert perfect["precision_at_k"] == 1.0
    assert inverted["roc_auc"] == 0.0
    assert tied["roc_auc"] == 0.5
    assert _ranking_metrics(
        {"a": 1, "b": 0}, {"a": 1, "b": 1}, top_k=1
    )["status"] == "INSUFFICIENT_DATA"


def test_backtest_runs_actual_engine_with_rolling_as_of_origins(db_session) -> None:
    from app.governance.service import resolve_risk_config

    settings = _settings()
    config = resolve_risk_config(db_session, settings)
    result = run_risk_backtest(
        _records(), settings=settings, config=config, dataset_key="fixture"
    )
    assert result["status"] == "COMPLETED"
    assert result["origin_count"] == 3
    assert set(result["methods"]) == {
        "civicflow_risk",
        "baseline_count",
        "baseline_recent",
        "baseline_weighted",
        "baseline_persistence",
    }
    for fold in result["folds"]:
        origin = datetime.fromisoformat(fold["origin"])
        target_start = datetime.fromisoformat(fold["target_start"])
        target_end = datetime.fromisoformat(fold["target_end"])
        assert target_start == origin
        assert target_end == origin + timedelta(hours=24)
        assert fold["metrics"]["civicflow_risk"]["cell_count"] > 0
        if fold["metrics"]["civicflow_risk"]["status"] == "COMPLETED":
            assert fold["metrics"]["civicflow_risk"]["top_k"] == 5
    assert result["sensitivity"] is not None
    assert result["sensitivity"]["main_resolution"] == 9


def test_backtest_reports_insufficient_data_without_folds(db_session) -> None:
    from app.governance.service import resolve_risk_config

    settings = _settings()
    config = resolve_risk_config(db_session, settings)
    result = run_risk_backtest(
        _records(days=2), settings=settings, config=config, dataset_key="fixture"
    )
    assert result["status"] == "INSUFFICIENT_DATA"
    assert result["folds"] == []
    assert result["methods"] == {}
    assert result["sensitivity"] is None


def test_backtest_reports_sparse_density_without_crashing(db_session) -> None:
    from app.governance.service import resolve_risk_config

    settings = _settings()
    config = resolve_risk_config(db_session, settings)
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    records = []
    for day in range(14):
        records.append(
            {
                "external_id": f"sparse-{day}",
                "observed_at": (start + timedelta(days=day, hours=12)).isoformat(),
                "complaint_type": "Rodent",
                "descriptor": "sparse fixture",
                "latitude": 40.690 + (day % 6) * 0.002,
                "longitude": -73.980,
                "status": IncidentStatus.OPEN.value,
                "category": IncidentCategory.SANITATION.value,
                "severity": IncidentSeverity.MEDIUM.value,
            }
        )
    result = run_risk_backtest(
        records, settings=settings, config=config, dataset_key="sparse-fixture"
    )
    assert result["status"] == "COMPLETED"
    assert result["density"]["classification"] == "SPARSE"
    assert result["density"]["mean_label_prevalence"] < 0.5
    assert all(fold["target_cell_count"] >= 1 for fold in result["folds"])
