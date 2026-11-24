"""Diagnostic audit of the existing risk model and evaluation pipeline."""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from datetime import timedelta
from itertools import combinations

import h3

from app.core.config import Settings
from app.risk.config import FACTOR_KEYS, RiskConfig
from app.risk.engine import RiskEngine, RiskQuery
from app.validation.risk import (
    _close_session,
    _make_isolated_session,
    _parse,
    _ranking_metrics,
    _spearman,
    run_risk_backtest,
)


def _score_stats(values: list[float]) -> dict:
    if not values:
        return {"count": 0}
    ordered = sorted(values)
    return {
        "count": len(values),
        "min": round(min(values), 4),
        "mean": round(statistics.fmean(values), 4),
        "median": round(statistics.median(values), 4),
        "max": round(max(values), 4),
        "unique_scores": len({round(value, 4) for value in values}),
        "zero_share": round(sum(1 for value in values if value == 0) / len(values), 6),
    }


def _factor_label_spearman(pairs: list[tuple[float, int]]) -> float | None:
    if len(pairs) < 5:
        return None
    first = {str(index): value for index, (value, _label) in enumerate(pairs)}
    second = {str(index): float(label) for index, (_value, label) in enumerate(pairs)}
    return _spearman(first, second)


def _factor_redundancy(samples: dict[str, list[tuple[float, int]]]) -> list[dict]:
    result = []
    for first, second in combinations(sorted(samples), 2):
        by_index_a = {index: value for index, (value, _label) in enumerate(samples[first])}
        by_index_b = {index: value for index, (value, _label) in enumerate(samples[second])}
        cells = sorted(set(by_index_a) & set(by_index_b))
        if len(cells) < 10:
            continue
        value = _spearman(
            {str(index): by_index_a[index] for index in cells},
            {str(index): by_index_b[index] for index in cells},
        )
        if value is not None:
            result.append(
                {
                    "factor_a": first,
                    "factor_b": second,
                    "spearman": value,
                    "observation": (
                        "strong redundancy"
                        if abs(value) >= 0.9
                        else "moderate redundancy"
                        if abs(value) >= 0.7
                        else "weak redundancy"
                    ),
                }
            )
    result.sort(key=lambda item: -abs(item["spearman"]))
    return result


def run_diagnostic_audit(
    records: list[dict],
    *,
    settings: Settings,
    config: RiskConfig,
    dataset_key: str,
    bbox: tuple[float, float, float, float],
    base_result: dict | None = None,
) -> dict:
    if not records:
        raise ValueError("No validated records are available.")
    base = base_result or run_risk_backtest(
        records,
        settings=settings,
        config=config,
        dataset_key=dataset_key,
        bbox=bbox,
        include_sensitivity=False,
        include_cell_data=True,
    )
    start = min(_parse(record["observed_at"]) for record in records)
    end = max(_parse(record["observed_at"]) for record in records)
    origin = start + timedelta(hours=settings.validation_history_hours)
    target = timedelta(hours=settings.validation_target_hours)
    session = _make_isolated_session(records, dataset_key)
    factor_values: dict[str, list[tuple[float, int]]] = defaultdict(list)
    factor_available = Counter()
    factor_observations = Counter()
    band_counts = Counter()
    score_values: list[float] = []
    fold_rows: list[dict] = []
    try:
        while origin + target <= end and len(fold_rows) < settings.validation_max_folds:
            history_start = origin - timedelta(hours=settings.validation_history_hours)
            history = [
                record
                for record in records
                if history_start <= _parse(record["observed_at"]) < origin
            ]
            future = [
                record
                for record in records
                if origin < _parse(record["observed_at"]) <= origin + target
            ]
            if not history or not future:
                origin += target
                continue
            computation = RiskEngine(session, config).compute(
                RiskQuery(
                    resolution=settings.validation_resolution,
                    window_hours=settings.validation_target_hours,
                    bbox=bbox,
                    limit=config.max_cells,
                    as_of=origin,
                )
            )
            target_by_cell: dict[str, int] = defaultdict(int)
            for record in future:
                target_by_cell[
                    h3.latlng_to_cell(
                        record["latitude"],
                        record["longitude"],
                        settings.validation_resolution,
                    )
                ] += 1
            labels = {cell: 1 if count else 0 for cell, count in target_by_cell.items()}
            for cell in computation.cells:
                label = labels.get(cell.h3_cell_id, 0)
                score_values.append(cell.risk_score)
                band_counts[cell.risk_category] += 1
                for factor in cell.factors:
                    factor_observations[factor.key] += 1
                    if factor.available and factor.normalized is not None:
                        factor_available[factor.key] += 1
                        factor_values[factor.key].append((factor.normalized, label))
            fold_rows.append(
                {
                    "origin": origin.isoformat(),
                    "risk_cell_count": len(computation.cells),
                    "future_activity_cells": len(target_by_cell),
                }
            )
            origin += target
    finally:
        _close_session(session)

    factor_stats = {}
    for key in FACTOR_KEYS:
        observations = factor_observations.get(key, 0)
        available = factor_available.get(key, 0)
        pairs = factor_values.get(key, [])
        positive = [value for value, label in pairs if label == 1]
        negative = [value for value, label in pairs if label == 0]
        factor_stats[key] = {
            "observations": observations,
            "available_count": available,
            "availability_rate": round(available / observations, 6) if observations else 0.0,
            "mean_normalized": round(statistics.fmean(v for v, _ in pairs), 6)
            if pairs
            else None,
            "mean_when_target_active": round(statistics.fmean(positive), 6)
            if positive
            else None,
            "mean_when_target_inactive": round(statistics.fmean(negative), 6)
            if negative
            else None,
            "target_spearman": _factor_label_spearman(pairs),
            "zero_share": round(sum(1 for v, _ in pairs if v == 0) / len(pairs), 6)
            if pairs
            else None,
        }

    methods = base.get("methods", {})
    risk = methods.get("civicflow_risk", {})
    baseline_methods = {
        key: value for key, value in methods.items() if key.startswith("baseline_")
    }
    best_name, best = (
        max(baseline_methods.items(), key=lambda item: item[1].get("pr_auc") or -1)
        if baseline_methods
        else ("none", {})
    )
    total_observations = sum(factor_observations.values())
    infra_available = factor_available.get("infrastructure", 0)
    dependency_available = factor_available.get("dependency", 0)
    hypotheses = []
    if total_observations and infra_available == 0 and dependency_available == 0:
        hypotheses.append(
            {
                "severity": "high",
                "finding": (
                    "Infrastructure and dependency factors are unavailable "
                    "throughout the validation universe."
                ),
                "evidence": (
                    "Both factors have zero available observations; their "
                    "configured 20% weight is excluded and remaining weights "
                    "are renormalized. This validation cannot test their value."
                ),
            }
        )
    if risk.get("pr_auc") is not None and best.get("pr_auc") is not None:
        delta = round(float(best["pr_auc"]) - float(risk["pr_auc"]), 6)
        hypotheses.append(
            {
                "severity": "high" if delta > 0.01 else "low",
                "finding": (
                    f"{best_name} baseline PR-AUC is "
                    f"{'higher' if delta > 0 else 'not higher'} than CivicFlow "
                    f"by {abs(delta):.6f}."
                ),
                "evidence": "Same folds, labels, snapshots, and top-k for both methods.",
            }
        )
    dense_prevalence = (base.get("density") or {}).get("mean_label_prevalence")
    if dense_prevalence is not None and dense_prevalence >= 0.5:
        hypotheses.append(
            {
                "severity": "medium",
                "finding": "The evaluated target is dense at the selected H3 resolution.",
                "evidence": (
                    f"Mean target prevalence is {dense_prevalence:.6f}; any-activity "
                    "labels make persistence and recent-count baselines strong."
                ),
            }
        )
    redundancy = _factor_redundancy(factor_values)
    redundant = [item for item in redundancy if abs(item["spearman"]) >= 0.9]
    if redundant:
        hypotheses.append(
            {
                "severity": "medium",
                "finding": "Strongly redundant factor pairs were observed.",
                "evidence": "; ".join(
                    f"{item['factor_a']} vs {item['factor_b']} "
                    f"rho={item['spearman']:.4f}"
                    for item in redundant[:5]
                ),
            }
        )
    total_cells = sum(band_counts.values())
    high_share = (
        (band_counts.get("HIGH", 0) + band_counts.get("CRITICAL", 0)) / total_cells
        if total_cells
        else None
    )
    if high_share is not None and high_share >= 0.75:
        hypotheses.append(
            {
                "severity": "medium",
                "finding": "Risk-band saturation may reduce categorical usefulness.",
                "evidence": f"{high_share:.4f} of observed cells are HIGH or CRITICAL.",
            }
        )
    if not hypotheses:
        hypotheses.append(
            {
                "severity": "info",
                "finding": "No strong diagnostic signal was detected.",
                "evidence": "All diagnostic evidence is descriptive.",
            }
        )

    status_counts = Counter(record["status"] for record in records)
    category_counts = Counter(record["category"] for record in records)
    severity_counts = Counter(record["severity"] for record in records)
    complaint_counts = Counter(record["complaint_type"] for record in records)
    return {
        "status": "COMPLETED" if fold_rows else "INSUFFICIENT_DATA",
        "dataset_key": dataset_key,
        "dataset_start": start.isoformat(),
        "dataset_end": end.isoformat(),
        "origin_count": len(fold_rows),
        "folds": fold_rows,
        "data_quality": {
            "record_count": len(records),
            "category_counts": dict(category_counts),
            "severity_counts": dict(severity_counts),
            "status_counts": dict(status_counts),
            "complaint_type_counts": dict(complaint_counts),
            "descriptor_missing": sum(
                1 for record in records if not record.get("descriptor")
            ),
        },
        "factor_diagnostics": factor_stats,
        "factor_redundancy": redundancy[:20],
        "score_distribution": _score_stats(score_values),
        "band_distribution": {
            key: {
                "count": value,
                "share": round(value / total_cells, 6) if total_cells else 0,
            }
            for key, value in sorted(band_counts.items())
        },
        "baseline_comparison": {
            "civicflow": risk,
            "best_baseline": best_name,
            "best_baseline_metrics": best,
        },
        "hypotheses": hypotheses,
        "limitations": [
            "Factor associations and redundancy are descriptive, not causal.",
            "H3 cells and rolling origins are repeated observations, not independent samples.",
            "Infrastructure unavailable in the isolated validation database is not evidence "
            "that the factor is useless in production.",
            "No model configuration was changed by this diagnostic audit.",
        ],
    }
