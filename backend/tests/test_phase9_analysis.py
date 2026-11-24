"""Phase 9 diagnostic audit, ablation, robustness, and curation tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.core.config import get_settings
from app.governance.service import resolve_risk_config
from app.models import IncidentCategory, IncidentSeverity, IncidentStatus
from app.models.enums import ValidationEvidenceKind, ValidationStatus
from app.risk.config import FACTOR_KEYS
from app.validation.ablations import (
    ablation_variants,
    run_ablation_suite,
    variant_config,
)
from app.validation.diagnostics import run_diagnostic_audit
from app.validation.research import (
    _curate_dataset,
    _select_candidate,
    dataset_bbox,
)
from app.validation.robustness import run_robustness_suite

BBOX = (40.680, -73.990, 40.710, -73.950)


def _settings():
    return get_settings().model_copy(
        update={
            "validation_history_hours": 72,
            "validation_target_hours": 24,
            "validation_max_folds": 2,
            "validation_top_k": 5,
            "validation_resolution": 9,
        }
    )


def _records(days: int = 10) -> list[dict]:
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    records = []
    for day in range(days):
        for cell_index in range(10):
            # Half the grid is sparse so both label classes exist per target window.
            if cell_index >= 5 and (day + cell_index) % 3 != 0:
                continue
            count = 1 + ((day + cell_index) % 3)
            for item in range(count):
                observed = start + timedelta(
                    days=day, hours=(cell_index * 2 + item) % 24
                )
                records.append(
                    {
                        "external_id": f"p9-{day}-{cell_index}-{item}",
                        "observed_at": observed.isoformat(),
                        "complaint_type": "Street Condition",
                        "descriptor": "fixture",
                        "latitude": 40.680 + cell_index * 0.002,
                        "longitude": -73.990 + (cell_index % 4) * 0.002,
                        "status": IncidentStatus.OPEN.value,
                        "category": IncidentCategory.ROADS.value,
                        "severity": IncidentSeverity.MEDIUM.value,
                    }
                )
    return records


def _run_base(db_session, settings, config) -> dict:
    from app.validation.risk import run_risk_backtest

    base = run_risk_backtest(
        _records(),
        settings=settings,
        config=config,
        dataset_key="fixture",
        bbox=BBOX,
        include_sensitivity=False,
        include_cell_data=True,
    )
    assert base["status"] == "COMPLETED"
    return base


def test_ablation_variants_cover_every_registered_factor(db_session) -> None:
    config = resolve_risk_config(db_session, _settings())

    variants = ablation_variants(config)
    keys = [item["key"] for item in variants]
    assert keys[0] == "full"
    assert len(keys) == 1 + 2 * len(FACTOR_KEYS)
    for factor in FACTOR_KEYS:
        assert f"drop_{factor}" in keys
        assert f"only_{factor}" in keys
    assert len(set(keys)) == len(keys)


def test_variant_config_renormalizes_and_never_invents_factors(db_session) -> None:
    config = resolve_risk_config(db_session, _settings())
    dropped = variant_config(
        config, {"removed": ["severity"], "only": []}, "drop_severity"
    )
    assert dropped.weights["severity"] == 0.0
    assert pytest.approx(sum(dropped.weights.values()), abs=1e-9) == 1.0
    assert set(dropped.weights) == set(FACTOR_KEYS)
    assert dropped.model_version.endswith("-drop_severity")
    assert dropped.config_hash != config.config_hash
    with pytest.raises(ValueError):
        variant_config(
            config, {"removed": list(FACTOR_KEYS), "only": []}, "empty"
        )


def test_diagnostic_audit_reports_unavailable_factors_and_hypotheses(
    db_session,
) -> None:
    settings = _settings()
    config = resolve_risk_config(db_session, settings)
    base = _run_base(db_session, settings, config)
    result = run_diagnostic_audit(
        _records(),
        settings=settings,
        config=config,
        dataset_key="fixture",
        bbox=BBOX,
        base_result=base,
    )
    assert result["status"] == "COMPLETED"
    assert set(result["factor_diagnostics"]) == set(FACTOR_KEYS)
    infrastructure = result["factor_diagnostics"]["infrastructure"]
    assert infrastructure["available_count"] == 0
    assert infrastructure["availability_rate"] == 0.0
    assert result["hypotheses"]
    assert any(
        "Infrastructure and dependency factors are unavailable" in item["finding"]
        for item in result["hypotheses"]
    )
    assert result["band_distribution"]
    assert result["score_distribution"]["count"] > 0
    assert result["data_quality"]["record_count"] == len(_records())


def test_ablation_suite_keeps_folds_comparable(db_session) -> None:
    settings = _settings()
    config = resolve_risk_config(db_session, settings)
    base = _run_base(db_session, settings, config)
    result = run_ablation_suite(
        _records(),
        settings=settings,
        config=config,
        dataset_key="fixture",
        bbox=BBOX,
        base_result=base,
    )
    assert result["status"] == "COMPLETED"
    assert len(result["variants"]) == 1 + 2 * len(FACTOR_KEYS)
    full = next(item for item in result["variants"] if item["variant_key"] == "full")
    assert full["delta_pr_auc"]["mean_delta"] == 0.0
    assert full["config_hash"] == base["config_hash"]
    for item in result["variants"]:
        assert item["weights"]
        assert pytest.approx(sum(item["weights"].values()), abs=1e-9) == 1.0
        assert item["delta_pr_auc"]["n"] <= len(base["folds"])
    assert result["best_variant"]
    assert result["interpretation"]
    assert result["runtime_ms"] >= 0


def test_robustness_suite_reports_bounded_variants(db_session) -> None:
    settings = _settings()
    config = resolve_risk_config(db_session, settings)
    base = _run_base(db_session, settings, config)
    result = run_robustness_suite(
        _records(),
        settings=settings,
        config=config,
        dataset_key="fixture",
        bbox=BBOX,
        base_result=base,
    )
    assert result["status"] == "COMPLETED"
    resolutions = [item["resolution"] for item in result["resolution"]]
    assert resolutions == sorted(set(resolutions))
    assert set(resolutions).issubset({7, 8, 9})
    assert [item["target_hours"] for item in result["target_window"]]
    assert result["record_thinning"]
    assert set(result["density_strata"]) >= {"dense", "sparse", "note"}
    assert set(result["threshold_sensitivity"]["variants"]) == {
        "narrow",
        "default",
        "wide",
    }
    assert 0 <= result["missingness"]["descriptor_missing_rate"] <= 1
    assert result["limitations"]
    assert result["runtime_ms"] >= 0


def test_candidate_selection_requires_a_positive_development_delta() -> None:
    positive = {
        "variants": [
            {
                "variant_key": "drop_trend",
                "kind": "leave_one_out",
                "metrics": {"pr_auc": 0.9},
                "removed_factors": ["trend"],
                "weights": {"trend": 0.0},
                "delta_pr_auc": {"mean_delta": 0.01, "ci_low": -0.01},
            },
            {
                "variant_key": "drop_spatial",
                "kind": "leave_one_out",
                "metrics": {"pr_auc": 0.88},
                "removed_factors": ["spatial"],
                "weights": {"spatial": 0.0},
                "delta_pr_auc": {"mean_delta": -0.02},
            },
        ]
    }
    selected = _select_candidate(positive, "dev")
    assert selected["candidate_key"] == "drop_trend"
    assert selected["removed_factors"] == ["trend"]
    assert selected["selection_dataset"] == "dev"
    assert "development dataset" in selected["rule"]

    negative = {"variants": [positive["variants"][1]]}
    rejected = _select_candidate(negative, "dev")
    assert rejected["candidate_key"] is None
    assert "No leave-one-out variant improved" in rejected["reason"]

    empty = _select_candidate({}, "dev")
    assert empty["candidate_key"] is None
    assert empty["selection_statistics"] is None


def test_single_factor_variants_are_not_eligible_for_selection() -> None:
    result = _select_candidate(
        {
            "variants": [
                {
                    "variant_key": "only_density",
                    "kind": "single_factor",
                    "metrics": {"pr_auc": 0.95},
                    "removed_factors": [],
                    "weights": {"density": 1.0},
                    "delta_pr_auc": {"mean_delta": 0.07},
                }
            ]
        },
        "dev",
    )
    assert result["candidate_key"] is None


def test_dataset_bbox_uses_metadata_then_default() -> None:
    dataset = SimpleNamespace(dataset_metadata={})
    assert dataset_bbox(dataset, {"bbox": [1, 2, 3, 4]}) == (1.0, 2.0, 3.0, 4.0)
    assert dataset_bbox(dataset, {"query": {"bbox": [5, 6, 7, 8]}}) == (
        5.0,
        6.0,
        7.0,
        8.0,
    )
    assert dataset_bbox(dataset, {})[0] == 40.68
    with pytest.raises(Exception) as error:
        dataset_bbox(dataset, {"bbox": [1, 2]})
    assert getattr(error.value, "code", "") == "dataset_bbox_invalid"


def _experiment(
    *,
    experiment_type: str,
    variant_key: str,
    metrics: dict,
    status: ValidationStatus = ValidationStatus.COMPLETED,
    findings: list[str] | None = None,
    limitations: list[str] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        experiment_type=SimpleNamespace(value=experiment_type),
        variant_key=variant_key,
        status=status,
        metrics=metrics,
        findings=findings or [],
        limitations=limitations or [],
        name=f"{experiment_type} {variant_key}",
        completed_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
        model_version="risk-v1",
        config_hash="a" * 64,
        split_method="rolling_origin_temporal_holdout",
        evidence_kind=ValidationEvidenceKind.EMPIRICAL_OBSERVATIONAL,
    )


def test_curation_projects_persisted_rows_without_recomputing() -> None:
    dataset = SimpleNamespace(
        id=uuid.uuid4(),
        dataset_key="nyc311-brooklyn-2025q1",
        name="Fixture dataset",
        region="fixture region",
        period_start=datetime(2025, 1, 1, tzinfo=timezone.utc),
        period_end=datetime(2025, 3, 31, tzinfo=timezone.utc),
        record_count=10,
        snapshot_sha256="b" * 64,
        schema_version="nyc311-normalized-v1",
    )
    methods = {
        "civicflow_risk": {"pr_auc": 0.8, "roc_auc": 0.7, "precision_at_k": 0.5},
        "baseline_count": {"pr_auc": 0.85, "roc_auc": 0.75},
        "baseline_recent": {"pr_auc": 0.7, "roc_auc": 0.65},
    }
    experiments = {
        ("RISK_BACKTEST", "full"): _experiment(
            experiment_type="RISK_BACKTEST",
            variant_key="full",
            metrics={
                "status": "COMPLETED",
                "methods": methods,
                "statistics": {
                    "fold_intervals": {"pr_auc": {"n": 2, "mean": 0.8}},
                    "paired_pr_auc_vs_baselines": {
                        "baseline_count": {"mean_delta": -0.05}
                    },
                },
                "density": {"classification": "DENSE"},
            },
            findings=["fixture finding"],
            limitations=["fixture limitation"],
        ),
        ("RISK_DIAGNOSTIC", "factor_audit"): _experiment(
            experiment_type="RISK_DIAGNOSTIC",
            variant_key="factor_audit",
            metrics={"hypotheses": [{"severity": "high", "finding": "x"}]},
        ),
        ("RISK_ABLATION", "factor_ablation"): _experiment(
            experiment_type="RISK_ABLATION",
            variant_key="factor_ablation",
            metrics={
                "variants": [
                    {
                        "variant_key": "drop_trend",
                        "kind": "leave_one_out",
                        "removed_factors": ["trend"],
                        "only_factors": [],
                        "metrics": {"pr_auc": 0.81},
                        "delta_pr_auc": {"mean_delta": 0.01},
                    }
                ],
                "best_variant": "drop_trend",
                "best_minus_full_pr_auc": 0.01,
                "interpretation": "fixture",
            },
        ),
        ("RISK_ABLATION", "candidate_drop_trend"): _experiment(
            experiment_type="RISK_ABLATION",
            variant_key="candidate_drop_trend",
            metrics={
                "sample": "external_holdout",
                "candidate_key": "drop_trend",
                "activated": False,
                "delta_pr_auc": {"mean_delta": 0.002, "ci_low": -0.01},
            },
        ),
        ("RISK_ABLATION", "candidate_drop_severity"): _experiment(
            experiment_type="RISK_ABLATION",
            variant_key="candidate_drop_severity",
            metrics={"sample": "external_holdout"},
            status=ValidationStatus.FAILED,
        ),
    }
    curated = _curate_dataset(dataset, experiments)  # type: ignore[arg-type]
    assert curated["role"] == "development"
    assert curated["risk"]["pr_auc"] == 0.8
    assert curated["best_baseline"]["method"] == "baseline_count"
    assert curated["baselines"][0]["method"] == "baseline_count"
    assert curated["diagnostics"]["hypotheses"][0]["finding"] == "x"
    assert curated["ablation"]["best_variant"] == "drop_trend"
    # Failed candidate rows are audit records, never evidence.
    assert len(curated["candidates"]) == 1
    assert curated["candidates"][0]["sample"] == "external_holdout"
    assert curated["candidates"][0]["activated"] is False
    assert "fixture limitation" in curated["limitations"]
    assert curated["findings"] == ["fixture finding"]
    assert curated["experiments"]["RISK_BACKTEST:full"]["status"] == "COMPLETED"