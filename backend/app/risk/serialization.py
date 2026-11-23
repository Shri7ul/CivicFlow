"""Convert engine dataclasses into stable API schemas."""

from __future__ import annotations

from collections import Counter
from datetime import datetime

from app.models import RiskCategory
from app.risk.config import FACTOR_LABELS, RiskConfig
from app.risk.engine import RiskCellResult, RiskComputation
from app.risk.scoring import Factor, TrendResult
from app.schemas.risk import (
    RiskAssetExposureResponse,
    RiskBandResponse,
    RiskCellBrief,
    RiskCellResponse,
    RiskConfigResponse,
    RiskDatasetResponse,
    RiskFactorResponse,
    RiskInfrastructureResponse,
    RiskSummaryResponse,
    RiskTrendResponse,
)


def _dataset(data: dict) -> RiskDatasetResponse:
    return RiskDatasetResponse(
        active_asset_count=int(data.get("active_asset_count", 0)),
        authoritative_asset_count=int(data.get("authoritative_asset_count", 0)),
        development_or_unknown_asset_count=int(
            data.get("development_or_unknown_asset_count", 0)
        ),
        asset_limit_reached=bool(data.get("asset_limit_reached", False)),
        is_authoritative=bool(data.get("is_authoritative", False)),
    )


def factor_response(factor: Factor) -> RiskFactorResponse:
    return RiskFactorResponse(
        key=factor.key,
        label=factor.label,
        raw_value=factor.raw_value,
        normalized=factor.normalized,
        weight=factor.weight,
        contribution=factor.contribution,
        available=factor.available,
        explanation=factor.explanation,
    )


def privacy_redact_trend(
    trend: TrendResult, *, minimum_incidents: int
) -> TrendResult:
    """Hide a comparison when either window falls below the small-cell floor."""
    if (
        trend.current_incident_count >= minimum_incidents
        and trend.previous_incident_count >= minimum_incidents
    ):
        return trend
    return TrendResult(
        available=False,
        direction="INSUFFICIENT_DATA",
        delta_score=0.0,
        current_score=0.0,
        previous_score=0.0,
        current_incident_count=0,
        previous_incident_count=0,
        label="Insufficient history",
        reason=(
            "Trend details are withheld because one comparison window is below "
            "the Citizen privacy minimum."
        ),
    )


def trend_response(trend: TrendResult) -> RiskTrendResponse:
    return RiskTrendResponse(
        available=trend.available,
        direction=trend.direction,
        direction_label=trend.label,
        delta_score=trend.delta_score,
        current_score=trend.current_score,
        previous_score=trend.previous_score,
        current_incident_count=trend.current_incident_count,
        previous_incident_count=trend.previous_incident_count,
        reason=trend.reason,
    )


def infrastructure_response(cell: RiskCellResult) -> RiskInfrastructureResponse:
    exposure = cell.infrastructure
    return RiskInfrastructureResponse(
        available=exposure.available,
        nearby_asset_count=exposure.nearby_asset_count,
        by_type=exposure.by_type,
        dependency_count=exposure.dependency_count,
        normalized_exposure=exposure.normalized,
        assets=[
            RiskAssetExposureResponse(
                id=item.id,
                name=item.name,
                asset_type=item.asset_type,
                criticality_score=item.criticality_score,
                distance_m=item.distance_m,
                dependency_count=item.dependency_count,
                source=item.source,
            )
            for item in exposure.items
        ],
        dataset=exposure.dataset,
        explanation=exposure.explanation,
    )


def cell_response(
    cell: RiskCellResult, *, calculated_at: datetime
) -> RiskCellResponse:
    return RiskCellResponse(
        h3_cell_id=cell.h3_cell_id,
        resolution=cell.resolution,
        boundary=cell.boundary,
        center_latitude=cell.center_latitude,
        center_longitude=cell.center_longitude,
        risk_score=cell.risk_score,
        incident_activity_score=cell.incident_activity_score,
        risk_category=RiskCategory(cell.risk_category),
        confidence=cell.confidence,
        confidence_label=cell.confidence_label,
        incident_count=cell.incident_count,
        active_count=cell.active_count,
        adjusted_incident_count=cell.adjusted_incident_count,
        removed_duplicates=cell.removed_duplicates,
        severity_distribution=cell.severity_distribution,
        category_distribution=cell.category_distribution,
        factors=[factor_response(factor) for factor in cell.factors],
        infrastructure=infrastructure_response(cell),
        trend=trend_response(cell.trend),
        calculated_at=calculated_at,
        model_version=cell.model_version,
        config_hash=cell.config_hash,
    )


def cell_brief(cell: RiskCellResult) -> RiskCellBrief:
    return RiskCellBrief(
        h3_cell_id=cell.h3_cell_id,
        resolution=cell.resolution,
        center_latitude=cell.center_latitude,
        center_longitude=cell.center_longitude,
        risk_score=cell.risk_score,
        risk_category=RiskCategory(cell.risk_category),
        confidence=cell.confidence,
        confidence_label=cell.confidence_label,
        incident_count=cell.incident_count,
        active_count=cell.active_count,
        trend_direction=cell.trend.direction,
    )


def summary_response(computation: RiskComputation) -> RiskSummaryResponse:
    cells = computation.cells
    categories = Counter(cell.risk_category for cell in cells)
    trend_counts = Counter(cell.trend.direction for cell in cells)
    factor_totals: dict[str, float] = {}
    factor_counts: dict[str, int] = {}
    for cell in cells:
        for factor in cell.factors:
            if factor.available and factor.normalized is not None:
                factor_totals[factor.key] = (
                    factor_totals.get(factor.key, 0.0) + factor.normalized
                )
                factor_counts[factor.key] = factor_counts.get(factor.key, 0) + 1
    factor_means = {
        key: round(factor_totals[key] / factor_counts[key], 4)
        for key in factor_totals
        if factor_counts[key]
    }
    exposed_assets = {
        item.id
        for cell in cells
        if cell.infrastructure.available
        for item in cell.infrastructure.items
    }
    incident_count = sum(cell.incident_count for cell in cells)
    adjusted = sum(cell.adjusted_incident_count for cell in cells)
    return RiskSummaryResponse(
        total_cells=len(cells),
        current_incident_count=incident_count,
        adjusted_incident_count=adjusted,
        duplicate_adjusted_count=max(0, incident_count - adjusted),
        category_distribution=dict(categories),
        high_critical_cells=(
            categories.get(RiskCategory.HIGH.value, 0)
            + categories.get(RiskCategory.CRITICAL.value, 0)
        ),
        increasing_cells=trend_counts.get("INCREASING", 0),
        decreasing_cells=trend_counts.get("DECREASING", 0),
        stable_cells=trend_counts.get("STABLE", 0),
        insufficient_trend_cells=trend_counts.get("INSUFFICIENT_DATA", 0),
        mean_risk_score=round(
            sum(cell.risk_score for cell in cells) / len(cells), 2
        )
        if cells
        else 0.0,
        max_risk_score=round(max((cell.risk_score for cell in cells), default=0.0), 2),
        mean_incident_activity_score=round(
            sum(cell.incident_activity_score for cell in cells) / len(cells), 2
        )
        if cells
        else 0.0,
        mean_confidence=round(
            sum(cell.confidence for cell in cells) / len(cells), 3
        )
        if cells
        else 0.0,
        exposure_cells=sum(
            1 for cell in cells if cell.infrastructure.nearby_asset_count > 0
        ),
        exposure_asset_count=len(exposed_assets),
        factor_means=factor_means,
        top_cells=[cell_brief(cell) for cell in cells[:5]],
        dataset=_dataset(computation.dataset),
        history_coverage=computation.history_coverage,
    )


def config_response(config: RiskConfig) -> RiskConfigResponse:
    payload = config.as_dict()
    return RiskConfigResponse(
        model_version=config.model_version,
        config_hash=config.config_hash,
        factor_weights=dict(config.weights),
        factor_labels=dict(FACTOR_LABELS),
        severity_weights=payload["severity_weights"],
        category_weights=payload["category_weights"],
        bands=[RiskBandResponse(**band) for band in payload["bands"]],
        resolutions={
            "min": config.min_resolution,
            "default": config.default_resolution,
            "max": config.max_resolution,
        },
        windows={
            "default_hours": config.default_window_hours,
            "max_hours": config.max_window_hours,
        },
        recency_half_life_hours=config.recency_half_life_hours,
        density_saturation=config.density_saturation,
        infrastructure_radius_m=config.infrastructure_radius_m,
        max_incidents=config.max_incidents,
        max_cells=config.max_cells,
        privacy_min_incidents=config.privacy_min_incidents,
        trend_min_incidents=config.trend_min_incidents,
        limitations=[
            "The model is an explainable decision-support heuristic, not a "
            "prediction or confirmed impact assessment.",
            "Category and severity priors are transparent model assumptions, "
            "not empirical outcome estimates.",
            "Infrastructure exposure is a geospatial association and may use "
            "development/unknown-provenance data.",
        ],
    )


def geojson_response(
    computation: RiskComputation, *, privacy: dict
) -> dict:
    features = []
    for cell in computation.cells:
        features.append(
            {
                "type": "Feature",
                "id": cell.h3_cell_id,
                "geometry": cell.boundary,
                "properties": {
                    "h3_cell_id": cell.h3_cell_id,
                    "resolution": cell.resolution,
                    "risk_score": cell.risk_score,
                    "incident_activity_score": cell.incident_activity_score,
                    "risk_category": cell.risk_category,
                    "confidence": cell.confidence,
                    "confidence_label": cell.confidence_label,
                    "incident_count": cell.incident_count,
                    "active_count": cell.active_count,
                    "trend_direction": cell.trend.direction,
                    "nearby_asset_count": cell.infrastructure.nearby_asset_count,
                },
            }
        )
    return {
        "type": "FeatureCollection",
        "features": features,
        "model_version": computation.config.model_version,
        "config_hash": computation.config.config_hash,
        "generated_at": computation.generated_at,
        "window_hours": computation.query.window_hours,
        "resolution": computation.query.resolution,
        "privacy": privacy,
        "limitations": list(computation.limitations),
    }
