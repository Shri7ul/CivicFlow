"""Robustness, sensitivity, density, and ranking-stability diagnostics."""

from __future__ import annotations

import hashlib
import statistics
import time
from dataclasses import replace

from app.core.config import Settings
from app.risk.config import RiskConfig
from app.validation.risk import _ranking_metrics, _spearman, _top_cells, run_risk_backtest


def _metric(result: dict) -> dict:
    return (result.get("methods") or {}).get("civicflow_risk", {})


def _cell_subset_metrics(result: dict, *, dense: bool) -> dict:
    """Average ranking metrics over fold-level density strata."""
    rows = []
    for fold in result.get("folds", []):
        cells = fold.get("cell_data") or {}
        counts = [row["history_count"] for row in cells.values()]
        if not counts:
            continue
        cutoff = statistics.median(counts)
        labels: dict[str, int] = {}
        scores: dict[str, float] = {}
        for cell, row in cells.items():
            selected = (
                row["history_count"] >= cutoff
                if dense
                else row["history_count"] < cutoff
            )
            if selected:
                labels[cell] = row["label"]
                scores[cell] = row["scores"]["civicflow_risk"]
        if labels:
            rows.append(_ranking_metrics(scores, labels, top_k=10))
    if not rows:
        return {"status": "INSUFFICIENT_DATA", "fold_count": 0}
    summary = {}
    for key in ("precision_at_k", "recall_at_k", "roc_auc", "pr_auc"):
        values = [row[key] for row in rows if row.get(key) is not None]
        summary[key] = round(statistics.fmean(values), 6) if values else None
    return {
        "status": "COMPLETED",
        "fold_count": len(rows),
        "mean_positive_cells": round(
            statistics.fmean(row.get("positive_count", 0) for row in rows), 3
        ),
        **summary,
        "note": "Metrics are computed per fold and averaged; cells are not independent.",
    }


def _threshold_counts(records: list[dict], settings: Settings, config: RiskConfig,
                      dataset_key: str, bbox: tuple[float, float, float, float]) -> dict:
    from datetime import timedelta

    from app.risk.engine import RiskEngine, RiskQuery
    from app.validation.risk import _close_session, _make_isolated_session, _parse

    start = min(_parse(record["observed_at"]) for record in records)
    origin = start + timedelta(hours=settings.validation_history_hours)
    session = _make_isolated_session(records, dataset_key)
    try:
        variants = {}
        for name, factor in (("narrow", 0.9), ("default", 1.0), ("wide", 1.1)):
            thresholds = [min(99.0, value * factor) for value in config.thresholds]
            candidate = replace(
                config,
                threshold_low=thresholds[0],
                threshold_moderate=thresholds[1],
                threshold_high=thresholds[2],
                threshold_critical=thresholds[3],
            )
            computation = RiskEngine(session, candidate).compute(
                RiskQuery(
                    resolution=settings.validation_resolution,
                    window_hours=settings.validation_target_hours,
                    bbox=bbox,
                    limit=config.max_cells,
                    as_of=origin,
                )
            )
            counts: dict[str, int] = {}
            for cell in computation.cells:
                counts[cell.risk_category] = counts.get(cell.risk_category, 0) + 1
            variants[name] = {
                "thresholds": {
                    "low": thresholds[0],
                    "moderate": thresholds[1],
                    "high": thresholds[2],
                    "critical": thresholds[3],
                },
                "cell_counts": counts,
                "cell_total": len(computation.cells),
            }
        return {
            "origin": origin.isoformat(),
            "variants": variants,
            "note": "Ranking does not change with thresholds; only band labels change.",
        }
    finally:
        _close_session(session)


def _stability(base: dict, variant: dict) -> dict:
    base_folds = base.get("folds") or []
    variant_folds = variant.get("folds") or []
    comparisons = []
    for left, right in zip(base_folds, variant_folds):
        left_cells = {
            cell: row["scores"]["civicflow_risk"]
            for cell, row in (left.get("cell_data") or {}).items()
        }
        right_cells = {
            cell: row["scores"]["civicflow_risk"]
            for cell, row in (right.get("cell_data") or {}).items()
        }
        common = sorted(set(left_cells) & set(right_cells))
        if not common:
            continue
        comparisons.append(
            {
                "origin": left["origin"],
                "common_cells": len(common),
                "spearman": _spearman(
                    {cell: left_cells[cell] for cell in common},
                    {cell: right_cells[cell] for cell in common},
                ),
                "top20_jaccard": _jaccard(
                    _top_cells({cell: left_cells[cell] for cell in common}, 20),
                    _top_cells({cell: right_cells[cell] for cell in common}, 20),
                ),
            }
        )
    values = [row["spearman"] for row in comparisons if row["spearman"] is not None]
    jaccards = [row["top20_jaccard"] for row in comparisons]
    return {
        "fold_count": len(comparisons),
        "mean_spearman": round(statistics.fmean(values), 6) if values else None,
        "mean_top20_jaccard": round(statistics.fmean(jaccards), 6) if jaccards else None,
        "folds": comparisons,
    }


def _jaccard(first: set[str], second: set[str]) -> float:
    union = first | second
    return round(len(first & second) / len(union), 6) if union else 0.0


def _thinned(records: list[dict], fraction: float) -> list[dict]:
    threshold = int(fraction * 10_000)
    kept = []
    for record in records:
        digest = hashlib.sha256(record["external_id"].encode("utf-8")).hexdigest()
        if int(digest[:8], 16) % 10_000 < threshold:
            kept.append(record)
    return kept


def run_robustness_suite(
    records: list[dict],
    *,
    settings: Settings,
    config: RiskConfig,
    dataset_key: str,
    bbox: tuple[float, float, float, float],
    base_result: dict | None = None,
) -> dict:
    started = time.perf_counter()
    base = base_result or run_risk_backtest(
        records,
        settings=settings,
        config=config,
        dataset_key=dataset_key,
        bbox=bbox,
        include_sensitivity=False,
        include_cell_data=True,
    )
    sensitivity = base.get("sensitivity")
    resol = []
    for resolution in (7, 8, 9):
        if not config.min_resolution <= resolution <= config.max_resolution:
            continue
        candidate_settings = settings.model_copy(
            update={"validation_resolution": resolution}
        )
        result = run_risk_backtest(
            records,
            settings=candidate_settings,
            config=config,
            dataset_key=dataset_key,
            bbox=bbox,
            include_sensitivity=False,
            include_cell_data=True,
        )
        resol.append(
            {
                "resolution": resolution,
                "metrics": _metric(result),
                "cell_count": (result.get("density") or {}).get("mean_universe_cells"),
                "status": result.get("status"),
                "stability_vs_default": _stability(base, result),
            }
        )
    windows = []
    for hours in (72, 168, 336):
        if hours > config.max_window_hours:
            continue
        candidate_settings = settings.model_copy(
            update={
                "validation_target_hours": hours,
                "validation_history_hours": max(settings.validation_history_hours, 2 * hours),
            }
        )
        result = run_risk_backtest(
            records,
            settings=candidate_settings,
            config=config,
            dataset_key=dataset_key,
            bbox=bbox,
            include_sensitivity=False,
            include_cell_data=True,
        )
        windows.append(
            {
                "target_hours": hours,
                "metrics": _metric(result),
                "status": result.get("status"),
                "stability_vs_default": _stability(base, result),
            }
        )
    thinning = []
    for fraction in (0.5, 0.75):
        sample = _thinned(records, fraction)
        result = run_risk_backtest(
            sample,
            settings=settings,
            config=config,
            dataset_key=dataset_key,
            bbox=bbox,
            include_sensitivity=False,
        )
        thinning.append(
            {
                "retained_fraction": fraction,
                "retained_records": len(sample),
                "metrics": _metric(result),
                "status": result.get("status"),
            }
        )
    missing = {
        "descriptor_missing_rate": round(
            sum(1 for record in records if not record.get("descriptor")) / len(records), 6
        ),
        "borough_missing_rate": round(
            sum(1 for record in records if not record.get("borough")) / len(records), 6
        ),
        "source_status_missing_rate": round(
            sum(1 for record in records if not record.get("source_status")) / len(records), 6
        ),
        "factor_missingness": (
            "Not simulated: the normalized snapshot has complete required fields. "
            "Record thinning measures volume sensitivity, not missing-at-random data."
        ),
    }
    return {
        "status": "COMPLETED" if resol or windows else "INSUFFICIENT_DATA",
        "dataset_key": dataset_key,
        "base_metrics": _metric(base),
        "resolution": resol,
        "target_window": windows,
        "record_thinning": thinning,
        "density_strata": {
            "dense": _cell_subset_metrics(base, dense=True),
            "sparse": _cell_subset_metrics(base, dense=False),
            "note": "Density split uses median history record count per fold, not labels.",
        },
        "threshold_sensitivity": _threshold_counts(
            records, settings, config, dataset_key, bbox
        ),
        "missingness": missing,
        "sensitivity_from_primary_run": sensitivity,
        "limitations": [
            "Resolution and window variants change the prediction universe, so "
            "cross-setting metrics are not strictly paired.",
            "Record thinning removes both history and future records and is a "
            "data-volume stress test, not a missing-data mechanism.",
            "Thresholds change categorical bands but not ranking metrics.",
            "Stability compares only cells present in both grids; parent-cell "
            "aggregation is not a truth-preserving relabeling.",
        ],
        "runtime_ms": round((time.perf_counter() - started) * 1000, 1),
    }
