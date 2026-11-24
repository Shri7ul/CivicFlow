"""Phase 9 report composition tests (persisted-record projection only)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.validation.research_report import (
    _executive_summary,
    _model_changes,
    build_research_report,
)


def _dataset(**overrides) -> dict:
    dataset = {
        "dataset_key": "nyc311-brooklyn-2025q1",
        "role": "development",
        "region": "Brooklyn",
        "period_start": "2025-01-01T00:00:00+00:00",
        "period_end": "2025-03-31T23:59:59+00:00",
        "record_count": 5102,
        "model_version": "risk-v1",
        "config_hash": "a" * 64,
        "risk": {"pr_auc": 0.88, "roc_auc": 0.72, "fold_count": 8},
        "best_baseline": {
            "method": "baseline_recent",
            "pr_auc": 0.88,
            "roc_auc": 0.7,
        },
        "density": {"classification": "DENSE"},
        "diagnostics": {"factor_diagnostics": {}, "hypotheses": []},
        "ablation": {"variants": [], "best_variant": None},
        "robustness": {},
        "statistics": {},
        "candidates": [],
        "limitations": ["complaint activity is not hazard ground truth"],
        "evidence_kind": "EMPIRICAL_OBSERVATIONAL",
        "dataset_id": "00000000-0000-0000-0000-000000000000",
    }
    dataset.update(overrides)
    return dataset


def test_executive_summary_states_the_direction_of_each_comparison() -> None:
    winning = _dataset()
    winning["risk"] = {"pr_auc": 0.95, "roc_auc": 0.8}
    lines = _executive_summary([winning], None)
    assert any("is 0.070000 above the strongest baseline" in line for line in lines)
    assert any("ranks above every baseline on 1 of 1" in line for line in lines)

    losing = _dataset()
    lines = _executive_summary([losing], None)
    assert any("is 0.000000 below" in line or "below the strongest baseline" in line for line in lines)
    assert any("ranks above every baseline on 0 of 1" in line for line in lines)
    assert any("no model configuration was activated" in line for line in lines)


def test_executive_summary_reports_absent_evidence_as_insufficient() -> None:
    missing = _dataset()
    missing["risk"] = {"pr_auc": None, "roc_auc": None}
    lines = _executive_summary([missing], None)
    assert any("insufficient evidence" in line for line in lines)
    assert _executive_summary([], None) == [
        "No Phase 9 experiment records are persisted, so no finding is reported."
    ]


def test_model_changes_never_claims_activation() -> None:
    base = _dataset()
    no_selection = _model_changes([base], None)
    assert no_selection["activated"] is False
    assert no_selection["activation_state"] == "NOT_ACTIVATED"
    assert "No model change was proposed" in no_selection["decision"]

    selected = {
        "candidate_key": "drop_trend",
        "selection_dataset": "nyc311-brooklyn-2025q1",
        "rule": "rule",
        "reason": "reason",
    }
    unproven = _model_changes([base], selected)
    assert "no candidate evaluation is persisted" in unproven["decision"]
    assert unproven["selected_candidate"] == "drop_trend"

    candidate = {
        "candidate_key": "drop_trend",
        "sample": "external_holdout",
        "dataset_key": "nyc311-manhattan-2025q2",
        "delta_pr_auc": {"mean_delta": 0.01, "ci_low": 0.002, "ci_high": 0.02},
        "activated": False,
    }
    improved = _model_changes([_dataset(candidates=[candidate])], selected)
    assert "All 1 external holdouts" in improved["decision"]
    assert "governed model" in improved["decision"]
    assert improved["activated"] is False

    second = dict(candidate)
    second["dataset_key"] = "nyc311-brooklyn-2025q2"
    second["delta_pr_auc"] = {"mean_delta": -0.003, "ci_low": -0.01, "ci_high": 0.002}
    mixed = _model_changes([_dataset(candidates=[candidate, second])], selected)
    assert "1 of 2 external holdouts" in mixed["decision"]
    assert "mixed evidence" in mixed["decision"]
    assert "retained unchanged" in mixed["decision"]

    flat = dict(candidate)
    flat["delta_pr_auc"] = {"mean_delta": 0.001, "ci_low": -0.01, "ci_high": 0.01}
    retained = _model_changes([_dataset(candidates=[flat])], selected)
    assert "registered model is retained unchanged" in retained["decision"]


def test_report_on_empty_database_is_honest(db_session: Session) -> None:
    report = build_research_report(db_session)
    assert report["dataset_count"] == 0
    assert report["datasets"] == []
    assert report["comparison"] == []
    assert report["phase8_findings"] is None
    assert report["model_changes"]["activated"] is False
    assert report["source"] == "persisted validation_experiments rows"
    assert report["protocol_key"] == "phase9-risk-diagnosis-v1"
    for section in (
        "executive_summary",
        "diagnostic_audit",
        "dataset_quality",
        "methodology",
        "split_methodology",
        "baselines",
        "ablation",
        "geographic",
        "temporal",
        "sensitivity",
        "statistics",
        "model_changes",
        "limitations",
        "reproducibility",
        "future_research",
    ):
        assert section in report
    assert report["executive_summary"] == [
        "No Phase 9 experiment records are persisted, so no finding is reported."
    ]