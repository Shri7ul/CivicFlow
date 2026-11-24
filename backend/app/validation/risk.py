"""Leakage-safe empirical backtesting for the Phase 5 risk engine.

The actual RiskEngine is executed against a bounded, isolated SQLite copy of a
validated public snapshot. No operational incident row is read or mutated.
Origins are strictly historical and target labels come only from the following
window, so future incidents cannot enter a feature or configuration decision.
"""

from __future__ import annotations

import math
import statistics
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Iterable

import h3
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.models import (
    Base,
    Incident,
    IncidentCategory,
    IncidentSeverity,
    IncidentStatus,
    Profile,
    RiskCategory,
    Role,
)
from app.risk.config import RiskConfig
from app.risk.engine import RiskEngine, RiskQuery
from app.validation.dataset import NYC311_BBOX

VALIDATION_REPORTER_ID = uuid.UUID("00000000-0000-0000-0000-000000000008")


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _cell(latitude: float, longitude: float, resolution: int) -> str:
    return h3.latlng_to_cell(latitude, longitude, resolution)


def _counting_cells(
    records: Iterable[dict], resolution: int
) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        grouped[_cell(record["latitude"], record["longitude"], resolution)].append(
            record
        )
    return grouped


def _make_isolated_session(records: list[dict], dataset_key: str) -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(
        Profile(
            id=VALIDATION_REPORTER_ID,
            full_name="Validation dataset fixture",
            role=Role.CITIZEN,
            is_active=True,
        )
    )
    incidents: list[Incident] = []
    for record in records:
        observed_at = _parse(record["observed_at"])
        incidents.append(
            Incident(
                id=uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"{dataset_key}:{record['external_id']}",
                ),
                title=record["complaint_type"],
                description=record.get("descriptor") or record["complaint_type"],
                category=IncidentCategory(record["category"]),
                severity=IncidentSeverity(record["severity"]),
                status=IncidentStatus(record["status"]),
                location=(
                    f"POINT({record['longitude']:.8f} "
                    f"{record['latitude']:.8f})"
                ),
                reporter_id=VALIDATION_REPORTER_ID,
                created_at=observed_at,
            )
        )
    session.add_all(incidents)
    session.commit()
    return session


def _close_session(session: Session) -> None:
    bind = session.get_bind()
    session.close()
    bind.dispose()


def _ranking_metrics(
    scores: dict[str, float],
    labels: dict[str, int],
    *,
    top_k: int,
) -> dict:
    cells = sorted(labels)
    positives = sum(labels.values())
    if positives == 0 or positives == len(cells):
        return {
            "status": "INSUFFICIENT_DATA",
            "cell_count": len(cells),
            "positive_count": positives,
            "precision_at_k": None,
            "recall_at_k": None,
            "roc_auc": None,
            "pr_auc": None,
        }
    ordered = sorted(
        cells, key=lambda cell: (-scores.get(cell, 0.0), cell)
    )
    k = max(1, min(top_k, len(ordered)))
    top = ordered[:k]
    hits = sum(labels.get(cell, 0) for cell in top)
    precision = hits / k
    recall = hits / positives
    # Average precision and ROC-AUC are computed from the full ranking.
    ordered_positive = [cell for cell in ordered if labels.get(cell) == 1]
    precision_sum = 0.0
    hit_count = 0
    positive_set = set(ordered_positive)
    for rank, cell in enumerate(ordered, start=1):
        if cell in positive_set:
            hit_count += 1
            precision_sum += hit_count / rank
    pr_auc = precision_sum / positives
    positives_count = positives
    negatives_count = len(cells) - positives
    rank_sum = 0.0
    index = 0
    while index < len(ordered):
        end = index + 1
        score = scores.get(ordered[index], 0.0)
        while (
            end < len(ordered)
            and scores.get(ordered[end], 0.0) == score
        ):
            end += 1
        # Ranks are assigned in ascending score order, while ``ordered`` is
        # descending, so convert the descending position to a conventional rank.
        average_rank = len(ordered) + 1 - (index + 1 + end) / 2
        rank_sum += average_rank * sum(
            1 for cell in ordered[index:end] if labels.get(cell) == 1
        )
        index = end
    roc_auc = (
        rank_sum
        - positives_count * (positives_count + 1) / 2
    ) / (positives_count * negatives_count)
    return {
        "status": "COMPLETED",
        "cell_count": len(cells),
        "positive_count": positives,
        "top_k": k,
        "precision_at_k": round(precision, 6),
        "recall_at_k": round(recall, 6),
        "roc_auc": round(roc_auc, 6),
        "pr_auc": round(pr_auc, 6),
    }


def _mean(values: Iterable[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return round(statistics.fmean(present), 6) if present else None


def _method_summary(folds: list[dict], method: str) -> dict:
    metrics = [fold["metrics"][method] for fold in folds]
    return {
        "fold_count": len(metrics),
        "precision_at_k": _mean(item.get("precision_at_k") for item in metrics),
        "recall_at_k": _mean(item.get("recall_at_k") for item in metrics),
        "roc_auc": _mean(item.get("roc_auc") for item in metrics),
        "pr_auc": _mean(item.get("pr_auc") for item in metrics),
        "completed_folds": sum(
            1 for item in metrics if item.get("status") == "COMPLETED"
        ),
    }


def _baseline_scores(
    history: list[dict],
    previous: list[dict],
    *,
    origin: datetime,
    config: RiskConfig,
    resolution: int,
) -> dict[str, dict[str, float]]:
    history_cells = _counting_cells(history, resolution)
    recent = [
        record
        for record in history
        if _parse(record["observed_at"]) >= origin - timedelta(hours=168)
    ]
    recent_cells = _counting_cells(recent, resolution)
    previous_cells = _counting_cells(previous, resolution)
    weighted: dict[str, float] = defaultdict(float)
    for record in history:
        observed = _parse(record["observed_at"])
        age_hours = max(0.0, (origin - observed).total_seconds() / 3600)
        category_weight = config.category_weights[
            IncidentCategory(record["category"])
        ]
        severity_weight = config.severity_weights[
            IncidentSeverity(record["severity"])
        ]
        recency_weight = math.exp(
            -age_hours / max(1.0, config.recency_half_life_hours)
        )
        weighted[_cell(record["latitude"], record["longitude"], resolution)] += (
            category_weight * severity_weight * recency_weight
        )
    return {
        "baseline_count": {
            cell: float(len(items)) for cell, items in history_cells.items()
        },
        "baseline_recent": {
            cell: float(len(items)) for cell, items in recent_cells.items()
        },
        "baseline_weighted": dict(weighted),
        "baseline_persistence": {
            cell: float(len(items)) for cell, items in previous_cells.items()
        },
    }


def _top_cells(scores: dict[str, float], limit: int = 20) -> set[str]:
    return set(
        sorted(scores, key=lambda cell: (-scores[cell], cell))[:limit]
    )


def _jaccard(first: set[str], second: set[str]) -> float:
    union = first | second
    return round(len(first & second) / len(union), 6) if union else 0.0


def _average_ranks(scores: dict[str, float], cells: list[str]) -> dict[str, float]:
    ordered = sorted(cells, key=lambda cell: (scores[cell], cell))
    ranks: dict[str, float] = {}
    index = 0
    while index < len(ordered):
        end = index + 1
        score = scores[ordered[index]]
        while end < len(ordered) and scores[ordered[end]] == score:
            end += 1
        average_rank = (index + 1 + end) / 2
        for cell in ordered[index:end]:
            ranks[cell] = average_rank
        index = end
    return ranks


def _spearman(first: dict[str, float], second: dict[str, float]) -> float | None:
    cells = sorted(set(first) & set(second))
    if len(cells) < 3:
        return None
    rank_a = _average_ranks(first, cells)
    rank_b = _average_ranks(second, cells)
    n = len(cells)
    delta_squared = sum(
        (rank_a[cell] - rank_b[cell]) ** 2 for cell in cells
    )
    return round(1 - (6 * delta_squared) / (n * (n * n - 1)), 6)


def _sensitivity(
    records: list[dict],
    *,
    origin: datetime,
    config: RiskConfig,
    session: Session,
    settings: Settings,
    bbox: tuple[float, float, float, float],
) -> dict:
    del records
    def window_scores(window_hours: int, resolution: int) -> dict[str, float]:
        result = RiskEngine(session, config).compute(
            RiskQuery(
                resolution=resolution,
                window_hours=window_hours,
                bbox=bbox,
                limit=config.max_cells,
                as_of=origin,
            )
        )
        return {
            cell.h3_cell_id: cell.risk_score for cell in result.cells
        }

    resolution = settings.validation_resolution
    short = window_scores(168, resolution)
    long = window_scores(min(config.max_window_hours, 336), resolution)
    res8 = window_scores(168, 8)
    res7 = window_scores(168, 7)
    res9 = window_scores(168, 9)
    res8_parent = {
        h3.cell_to_parent(cell, 7): score for cell, score in res8.items()
    }
    thresholds = config.thresholds
    threshold_counts = {
        "low": sum(1 for score in short.values() if score >= thresholds[0]),
        "moderate": sum(1 for score in short.values() if score >= thresholds[1]),
        "high": sum(1 for score in short.values() if score >= thresholds[2]),
        "critical": sum(1 for score in short.values() if score >= thresholds[3]),
    }
    return {
        "origin": origin.isoformat(),
        "window_168_vs_336": {
            "common_cell_count": len(set(short) & set(long)),
            "spearman": _spearman(short, long),
            "top20_jaccard": _jaccard(_top_cells(short), _top_cells(long)),
        },
        "resolution": {
            "cell_counts": {
                "7": len(res7),
                "8": len(res8),
                "9": len(res9),
            },
            "max_scores": {
                "7": round(max(res7.values(), default=0.0), 4),
                "8": round(max(res8.values(), default=0.0), 4),
                "9": round(max(res9.values(), default=0.0), 4),
            },
            "top20_res7_vs_res8_parent_jaccard": _jaccard(
                _top_cells(res7), _top_cells(res8_parent)
            ),
        },
        "thresholds": {
            "values": {
                "low": thresholds[0],
                "moderate": thresholds[1],
                "high": thresholds[2],
                "critical": thresholds[3],
            },
            "cell_counts_at_or_above": threshold_counts,
            "note": "Descriptive band counts at one origin; not tuned.",
        },
        "top_k_limit": 20,
        "main_resolution": resolution,
        "note": (
            "Sensitivity checks use one origin only and are descriptive "
            "stability diagnostics, not ground-truth model selection."
        ),
    }


def run_risk_backtest(
    records: list[dict],
    *,
    settings: Settings,
    config: RiskConfig,
    dataset_key: str,
    bbox: tuple[float, float, float, float] = NYC311_BBOX,
    include_sensitivity: bool = True,
    include_cell_data: bool = False,
) -> dict:
    if not records:
        raise ValueError("No validated records are available.")
    start = min(_parse(record["observed_at"]) for record in records)
    end = max(_parse(record["observed_at"]) for record in records)
    origin = start + timedelta(hours=settings.validation_history_hours)
    target = timedelta(hours=settings.validation_target_hours)
    folds = []
    session = _make_isolated_session(records, dataset_key)
    try:
        while origin + target <= end and len(folds) < settings.validation_max_folds:
            history_start = origin - timedelta(
                hours=settings.validation_history_hours
            )
            history = [
                record
                for record in records
                if history_start <= _parse(record["observed_at"]) < origin
            ]
            previous_start = origin - timedelta(
                hours=settings.validation_target_hours
            )
            previous = [
                record
                for record in history
                if previous_start <= _parse(record["observed_at"]) < origin
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
            risk_scores = {
                cell.h3_cell_id: cell.risk_score for cell in computation.cells
            }
            baselines = _baseline_scores(
                history,
                previous,
                origin=origin,
                config=config,
                resolution=settings.validation_resolution,
            )
            target_by_cell: dict[str, int] = defaultdict(int)
            for record in future:
                target_by_cell[
                    _cell(
                        record["latitude"],
                        record["longitude"],
                        settings.validation_resolution,
                    )
                ] += 1
            labels = {
                cell: 1 if count > 0 else 0
                for cell, count in target_by_cell.items()
            }
            universe = (
                {
                    _cell(
                        record["latitude"],
                        record["longitude"],
                        settings.validation_resolution,
                    )
                    for record in history
                }
                | set(labels)
                | set(risk_scores)
                | set(baselines["baseline_count"])
            )
            labels = {cell: labels.get(cell, 0) for cell in universe}
            methods = {
                "civicflow_risk": risk_scores,
                **baselines,
            }
            fold_metrics = {
                method: _ranking_metrics(
                    scores, labels, top_k=settings.validation_top_k
                )
                for method, scores in methods.items()
            }
            cell_data = None
            if include_cell_data:
                history_counts = _counting_cells(
                    history, settings.validation_resolution
                )
                cell_data = {
                    cell: {
                        "label": labels[cell],
                        "history_count": len(history_counts.get(cell, [])),
                        "scores": {
                            method: round(scores.get(cell, 0.0), 6)
                            for method, scores in methods.items()
                        },
                    }
                    for cell in sorted(labels)
                }
            fold_payload = {
                    "origin": origin.isoformat(),
                    "target_start": origin.isoformat(),
                    "target_end": (origin + target).isoformat(),
                    "history_count": len(history),
                    "target_incident_count": len(future),
                    "target_cell_count": len(target_by_cell),
                    "cell_count": len(universe),
                    "label_prevalence": round(
                        sum(labels.values()) / len(universe), 6
                    ),
                    "metrics": fold_metrics,
                }
            if cell_data is not None:
                fold_payload["cell_data"] = cell_data
            folds.append(fold_payload)
            origin += target
        sensitivity_origin = (
            _parse(folds[0]["origin"]) if folds else None
        )
        sensitivity = (
            _sensitivity(
                records,
                origin=sensitivity_origin,
                config=config,
                session=session,
                settings=settings,
                bbox=bbox,
            )
            if include_sensitivity and sensitivity_origin is not None
            else None
        )
    finally:
        _close_session(session)
    if not folds:
        return {
            "status": "INSUFFICIENT_DATA",
            "folds": [],
            "methods": {},
            "sensitivity": None,
        }
    methods = {
        method: _method_summary(folds, method)
        for method in (
            "civicflow_risk",
            "baseline_count",
            "baseline_recent",
            "baseline_weighted",
            "baseline_persistence",
        )
    }
    density = {
        "mean_history_records": round(
            statistics.fmean(fold["history_count"] for fold in folds), 3
        ),
        "mean_target_records": round(
            statistics.fmean(fold["target_incident_count"] for fold in folds), 3
        ),
        "mean_target_cells": round(
            statistics.fmean(fold["target_cell_count"] for fold in folds), 3
        ),
        "mean_universe_cells": round(
            statistics.fmean(fold["cell_count"] for fold in folds), 3
        ),
        "mean_label_prevalence": round(
            statistics.fmean(fold["label_prevalence"] for fold in folds), 6
        ),
        "classification": (
            "DENSE"
            if statistics.fmean(fold["label_prevalence"] for fold in folds) >= 0.5
            else "SPARSE"
        ),
        "note": "Descriptive target-cell prevalence across folds, not a tuning signal.",
    }
    return {
        "status": "COMPLETED",
        "folds": folds,
        "methods": methods,
        "sensitivity": sensitivity,
        "density": density,
        "resolution": settings.validation_resolution,
        "config_hash": config.config_hash,
        "risk_config": config.as_dict(),
        "dataset_start": start.isoformat(),
        "dataset_end": end.isoformat(),
        "origin_count": len(folds),
    }
