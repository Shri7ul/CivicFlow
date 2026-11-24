"""Deterministic fold-level statistics used by the Phase 9 protocol."""

from __future__ import annotations

from app.validation.stats import (
    aggregate_fold_metric,
    bootstrap_mean_ci,
    mean,
    paired_comparison,
)


def test_bootstrap_is_deterministic_and_brackets_the_mean() -> None:
    values = [0.81, 0.84, 0.79, 0.88, 0.90, 0.86]
    first = bootstrap_mean_ci(values)
    second = bootstrap_mean_ci(values)
    assert first == second
    assert first["n"] == 6
    assert first["seed"] == 20261124
    assert first["ci_low"] <= first["mean"] <= first["ci_high"]
    assert first["note"].startswith("Percentile bootstrap")


def test_bootstrap_and_mean_handle_empty_input_explicitly() -> None:
    empty = bootstrap_mean_ci([])
    assert empty == {"n": 0, "mean": None, "ci_low": None, "ci_high": None}
    assert mean([]) is None
    assert mean([1.0, 2.0]) == 1.5


def test_paired_comparison_reports_wins_and_sign_test() -> None:
    positive = paired_comparison([0.02, 0.01, 0.03, 0.04, 0.02, 0.01, 0.03, 0.02])
    assert positive["n"] == 8
    assert positive["wins"] == 8
    assert positive["losses"] == 0
    assert positive["ci_low"] > 0
    assert positive["sign_test_p"] == round(2 * 1 / (2**8), 6)
    assert positive["bootstrap_probability_positive"] == 1.0

    mixed = paired_comparison([0.01, -0.01, 0.01, -0.01])
    assert mixed["wins"] == 2
    assert mixed["losses"] == 2
    assert mixed["ci_low"] < 0 < mixed["ci_high"]
    assert mixed["sign_test_p"] == 1.0


def test_paired_comparison_with_ties_avoids_false_certainty() -> None:
    ties = paired_comparison([0.0, 0.0, 0.0])
    assert ties["ties"] == 3
    assert ties["sign_test_p"] is None
    assert ties["mean_delta"] == 0.0
    assert paired_comparison([])["mean_delta"] is None


def test_aggregate_fold_metric_skips_missing_folds() -> None:
    results = [
        {"methods": {"civicflow_risk": {"pr_auc": 0.8}}},
        {"methods": {"civicflow_risk": {}}},
        {"methods": {}},
        {"methods": {"civicflow_risk": {"pr_auc": 0.9}}},
    ]
    assert aggregate_fold_metric(results) == [0.8, 0.9]