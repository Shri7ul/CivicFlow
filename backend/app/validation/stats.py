"""Small, dependency-free statistical helpers for fold-level comparisons.

The evaluation unit is a rolling origin/fold, not an H3 cell or an incident.
Cells within a fold and folds from the same period are not independent. The
intervals below therefore describe variability across the observed origins and
must not be presented as population-level confidence in a deployment.
"""

from __future__ import annotations

import math
import random
import statistics
from typing import Iterable, Sequence


def mean(values: Iterable[float]) -> float | None:
    present = [float(value) for value in values if value is not None]
    return round(statistics.fmean(present), 6) if present else None


def bootstrap_mean_ci(
    values: Sequence[float],
    *,
    resamples: int = 2000,
    seed: int = 20261124,
    alpha: float = 0.05,
) -> dict:
    if not values:
        return {"n": 0, "mean": None, "ci_low": None, "ci_high": None}
    rng = random.Random(seed)
    samples = []
    for _ in range(resamples):
        draw = [values[rng.randrange(len(values))] for _ in values]
        samples.append(statistics.fmean(draw))
    samples.sort()
    low = samples[int((alpha / 2) * (len(samples) - 1))]
    high = samples[int((1 - alpha / 2) * (len(samples) - 1))]
    return {
        "n": len(values),
        "mean": round(statistics.fmean(values), 6),
        "ci_low": round(low, 6),
        "ci_high": round(high, 6),
        "resamples": resamples,
        "seed": seed,
        "note": "Percentile bootstrap over fold-level values; folds are not independent.",
    }


def paired_comparison(
    deltas: Sequence[float],
    *,
    resamples: int = 2000,
    seed: int = 20261124,
) -> dict:
    """Summarize variant-minus-reference fold deltas without overclaiming."""
    if not deltas:
        return {
            "n": 0,
            "mean_delta": None,
            "ci_low": None,
            "ci_high": None,
            "wins": 0,
            "losses": 0,
            "ties": 0,
            "sign_test_p": None,
        }
    wins = sum(1 for value in deltas if value > 0)
    losses = sum(1 for value in deltas if value < 0)
    ties = len(deltas) - wins - losses
    n = wins + losses
    p_value = None
    if n:
        tail = sum(math.comb(n, index) for index in range(0, min(wins, losses) + 1))
        p_value = min(1.0, 2 * tail / (2**n))
    interval = bootstrap_mean_ci(
        deltas, resamples=resamples, seed=seed
    )
    rng = random.Random(seed)
    positive_resamples = 0
    for _ in range(resamples):
        draw = [deltas[rng.randrange(len(deltas))] for _ in deltas]
        if statistics.fmean(draw) > 0:
            positive_resamples += 1
    return {
        "n": len(deltas),
        "mean_delta": interval["mean"],
        "median_delta": round(statistics.median(deltas), 6),
        "ci_low": interval["ci_low"],
        "ci_high": interval["ci_high"],
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "sign_test_p": round(p_value, 6) if p_value is not None else None,
        "bootstrap_probability_positive": round(
            positive_resamples / resamples, 6
        ),
        "note": (
            "Paired fold deltas; percentile bootstrap and exact sign test are "
            "descriptive because folds overlap temporally."
        ),
    }


def aggregate_fold_metric(
    results: Sequence[dict], metric: str = "pr_auc"
) -> list[float]:
    values = []
    for result in results:
        risk = (result.get("methods") or {}).get("civicflow_risk", {})
        value = risk.get(metric)
        if value is not None:
            values.append(float(value))
    return values
