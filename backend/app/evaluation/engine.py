"""Transparent evaluation metrics for risk-model predictions.

Samples are supplied by a caller with an explicit ground-truth label. The
repository does not contain a validated municipal outcome dataset, so the API
must mark synthetic fixtures and must never present them as field performance.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from math import isfinite
from typing import Iterable


class EvaluationError(ValueError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class EvaluationSample:
    predicted_score: float
    observed: int
    cell_id: str | None = None
    observed_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isfinite(self.predicted_score) or not 0 <= self.predicted_score <= 100:
            raise EvaluationError(
                "predicted_score must be a finite number within 0..100.",
                code="invalid_evaluation_sample",
            )
        if self.observed not in (0, 1):
            raise EvaluationError(
                "observed must be 0 or 1.",
                code="invalid_evaluation_sample",
            )


def _safe_ratio(numerator: float, denominator: float) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def _roc_auc(samples: list[EvaluationSample]) -> float | None:
    positives = sum(sample.observed for sample in samples)
    negatives = len(samples) - positives
    if positives == 0 or negatives == 0:
        return None
    ordered = sorted(samples, key=lambda sample: sample.predicted_score)
    rank_sum = 0.0
    index = 0
    while index < len(ordered):
        end_index = index + 1
        while (
            end_index < len(ordered)
            and ordered[end_index].predicted_score
            == ordered[index].predicted_score
        ):
            end_index += 1
        average_rank = (index + 1 + end_index) / 2
        rank_sum += average_rank * sum(
            1 for sample in ordered[index:end_index] if sample.observed == 1
        )
        index = end_index
    auc = (
        rank_sum - positives * (positives + 1) / 2
    ) / (positives * negatives)
    return round(auc, 6)


def _average_precision(samples: list[EvaluationSample]) -> float | None:
    positives = sum(sample.observed for sample in samples)
    if positives == 0:
        return None
    ordered = sorted(samples, key=lambda sample: sample.predicted_score, reverse=True)
    hit_count = 0
    precision_sum = 0.0
    for index, sample in enumerate(ordered, start=1):
        if sample.observed:
            hit_count += 1
            precision_sum += hit_count / index
    return round(precision_sum / positives, 6)


def _binary_metrics(
    samples: list[EvaluationSample], threshold: float
) -> dict:
    tp = sum(1 for sample in samples if sample.observed == 1 and sample.predicted_score >= threshold)
    fp = sum(1 for sample in samples if sample.observed == 0 and sample.predicted_score >= threshold)
    fn = sum(1 for sample in samples if sample.observed == 1 and sample.predicted_score < threshold)
    tn = sum(1 for sample in samples if sample.observed == 0 and sample.predicted_score < threshold)
    precision = _safe_ratio(tp, tp + fp)
    recall = _safe_ratio(tp, tp + fn)
    f1 = (
        round(2 * precision * recall / (precision + recall), 6)
        if precision is not None and recall is not None and precision + recall > 0
        else None
    )
    return {
        "threshold": threshold,
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_positive_rate": _safe_ratio(fp, fp + tn),
        "specificity": _safe_ratio(tn, tn + fp),
        "accuracy": _safe_ratio(tp + tn, len(samples)),
    }


def _calibration(samples: list[EvaluationSample], bins: int = 10) -> dict:
    buckets: list[dict] = []
    for index in range(bins):
        low = index / bins * 100
        high = (index + 1) / bins * 100
        members = [
            sample
            for sample in samples
            if low <= sample.predicted_score < high
            or (index == bins - 1 and sample.predicted_score == 100)
        ]
        if not members:
            continue
        mean_predicted = sum(sample.predicted_score for sample in members) / len(members) / 100
        observed_rate = sum(sample.observed for sample in members) / len(members)
        buckets.append(
            {
                "lower": round(low, 2),
                "upper": round(high, 2),
                "count": len(members),
                "mean_predicted_probability": round(mean_predicted, 6),
                "observed_rate": round(observed_rate, 6),
                "absolute_error": round(abs(mean_predicted - observed_rate), 6),
            }
        )
    expected_calibration_error = (
        sum(item["count"] * item["absolute_error"] for item in buckets) / len(samples)
        if samples and buckets
        else None
    )
    return {
        "bins": buckets,
        "expected_calibration_error": (
            round(expected_calibration_error, 6)
            if expected_calibration_error is not None
            else None
        ),
    }


def _spatial_slices(samples: list[EvaluationSample], threshold: float) -> dict:
    groups: dict[str, list[EvaluationSample]] = {}
    for sample in samples:
        if sample.cell_id:
            groups.setdefault(sample.cell_id, []).append(sample)
    cells: list[dict] = []
    for cell_id, members in sorted(groups.items()):
        metrics = _binary_metrics(members, threshold)
        cells.append(
            {
                "cell_id": cell_id,
                "count": len(members),
                "positives": sum(sample.observed for sample in members),
                "precision": metrics["precision"],
                "recall": metrics["recall"],
                "f1": metrics["f1"],
            }
        )
    eligible = [cell for cell in cells if cell["f1"] is not None]
    both_classes = sum(
        1
        for cell in cells
        if 0 < cell["positives"] < cell["count"]
    )
    macro_f1 = (
        round(sum(cell["f1"] for cell in eligible) / len(eligible), 6)
        if eligible
        else None
    )
    return {
        "groups": cells[:100],
        "group_count": len(cells),
        "macro_f1": macro_f1,
        "groups_with_defined_f1": len(eligible),
        "groups_with_positive_and_negative": both_classes,
    }


def evaluate_samples(
    samples: Iterable[EvaluationSample],
    *,
    threshold: float = 50.0,
    include_spatial: bool = False,
    time_split: bool = False,
) -> dict:
    sample_list = list(samples)
    if not sample_list:
        return {
            "status": "INSUFFICIENT_DATA",
            "sample_count": 0,
            "metrics": {},
            "slices": {},
            "warnings": ["No labelled samples were supplied."],
        }
    if not 0 <= threshold <= 100:
        raise EvaluationError("threshold must be within 0..100.", code="invalid_threshold")
    positives = sum(sample.observed for sample in sample_list)
    negatives = len(sample_list) - positives
    metrics = {
        "sample_count": len(sample_list),
        "positive_count": positives,
        "negative_count": negatives,
        "prevalence": round(positives / len(sample_list), 6),
        "mean_predicted_score": round(
            sum(sample.predicted_score for sample in sample_list) / len(sample_list), 6
        ),
        "roc_auc": _roc_auc(sample_list),
        "pr_auc": _average_precision(sample_list),
        "brier_score": round(
            sum((sample.predicted_score / 100 - sample.observed) ** 2 for sample in sample_list)
            / len(sample_list),
            6,
        ),
        **_binary_metrics(sample_list, threshold),
    }
    calibration = _calibration(sample_list)
    metrics["expected_calibration_error"] = calibration["expected_calibration_error"]
    warnings: list[str] = []
    if len(sample_list) < 20:
        warnings.append("Fewer than 20 labelled samples; metrics are unstable.")
    if positives == 0 or negatives == 0:
        warnings.append("Both classes are required for discrimination metrics.")
    slices: dict = {"calibration_bins": calibration["bins"]}
    if include_spatial:
        slices["spatial"] = _spatial_slices(sample_list, threshold)
    if time_split:
        dated = [sample for sample in sample_list if sample.observed_at is not None]
        if len(dated) >= 2:
            dated.sort(key=lambda sample: sample.observed_at)
            split_at = max(1, int(len(dated) * 0.7))
            early = dated[:split_at]
            late = dated[split_at:]
            slices["time_split"] = {
                "early_count": len(early),
                "late_count": len(late),
                "early": _binary_metrics(early, threshold) if early else None,
                "late": _binary_metrics(late, threshold) if late else None,
            }
        else:
            warnings.append(
                "Time-based slices require at least two samples with observed_at."
            )
    status = "INSUFFICIENT_DATA" if positives == 0 or negatives == 0 else "COMPLETED"
    return {
        "status": status,
        "sample_count": len(sample_list),
        "metrics": metrics,
        "slices": slices,
        "warnings": warnings,
    }
