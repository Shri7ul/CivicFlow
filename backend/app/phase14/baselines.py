"""Null-safe baseline comparison records."""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser
from app.geo.contexts import require_context
from app.governance.errors import GovernanceError
from app.models.enums import Role
from app.models.phase14 import BaselineComparison
from app.models.pilot import Pilot

METRIC_KEYS = {
    "precision",
    "recall",
    "f1",
    "roc_auc",
    "pr_auc",
    "brier_score",
    "expected_calibration_error",
    "false_positive_rate",
    "false_negative_rate",
    "coverage",
    "data_completeness",
    "geographic_coverage",
    "temporal_coverage",
    "human_agreement",
}


def _fail(message: str, *, code: str, status_code: int = 400) -> None:
    raise GovernanceError(message, code=code, status_code=status_code)


def _clean_metrics(values: dict, *, label: str, allow_null: bool) -> dict:
    if not isinstance(values, dict):
        _fail(f"{label} must be an object", code="invalid_metrics", status_code=422)
    cleaned: dict[str, float | None] = {}
    for key, value in values.items():
        if key not in METRIC_KEYS:
            _fail(f"Unsupported metric {key}", code="invalid_metric_key", status_code=422)
        if value is None:
            # Null is always honest: it means the metric was not computed.
            cleaned[key] = None
            continue
        if not allow_null:
            _fail(f"{label}.{key} cannot be populated without labels", code="fabricated_metric", status_code=422)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            _fail(f"{label}.{key} must be a finite number or null", code="invalid_metric_value", status_code=422)
        cleaned[key] = float(value)
    return cleaned


def record_comparison(session: Session, payload: Any, actor: AuthenticatedUser) -> BaselineComparison:
    if actor.profile.role != Role.ADMIN:
        _fail("Only an administrator can record a baseline comparison", code="baseline_forbidden", status_code=403)
    context_key = require_context(payload.geographic_context_key).key
    if payload.pilot_id is not None and session.get(Pilot, payload.pilot_id) is None:
        _fail("Pilot not found", code="pilot_not_found", status_code=404)
    existing = session.scalar(
        select(BaselineComparison.id).where(BaselineComparison.comparison_key == payload.comparison_key)
    )
    if existing is not None:
        _fail("A comparison with this key already exists", code="comparison_key_conflict", status_code=409)

    allow_metrics = payload.label_count > 0
    baseline_metrics = _clean_metrics(payload.baseline_metrics, label="baseline_metrics", allow_null=allow_metrics)
    candidate_metrics = _clean_metrics(payload.candidate_metrics, label="candidate_metrics", allow_null=allow_metrics)

    comparison = BaselineComparison(
        comparison_key=payload.comparison_key,
        pilot_id=payload.pilot_id,
        geographic_context_key=context_key,
        comparison_type=payload.comparison_type,
        method=payload.method,
        baseline_name=payload.baseline_name,
        candidate_name=payload.candidate_name,
        label_source=payload.label_source,
        label_count=payload.label_count,
        sample_count=payload.sample_count,
        baseline_metrics=baseline_metrics,
        candidate_metrics=candidate_metrics,
        notes=payload.notes,
        limitations=payload.limitations,
        created_by=actor.profile.id,
    )
    session.add(comparison)
    session.commit()
    return comparison


def usable_comparisons(session: Session, *, context_key: str, pilot_id: uuid.UUID | None = None) -> list[BaselineComparison]:
    statement = select(BaselineComparison).where(
        BaselineComparison.geographic_context_key == context_key,
        BaselineComparison.label_count > 0,
    )
    if pilot_id is not None:
        statement = statement.where(BaselineComparison.pilot_id == pilot_id)
    rows = list(session.scalars(statement).all())
    return [
        row
        for row in rows
        if any(value is not None for value in row.candidate_metrics.values())
        and any(value is not None for value in row.baseline_metrics.values())
    ]


def count(session: Session, *, context_key: str | None = None) -> int:
    statement = select(func.count()).select_from(BaselineComparison)
    if context_key:
        statement = statement.where(BaselineComparison.geographic_context_key == context_key)
    return int(session.scalar(statement) or 0)
