"""Deterministic factor normalization and explainable risk scoring."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Iterable
from uuid import UUID

from app.models import (
    IncidentCategory,
    IncidentSeverity,
    IncidentStatus,
    RiskCategory,
)
from app.risk.config import FACTOR_LABELS, RiskConfig
from app.risk.geo import haversine_m

ACTIVE_STATUSES = {
    IncidentStatus.OPEN,
    IncidentStatus.ACKNOWLEDGED,
    IncidentStatus.IN_PROGRESS,
}

_SEVERITY_RANK = {
    IncidentSeverity.LOW: 0,
    IncidentSeverity.MEDIUM: 1,
    IncidentSeverity.HIGH: 2,
    IncidentSeverity.CRITICAL: 3,
}


@dataclass(frozen=True)
class IncidentRecord:
    id: UUID
    latitude: float
    longitude: float
    created_at: datetime
    severity: IncidentSeverity
    category: IncidentCategory
    status: IncidentStatus
    reporter_id: UUID


@dataclass(frozen=True)
class Factor:
    key: str
    label: str
    raw_value: float | int | str | None
    normalized: float | None
    weight: float
    contribution: float
    available: bool
    explanation: str


@dataclass(frozen=True)
class IncidentAggregate:
    raw_incidents: tuple[IncidentRecord, ...]
    adjusted_incidents: tuple[IncidentRecord, ...]
    removed_duplicates: int
    status_counts: dict[str, int]
    severity_counts: dict[str, int]
    category_counts: dict[str, int]
    active_count: int


@dataclass(frozen=True)
class InfrastructureFactor:
    normalized: float | None
    available: bool
    explanation: str
    metadata: dict


@dataclass(frozen=True)
class ScoringResult:
    incident_activity_score: float
    risk_score: float
    risk_category: RiskCategory
    confidence: float
    confidence_label: str
    factors: tuple[Factor, ...]
    availability: float


@dataclass(frozen=True)
class TrendResult:
    available: bool
    direction: str
    delta_score: float
    current_score: float
    previous_score: float
    current_incident_count: int
    previous_incident_count: int
    label: str
    reason: str


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def recency_weight(
    created_at: datetime,
    *,
    now: datetime,
    half_life_hours: float,
) -> float:
    age_hours = max(0.0, (_utc(now) - _utc(created_at)).total_seconds() / 3600)
    return max(0.0001, 0.5 ** (age_hours / half_life_hours))


def _deduplicate(
    incidents: list[IncidentRecord],
    duplicate_pairs: Iterable[tuple[UUID, UUID]],
) -> list[IncidentRecord]:
    """Remove confirmed duplicate clusters, keeping one representative.

    Unresolved suggestions are deliberately absent from ``duplicate_pairs``:
    only a WORKER/ADMIN-confirmed DUPLICATE relationship can adjust activity.
    """
    ids = {incident.id for incident in incidents}
    parent = {incident_id: incident_id for incident_id in ids}

    def find(value: UUID) -> UUID:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(first: UUID, second: UUID) -> None:
        if first not in parent or second not in parent:
            return
        root_a = find(first)
        root_b = find(second)
        if root_a != root_b:
            parent[root_b] = root_a

    for first, second in duplicate_pairs:
        union(first, second)

    groups: dict[UUID, list[IncidentRecord]] = {}
    for incident in incidents:
        groups.setdefault(find(incident.id), []).append(incident)

    kept: list[IncidentRecord] = []
    for group in groups.values():
        representative = max(
            group,
            key=lambda item: (
                _SEVERITY_RANK[item.severity],
                _utc(item.created_at),
                item.id,
            ),
        )
        kept.append(representative)

    kept.sort(key=lambda item: item.created_at)
    return kept


def deduplicate_incidents(
    incidents: Iterable[IncidentRecord],
    duplicate_pairs: Iterable[tuple[UUID, UUID]] = (),
) -> tuple[IncidentRecord, ...]:
    """Return one representative per confirmed duplicate cluster."""
    return tuple(_deduplicate(list(incidents), duplicate_pairs))


def aggregate_records(
    raw: Iterable[IncidentRecord],
    adjusted: Iterable[IncidentRecord],
) -> IncidentAggregate:
    """Build explainable counts from raw and globally adjusted records."""
    raw_items = tuple(raw)
    adjusted_items = tuple(adjusted)
    return IncidentAggregate(
        raw_incidents=raw_items,
        adjusted_incidents=adjusted_items,
        removed_duplicates=max(0, len(raw_items) - len(adjusted_items)),
        status_counts=dict(Counter(item.status.value for item in raw_items)),
        severity_counts=dict(Counter(item.severity.value for item in adjusted_items)),
        category_counts=dict(Counter(item.category.value for item in adjusted_items)),
        active_count=sum(
            1 for item in adjusted_items if item.status in ACTIVE_STATUSES
        ),
    )


def aggregate_incidents(
    incidents: Iterable[IncidentRecord],
    *,
    duplicate_pairs: Iterable[tuple[UUID, UUID]] = (),
) -> IncidentAggregate:
    raw = tuple(incidents)
    adjusted = deduplicate_incidents(raw, duplicate_pairs)
    return aggregate_records(raw, adjusted)


def _weighted_average(
    values: Iterable[tuple[float, float]],
) -> float:
    total_weight = 0.0
    total = 0.0
    for value, weight in values:
        total += value * weight
        total_weight += weight
    if total_weight <= 0:
        return 0.0
    return total / total_weight


def _renormalize_contributions(
    factors: tuple[Factor, ...], total_weight: float
) -> tuple[Factor, ...]:
    """Make returned contributions sum to the final composite score.

    Base weights are configuration inputs. When a factor is unavailable, the
    remaining factors are renormalized for scoring; their reported
    contributions must use the same effective weights or they would not add up
    to the returned risk score.
    """
    if total_weight <= 0:
        return tuple(
            replace(factor, contribution=0.0) for factor in factors
        )
    return tuple(
        replace(
            factor,
            contribution=round(
                (factor.weight / total_weight) * (factor.normalized or 0)
                if factor.available and factor.normalized is not None
                else 0.0,
                4,
            ),
        )
        for factor in factors
    )


def _factor(
    key: str,
    *,
    raw_value: float | int | str | None,
    normalized: float | None,
    weight: float,
    available: bool,
    explanation: str,
) -> Factor:
    contribution = (
        round(weight * normalized, 4)
        if available and normalized is not None
        else 0.0
    )
    return Factor(
        key=key,
        label=FACTOR_LABELS[key],
        raw_value=raw_value,
        normalized=round(normalized, 4) if normalized is not None else None,
        weight=weight,
        contribution=contribution,
        available=available,
        explanation=explanation,
    )


def spatial_concentration(
    incidents: Iterable[IncidentRecord],
    *,
    center_latitude: float,
    center_longitude: float,
    cell_edge_length_m: float,
) -> float | None:
    """Measure how tightly incidents cluster inside their aggregate cell.

    H3 already supplies spatial aggregation. This factor adds a within-cell
    concentration signal: a single report is weak evidence (0.40), tightly
    co-located reports approach 1.0, and reports spread across the cell move
    toward 0.50. It is deliberately bounded and never substitutes for the
    incident count/density factor.
    """
    items = tuple(incidents)
    if not items:
        return None
    if len(items) == 1:
        return 0.40
    mean_latitude = sum(item.latitude for item in items) / len(items)
    mean_longitude = sum(item.longitude for item in items) / len(items)
    distances = [
        haversine_m(
            mean_latitude, mean_longitude, item.latitude, item.longitude
        )
        for item in items
    ]
    spread = sum(distances) / len(distances)
    edge = max(1.0, cell_edge_length_m)
    compactness = max(0.0, 1.0 - min(1.0, spread / edge))
    return max(0.0, min(1.0, 0.5 + 0.5 * compactness))


def trend_signal(
    *,
    current_count: int,
    previous_count: int,
    minimum_incidents: int,
    history_coverage: float = 1.0,
) -> float | None:
    """Convert a previous-period count comparison into a bounded risk factor.

    This is intentionally count-based so it does not feed the current composite
    score back into itself. It is unavailable until the combined history meets
    the configured minimum, avoiding confident trends from one or two reports.
    """
    combined = current_count + previous_count
    if history_coverage < 1.0 or combined < minimum_incidents:
        return None
    if previous_count == 0:
        return 1.0 if current_count > 0 else 0.5
    change = (current_count - previous_count) / previous_count
    return max(0.0, min(1.0, 0.5 + 0.5 * max(-1.0, min(1.0, change))))


def score_aggregate(
    aggregate: IncidentAggregate,
    *,
    config: RiskConfig,
    now: datetime,
    infrastructure: InfrastructureFactor,
    history_coverage: float = 1.0,
    spatial_value: float | None = None,
    trend_value: float | None = None,
) -> ScoringResult:
    incidents = aggregate.adjusted_incidents
    count = len(incidents)
    dependency_count = int(infrastructure.metadata.get("dependency_count", 0) or 0)
    dependency_value = min(1.0, dependency_count / 5.0)
    dependency_available = bool(
        infrastructure.available
        and infrastructure.metadata.get("nearby_asset_count", 0) > 0
    )
    if count == 0:
        factors = (
            _factor(
                "severity",
                raw_value=0,
                normalized=0.0,
                weight=config.weights["severity"],
                available=False,
                explanation="No adjusted incidents in this cell/window.",
            ),
            _factor(
                "density",
                raw_value=0,
                normalized=0.0,
                weight=config.weights["density"],
                available=False,
                explanation="No adjusted incidents in this cell/window.",
            ),
            _factor(
                "spatial",
                raw_value=0,
                normalized=None,
                weight=config.weights["spatial"],
                available=False,
                explanation="Spatial concentration is unavailable without incidents.",
            ),
            _factor(
                "recency",
                raw_value=0,
                normalized=0.0,
                weight=config.weights["recency"],
                available=False,
                explanation="No adjusted incidents in this cell/window.",
            ),
            _factor(
                "active",
                raw_value="0/0",
                normalized=0.0,
                weight=config.weights["active"],
                available=False,
                explanation="No adjusted incidents in this cell/window.",
            ),
            _factor(
                "category",
                raw_value=0,
                normalized=0.0,
                weight=config.weights["category"],
                available=False,
                explanation="No adjusted incidents in this cell/window.",
            ),
            _factor(
                "trend",
                raw_value="0 current / 0 previous",
                normalized=None,
                weight=config.weights["trend"],
                available=False,
                explanation="The window has no comparable incident history.",
            ),
            _factor(
                "infrastructure",
                raw_value=infrastructure.metadata.get("nearby_asset_count", 0),
                normalized=infrastructure.normalized,
                weight=config.weights["infrastructure"],
                available=infrastructure.available,
                explanation=infrastructure.explanation,
            ),
            _factor(
                "dependency",
                raw_value=dependency_count,
                normalized=dependency_value if dependency_available else None,
                weight=config.weights["dependency"],
                available=dependency_available,
                explanation=(
                    "Counts dependency links touching nearby active assets. "
                    "This is association context, not confirmed service impact."
                ),
            ),
        )
        exposure_weight = sum(
            factor.weight for factor in factors if factor.available
        )
        exposure_value = (
            sum(
                factor.weight * (factor.normalized or 0)
                for factor in factors
                if factor.available
            )
            / exposure_weight
            if exposure_weight > 0
            else 0.0
        )
        risk_score = round(exposure_value * 100, 2)
        return ScoringResult(
            incident_activity_score=0.0,
            risk_score=risk_score,
            risk_category=config.category_for(risk_score),
            confidence=0.0,
            confidence_label="low",
            factors=_renormalize_contributions(factors, exposure_weight),
            availability=round(exposure_weight, 4),
        )

    recency_weights = [
        recency_weight(
            item.created_at,
            now=now,
            half_life_hours=config.recency_half_life_hours,
        )
        for item in incidents
    ]
    severity_value = _weighted_average(
        (config.severity_weights[item.severity], weight)
        for item, weight in zip(incidents, recency_weights, strict=True)
    )
    category_value = _weighted_average(
        (config.category_weights[item.category], weight)
        for item, weight in zip(incidents, recency_weights, strict=True)
    )
    recency_value = sum(recency_weights) / len(recency_weights)
    density_value = min(
        1.0,
        math.log1p(count) / math.log1p(max(1, config.density_saturation)),
    )
    active_value = aggregate.active_count / count

    factors_list = [
        _factor(
            "severity",
            raw_value=round(severity_value * 100, 2),
            normalized=severity_value,
            weight=config.weights["severity"],
            available=True,
            explanation=(
                f"Recency-weighted mean severity across {count} adjusted "
                "incident(s); LOW=0.10, MEDIUM=0.35, HIGH=0.70, "
                "CRITICAL=1.00."
            ),
        ),
        _factor(
            "density",
            raw_value=count,
            normalized=density_value,
            weight=config.weights["density"],
            available=True,
            explanation=(
                f"Log-scaled adjusted incident count {count} against "
                f"saturation {config.density_saturation}."
            ),
        ),
        _factor(
            "spatial",
            raw_value=f"{len(incidents)} incident locations",
            normalized=spatial_value,
            weight=config.weights["spatial"],
            available=spatial_value is not None,
            explanation=(
                "Within-cell clustering from mean distance to the incident "
                "centroid, normalized by the H3 cell edge. A single report is "
                "treated as weak concentration evidence."
            ),
        ),
        _factor(
            "recency",
            raw_value=round(recency_value, 4),
            normalized=recency_value,
            weight=config.weights["recency"],
            available=True,
            explanation=(
                "Mean exponential recency weight with a "
                f"{config.recency_half_life_hours:g}-hour half-life."
            ),
        ),
        _factor(
            "active",
            raw_value=f"{aggregate.active_count}/{count}",
            normalized=active_value,
            weight=config.weights["active"],
            available=True,
            explanation=(
                "Share of adjusted incidents in OPEN, ACKNOWLEDGED, or "
                "IN_PROGRESS status."
            ),
        ),
        _factor(
            "category",
            raw_value=round(category_value * 100, 2),
            normalized=category_value,
            weight=config.weights["category"],
            available=True,
            explanation=(
                "Recency-weighted consequence weighting by category. This is "
                "a transparent model prior, not an empirical outcome estimate."
            ),
        ),
        _factor(
            "trend",
            raw_value="current vs previous period",
            normalized=trend_value,
            weight=config.weights["trend"],
            available=trend_value is not None,
            explanation=(
                "Previous-period adjusted incident count comparison; "
                "unavailable until the configured minimum history is met."
            ),
        ),
        _factor(
            "infrastructure",
            raw_value=infrastructure.metadata.get("nearby_asset_count", 0),
            normalized=infrastructure.normalized,
            weight=config.weights["infrastructure"],
            available=infrastructure.available,
            explanation=infrastructure.explanation,
        ),
        _factor(
            "dependency",
            raw_value=dependency_count,
            normalized=dependency_value if dependency_available else None,
            weight=config.weights["dependency"],
            available=dependency_available,
            explanation=(
                "Counts dependency links touching nearby active assets. "
                "This is association context, not confirmed service impact."
            ),
        ),
    ]
    factors = tuple(factors_list)

    incident_keys = (
        "severity",
        "density",
        "spatial",
        "recency",
        "active",
        "category",
        "trend",
    )
    incident_weight = sum(
        config.weights[key]
        for key in incident_keys
        if next(
            factor.available for factor in factors if factor.key == key
        )
    )
    incident_activity = (
        sum(
            config.weights[factor.key] * (factor.normalized or 0)
            for factor in factors
            if factor.key in incident_keys and factor.available
        )
        / incident_weight
        * 100
        if incident_weight > 0
        else 0.0
    )

    available = [factor for factor in factors if factor.available]
    total_weight = sum(factor.weight for factor in available)
    risk_score = (
        sum(factor.weight * (factor.normalized or 0) for factor in available)
        / total_weight
        * 100
        if total_weight > 0
        else 0.0
    )
    availability = total_weight
    factors = _renormalize_contributions(factors, total_weight)
    count_confidence = min(1.0, count / 5.0)
    confidence = max(
        0.0,
        min(
            1.0,
            0.40 * count_confidence
            + 0.35 * availability
            + 0.25 * max(0.0, min(1.0, history_coverage)),
        ),
    )
    confidence_label = (
        "high" if confidence >= 0.75 else "moderate" if confidence >= 0.5 else "low"
    )
    risk_score = round(risk_score, 2)
    return ScoringResult(
        incident_activity_score=round(incident_activity, 2),
        risk_score=risk_score,
        risk_category=config.category_for(risk_score),
        confidence=round(confidence, 3),
        confidence_label=confidence_label,
        factors=factors,
        availability=round(availability, 4),
    )


def calculate_trend(
    *,
    current_score: float,
    previous_score: float,
    current_count: int,
    previous_count: int,
    config: RiskConfig,
    stable_delta: float = 3.0,
    history_coverage: float = 1.0,
) -> TrendResult:
    combined = current_count + previous_count
    if history_coverage < 1.0:
        return TrendResult(
            available=False,
            direction="INSUFFICIENT_DATA",
            delta_score=round(current_score - previous_score, 2),
            current_score=round(current_score, 2),
            previous_score=round(previous_score, 2),
            current_incident_count=current_count,
            previous_incident_count=previous_count,
            label="Insufficient history",
            reason=(
                "The previous comparison window is only "
                f"{max(0.0, min(1.0, history_coverage)) * 100:.0f}% covered "
                "by available incident history; a trend is withheld until the "
                "full comparison window is observable."
            ),
        )
    if combined < config.trend_min_incidents:
        return TrendResult(
            available=False,
            direction="INSUFFICIENT_DATA",
            delta_score=round(current_score - previous_score, 2),
            current_score=round(current_score, 2),
            previous_score=round(previous_score, 2),
            current_incident_count=current_count,
            previous_incident_count=previous_count,
            label="Insufficient history",
            reason=(
                f"At least {config.trend_min_incidents} combined current and "
                "previous-period incidents are required before a trend is "
                "reported."
            ),
        )
    delta = round(current_score - previous_score, 2)
    if abs(delta) < stable_delta:
        direction = "STABLE"
        label = "Stable"
    elif delta > 0:
        direction = "INCREASING"
        label = "Increasing"
    else:
        direction = "DECREASING"
        label = "Decreasing"
    return TrendResult(
        available=True,
        direction=direction,
        delta_score=delta,
        current_score=round(current_score, 2),
        previous_score=round(previous_score, 2),
        current_incident_count=current_count,
        previous_incident_count=previous_count,
        label=label,
        reason=(
            "Current-period incident-activity score compared with the "
            "immediately preceding equal-length window; infrastructure "
            "exposure is excluded from the trend comparison."
        ),
    )
