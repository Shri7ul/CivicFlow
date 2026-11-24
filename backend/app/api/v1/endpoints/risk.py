"""Urban risk engine API endpoints."""

from __future__ import annotations

import h3
from dataclasses import replace
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser, require_active_user, require_worker
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.db.session import get_db_session
from app.models import Incident, RiskCategory
from app.risk.config import RiskConfig
from app.governance.service import resolve_risk_config
from app.ingestion.service import quality_overview
from app.risk.engine import (
    RiskCellResult,
    RiskComputation,
    RiskEngine,
    RiskQuery,
    RiskQueryError,
)
from app.risk.persistence import list_runs, persist_run
from app.risk.serialization import (
    cell_response,
    config_response,
    geojson_response,
    privacy_redact_trend,
    summary_response,
    trend_response,
)
from app.schemas.risk import (
    RiskBBoxRequest,
    RiskCellDetailResponse,
    RiskCellsResponse,
    RiskConfigResponse,
    RiskGeoJSONResponse,
    RiskIncidentBrief,
    RiskInfrastructureSummaryResponse,
    RiskRunListResponse,
    RiskRunListItem,
    RiskRunRequest,
    RiskRunResponse,
    RiskSummaryResponse,
    RiskTrendCellResponse,
    RiskTrendsResponse,
)
from app.services.incidents import is_staff

router = APIRouter()
WINDOW_ALIASES = {"current": None, "24h": 24, "7d": 168, "30d": 720}


def _risk_config(
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[Session, Depends(get_db_session)],
) -> RiskConfig:
    return resolve_risk_config(session, settings)


def _window_hours(
    *,
    window: str | None,
    window_hours: int | None,
    config: RiskConfig,
) -> int:
    if window is not None and window_hours is not None:
        raise AppError(
            "Use either window or window_hours, not both.",
            status_code=422,
            code="invalid_window",
        )
    if window is not None:
        if window not in WINDOW_ALIASES:
            raise AppError(
                "window must be one of current, 24h, 7d, or 30d.",
                status_code=422,
                code="invalid_window",
            )
        return WINDOW_ALIASES[window] or config.default_window_hours
    return window_hours or config.default_window_hours


def _bbox(
    *,
    min_latitude: float | None,
    min_longitude: float | None,
    max_latitude: float | None,
    max_longitude: float | None,
) -> tuple[float, float, float, float] | None:
    try:
        payload = RiskBBoxRequest(
            min_latitude=min_latitude,
            min_longitude=min_longitude,
            max_latitude=max_latitude,
            max_longitude=max_longitude,
        )
    except ValueError as exc:
        raise AppError(
            "bbox must be supplied as four ordered WGS84 coordinates.",
            status_code=422,
            code="invalid_bbox",
        ) from exc
    if payload.min_latitude is None:
        return None
    return (
        payload.min_latitude,
        payload.min_longitude,
        payload.max_latitude,
        payload.max_longitude,
    )


def _query(
    *,
    config: RiskConfig,
    resolution: int | None,
    window_hours: int | None,
    bbox: tuple[float, float, float, float] | None,
    limit: int,
    offset: int = 0,
    min_score: float | None = None,
    category: RiskCategory | None = None,
) -> RiskQuery:
    return RiskQuery(
        resolution=resolution or config.default_resolution,
        window_hours=window_hours or config.default_window_hours,
        bbox=bbox,
        limit=limit,
        offset=offset,
        min_score=min_score,
        category=category.value if category else None,
    )


def _filtered_computation(
    computation: RiskComputation,
    *,
    user: AuthenticatedUser,
    config: RiskConfig,
) -> tuple[RiskComputation, dict]:
    cells = list(computation.cells)
    if not is_staff(user):
        cells = [
            cell
            for cell in cells
            if cell.incident_count >= config.privacy_min_incidents
        ]
        cells = [
            replace(
                cell,
                trend=privacy_redact_trend(
                    cell.trend,
                    minimum_incidents=config.privacy_min_incidents,
                ),
            )
            for cell in cells
        ]
    privacy = {
        "citizen_min_incidents": config.privacy_min_incidents,
        "applied": not is_staff(user),
        "suppressed_cells": len(computation.cells) - len(cells),
    }
    return replace(computation, cells=tuple(cells)), privacy


def _apply_cell_filters(
    computation: RiskComputation,
    *,
    min_score: float | None,
    category: RiskCategory | None,
) -> RiskComputation:
    cells = computation.cells
    if category is not None:
        cells = tuple(cell for cell in cells if cell.risk_category == category.value)
    if min_score is not None:
        cells = tuple(cell for cell in cells if cell.risk_score >= min_score)
    return replace(computation, cells=cells)


def _raise_engine_error(error: RiskQueryError) -> None:
    raise AppError(str(error), status_code=422, code=error.code) from error


@router.get(
    "/config",
    response_model=RiskConfigResponse,
    summary="Risk model version, weights, thresholds, and H3 bounds",
)
def risk_config(
    user: Annotated[AuthenticatedUser, Depends(require_active_user)],
    config: Annotated[RiskConfig, Depends(_risk_config)],
) -> RiskConfigResponse:
    del user
    return config_response(config)


@router.get(
    "/cells",
    response_model=None,
    summary="H3 risk cells with factors, trends, and infrastructure exposure",
)
def risk_cells(
    user: Annotated[AuthenticatedUser, Depends(require_active_user)],
    session: Annotated[Session, Depends(get_db_session)],
    config: Annotated[RiskConfig, Depends(_risk_config)],
    resolution: Annotated[int | None, Query(ge=5, le=12)] = None,
    window: str | None = None,
    window_hours: Annotated[int | None, Query(ge=1, le=8760)] = None,
    min_latitude: Annotated[float | None, Query(ge=-90, le=90)] = None,
    min_longitude: Annotated[float | None, Query(ge=-180, le=180)] = None,
    max_latitude: Annotated[float | None, Query(ge=-90, le=90)] = None,
    max_longitude: Annotated[float | None, Query(ge=-180, le=180)] = None,
    min_score: Annotated[float | None, Query(ge=0, le=100)] = None,
    category: RiskCategory | None = None,
    limit: Annotated[int | None, Query(ge=1, le=2000)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    format: Literal["json", "geojson"] = "json",
) -> RiskCellsResponse | RiskGeoJSONResponse:
    bbox = _bbox(
        min_latitude=min_latitude,
        min_longitude=min_longitude,
        max_latitude=max_latitude,
        max_longitude=max_longitude,
    )
    query = _query(
        config=config,
        resolution=resolution,
        window_hours=_window_hours(
            window=window, window_hours=window_hours, config=config
        ),
        bbox=bbox,
        limit=limit or config.max_cells,
        offset=offset,
        min_score=min_score,
        category=category,
    )
    engine = RiskEngine(session, config)
    try:
        computation = engine.compute(query)
    except RiskQueryError as error:
        _raise_engine_error(error)
    computation, privacy = _filtered_computation(
        computation, user=user, config=config
    )
    computation = _apply_cell_filters(
        computation, min_score=min_score, category=category
    )
    total = len(computation.cells)
    page_cells = computation.cells[offset : offset + query.limit]
    if format == "geojson":
        page = replace(computation, cells=page_cells)
        return RiskGeoJSONResponse(**geojson_response(page, privacy=privacy))
    summary = summary_response(computation)
    return RiskCellsResponse(
        items=[
            cell_response(cell, calculated_at=computation.generated_at)
            for cell in page_cells
        ],
        total=total,
        offset=offset,
        limit=query.limit,
        resolution=query.resolution,
        window_hours=query.window_hours,
        window_start=computation.window_start,
        window_end=computation.window_end,
        generated_at=computation.generated_at,
        model_version=config.model_version,
        config_hash=config.config_hash,
        history_coverage=computation.history_coverage,
        dataset={
            "active_asset_count": computation.dataset["active_asset_count"],
            "authoritative_asset_count": computation.dataset[
                "authoritative_asset_count"
            ],
            "development_or_unknown_asset_count": computation.dataset[
                "development_or_unknown_asset_count"
            ],
            "asset_limit_reached": computation.dataset["asset_limit_reached"],
            "is_authoritative": (
                computation.dataset["authoritative_asset_count"]
                == computation.dataset["active_asset_count"]
                and computation.dataset["active_asset_count"] > 0
            ),
        },
        privacy=privacy,
        summary=summary,
        limitations=list(computation.limitations),
    )


@router.get(
    "/summary",
    response_model=RiskSummaryResponse,
    summary="Urban risk distribution and top cells for the selected filters",
)
def risk_summary(
    user: Annotated[AuthenticatedUser, Depends(require_active_user)],
    session: Annotated[Session, Depends(get_db_session)],
    config: Annotated[RiskConfig, Depends(_risk_config)],
    resolution: Annotated[int | None, Query(ge=5, le=12)] = None,
    window: str | None = None,
    window_hours: Annotated[int | None, Query(ge=1, le=8760)] = None,
    min_latitude: Annotated[float | None, Query(ge=-90, le=90)] = None,
    min_longitude: Annotated[float | None, Query(ge=-180, le=180)] = None,
    max_latitude: Annotated[float | None, Query(ge=-90, le=90)] = None,
    max_longitude: Annotated[float | None, Query(ge=-180, le=180)] = None,
    min_score: Annotated[float | None, Query(ge=0, le=100)] = None,
    category: RiskCategory | None = None,
) -> RiskSummaryResponse:
    query = _query(
        config=config,
        resolution=resolution,
        window_hours=_window_hours(
            window=window, window_hours=window_hours, config=config
        ),
        bbox=_bbox(
            min_latitude=min_latitude,
            min_longitude=min_longitude,
            max_latitude=max_latitude,
            max_longitude=max_longitude,
        ),
        limit=config.max_cells,
        min_score=min_score,
        category=category,
    )
    try:
        computation = RiskEngine(session, config).compute(query)
    except RiskQueryError as error:
        _raise_engine_error(error)
    computation, _privacy = _filtered_computation(
        computation, user=user, config=config
    )
    computation = _apply_cell_filters(
        computation, min_score=min_score, category=category
    )
    return summary_response(computation)


@router.get(
    "/cells/{cell_id}",
    response_model=RiskCellDetailResponse,
    summary="Explain one H3 risk cell, with authorized incident briefs",
)
def risk_cell_detail(
    cell_id: str,
    user: Annotated[AuthenticatedUser, Depends(require_active_user)],
    session: Annotated[Session, Depends(get_db_session)],
    config: Annotated[RiskConfig, Depends(_risk_config)],
    resolution: Annotated[int | None, Query(ge=5, le=12)] = None,
    window: str | None = None,
    window_hours: Annotated[int | None, Query(ge=1, le=8760)] = None,
) -> RiskCellDetailResponse:
    query = _query(
        config=config,
        resolution=resolution,
        window_hours=_window_hours(
            window=window, window_hours=window_hours, config=config
        ),
        bbox=None,
        limit=config.max_cells,
    )
    if not h3.is_valid_cell(cell_id) or h3.get_resolution(cell_id) != query.resolution:
        raise AppError(
            "Risk cell not found.",
            status_code=404,
            code="risk_cell_not_found",
        )
    try:
        computation = RiskEngine(session, config).compute(
            query, include_previous_only=True
        )
    except RiskQueryError as error:
        _raise_engine_error(error)
    cell = next(
        (candidate for candidate in computation.cells if candidate.h3_cell_id == cell_id),
        None,
    )
    if cell is None or (
        not is_staff(user) and cell.incident_count < config.privacy_min_incidents
    ):
        raise AppError(
            "Risk cell not found.",
            status_code=404,
            code="risk_cell_not_found",
        )
    if not is_staff(user):
        cell = replace(
            cell,
            trend=privacy_redact_trend(
                cell.trend,
                minimum_incidents=config.privacy_min_incidents,
            ),
        )
    base = cell_response(cell, calculated_at=computation.generated_at)
    ids = [
        incident.id
        for incident in computation.current_incidents
        if _cell_for(incident.latitude, incident.longitude, query.resolution) == cell_id
    ]
    incidents: list[Incident] = []
    if ids:
        incidents = list(
            session.scalars(
                select(Incident)
                .where(Incident.id.in_(ids))
                .order_by(Incident.created_at.desc())
                .limit(100)
            ).all()
        )
        if not is_staff(user):
            incidents = [
                incident
                for incident in incidents
                if incident.reporter_id == user.profile.id
            ]
    return RiskCellDetailResponse(
        **base.model_dump(),
        incidents=[
            RiskIncidentBrief(
                id=incident.id,
                title=incident.title,
                category=incident.category.value,
                severity=incident.severity.value,
                status=incident.status.value,
                created_at=incident.created_at,
            )
            for incident in incidents
        ],
        limitations=list(computation.limitations),
    )


def _cell_for(latitude: float, longitude: float, resolution: int) -> str:
    return h3.latlng_to_cell(latitude, longitude, resolution)


@router.get(
    "/trends",
    response_model=RiskTrendsResponse,
    summary="Cell-level current vs previous-window risk changes",
)
def risk_trends(
    user: Annotated[AuthenticatedUser, Depends(require_active_user)],
    session: Annotated[Session, Depends(get_db_session)],
    config: Annotated[RiskConfig, Depends(_risk_config)],
    resolution: Annotated[int | None, Query(ge=5, le=12)] = None,
    window: str | None = None,
    window_hours: Annotated[int | None, Query(ge=1, le=8760)] = None,
    min_latitude: Annotated[float | None, Query(ge=-90, le=90)] = None,
    min_longitude: Annotated[float | None, Query(ge=-180, le=180)] = None,
    max_latitude: Annotated[float | None, Query(ge=-90, le=90)] = None,
    max_longitude: Annotated[float | None, Query(ge=-180, le=180)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RiskTrendsResponse:
    query = _query(
        config=config,
        resolution=resolution,
        window_hours=_window_hours(
            window=window, window_hours=window_hours, config=config
        ),
        bbox=_bbox(
            min_latitude=min_latitude,
            min_longitude=min_longitude,
            max_latitude=max_latitude,
            max_longitude=max_longitude,
        ),
        limit=config.max_cells,
    )
    try:
        computation = RiskEngine(session, config).compute(
            query, include_previous_only=True
        )
    except RiskQueryError as error:
        _raise_engine_error(error)
    cells = list(computation.cells)
    if not is_staff(user):
        cells = [
            cell
            for cell in cells
            if cell.trend.current_incident_count
            >= config.privacy_min_incidents
            and cell.trend.previous_incident_count
            >= config.privacy_min_incidents
        ]
    cells.sort(key=lambda cell: -abs(cell.trend.delta_score))
    total = len(cells)
    page = cells[offset : offset + limit]
    counts = {
        "INCREASING": sum(1 for cell in cells if cell.trend.direction == "INCREASING"),
        "DECREASING": sum(1 for cell in cells if cell.trend.direction == "DECREASING"),
        "STABLE": sum(1 for cell in cells if cell.trend.direction == "STABLE"),
        "INSUFFICIENT_DATA": sum(
            1 for cell in cells if cell.trend.direction == "INSUFFICIENT_DATA"
        ),
        "total": total,
    }
    return RiskTrendsResponse(
        items=[
            RiskTrendCellResponse(
                h3_cell_id=cell.h3_cell_id,
                resolution=cell.resolution,
                boundary=cell.boundary,
                center_latitude=cell.center_latitude,
                center_longitude=cell.center_longitude,
                current_score=cell.trend.current_score,
                previous_score=cell.trend.previous_score,
                delta_score=cell.trend.delta_score,
                direction=cell.trend.direction,
                direction_label=cell.trend.label,
                current_incident_count=cell.trend.current_incident_count,
                previous_incident_count=cell.trend.previous_incident_count,
                current_category=RiskCategory(cell.risk_category),
                confidence=cell.confidence,
                reason=cell.trend.reason,
            )
            for cell in page
        ],
        counts=counts,
        resolution=query.resolution,
        window_hours=query.window_hours,
        window_start=computation.window_start,
        window_end=computation.window_end,
        generated_at=computation.generated_at,
        model_version=config.model_version,
        config_hash=config.config_hash,
        privacy={
            "citizen_min_incidents": config.privacy_min_incidents,
            "applied": not is_staff(user),
        },
        limitations=list(computation.limitations),
    )


@router.get(
    "/infrastructure-exposure",
    response_model=RiskInfrastructureSummaryResponse,
    summary="Aggregate inferred infrastructure exposure for current risk cells",
)
def risk_infrastructure_exposure(
    user: Annotated[AuthenticatedUser, Depends(require_active_user)],
    session: Annotated[Session, Depends(get_db_session)],
    config: Annotated[RiskConfig, Depends(_risk_config)],
    resolution: Annotated[int | None, Query(ge=5, le=12)] = None,
    window: str | None = None,
    window_hours: Annotated[int | None, Query(ge=1, le=8760)] = None,
    min_latitude: Annotated[float | None, Query(ge=-90, le=90)] = None,
    min_longitude: Annotated[float | None, Query(ge=-180, le=180)] = None,
    max_latitude: Annotated[float | None, Query(ge=-90, le=90)] = None,
    max_longitude: Annotated[float | None, Query(ge=-180, le=180)] = None,
) -> RiskInfrastructureSummaryResponse:
    query = _query(
        config=config,
        resolution=resolution,
        window_hours=_window_hours(
            window=window, window_hours=window_hours, config=config
        ),
        bbox=_bbox(
            min_latitude=min_latitude,
            min_longitude=min_longitude,
            max_latitude=max_latitude,
            max_longitude=max_longitude,
        ),
        limit=config.max_cells,
    )
    try:
        computation = RiskEngine(session, config).compute(query)
    except RiskQueryError as error:
        _raise_engine_error(error)
    computation, _privacy = _filtered_computation(
        computation, user=user, config=config
    )
    by_type: dict[str, int] = {}
    assets: dict[str, dict] = {}
    exposed_cells = 0
    authoritative_cells = 0
    for cell in computation.cells:
        exposure = cell.infrastructure
        if exposure.nearby_asset_count > 0:
            exposed_cells += 1
        if exposure.dataset.get("is_authoritative"):
            authoritative_cells += 1
        for asset_type, count in exposure.by_type.items():
            by_type[asset_type] = by_type.get(asset_type, 0) + count
        for item in exposure.items:
            key = str(item.id)
            current = assets.get(key)
            if current is None:
                assets[key] = {
                    "id": key,
                    "name": item.name,
                    "asset_type": item.asset_type,
                    "criticality_score": item.criticality_score,
                    "minimum_distance_m": item.distance_m,
                    "dependency_count": item.dependency_count,
                    "source": item.source,
                    "exposed_cell_count": 1,
                }
            else:
                current["exposed_cell_count"] += 1
                current["minimum_distance_m"] = min(
                    current["minimum_distance_m"], item.distance_m
                )
    top_assets = sorted(
        assets.values(), key=lambda item: (-item["exposed_cell_count"], item["name"])
    )[:10]
    return RiskInfrastructureSummaryResponse(
        total_cells=len(computation.cells),
        exposed_cells=exposed_cells,
        cells_with_authoritative_dataset=authoritative_cells,
        by_asset_type=by_type,
        top_assets=top_assets,
        dataset={
            "active_asset_count": computation.dataset["active_asset_count"],
            "authoritative_asset_count": computation.dataset[
                "authoritative_asset_count"
            ],
            "development_or_unknown_asset_count": computation.dataset[
                "development_or_unknown_asset_count"
            ],
            "asset_limit_reached": computation.dataset["asset_limit_reached"],
            "is_authoritative": (
                computation.dataset["authoritative_asset_count"]
                == computation.dataset["active_asset_count"]
                and computation.dataset["active_asset_count"] > 0
            ),
        },
        limitations=list(computation.limitations)
        + [
            "Exposure is geospatial proximity and dependency context; it is "
            "not a confirmed outage, damage, or service-impact finding."
        ],
    )


@router.post(
    "/runs",
    response_model=RiskRunResponse,
    summary="Persist a staff-triggered risk run for audit/history",
)
def create_risk_run(
    payload: RiskRunRequest,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
    config: Annotated[RiskConfig, Depends(_risk_config)],
) -> RiskRunResponse:
    bbox = None
    if payload.bbox is not None and payload.bbox.min_latitude is not None:
        bbox = (
            payload.bbox.min_latitude,
            payload.bbox.min_longitude,
            payload.bbox.max_latitude,
            payload.bbox.max_longitude,
        )
        if any(value is None for value in bbox):
            raise AppError(
                "bbox must be supplied as four ordered WGS84 coordinates.",
                status_code=422,
                code="invalid_bbox",
            )
        bbox = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
    query = _query(
        config=config,
        resolution=payload.resolution,
        window_hours=payload.window_hours,
        bbox=bbox,
        limit=payload.limit,
    )
    try:
        computation = RiskEngine(session, config).compute(query)
    except RiskQueryError as error:
        _raise_engine_error(error)
    summary = summary_response(computation)
    try:
        run = persist_run(
            session,
            computation=computation,
            requested_by=user.profile.id,
            summary=summary.model_dump(mode="json"),
        )
    except Exception:
        session.rollback()
        raise
    return RiskRunResponse(
        run_id=run.id,
        generated_at=run.calculated_at,
        resolution=run.resolution,
        window_hours=run.window_hours,
        cell_count=run.cell_count,
        incident_count=run.incident_count,
        model_version=run.model_version,
        config_hash=run.config_hash,
        summary=summary,
    )


@router.get(
    "/data-quality",
    summary="Staff-visible data-source freshness and quality warnings",
)
def risk_data_quality(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> list[dict]:
    del user
    return [
        {
            "source_id": str(item["source"].id),
            "source_key": item["source"].source_key,
            "name": item["source"].name,
            "reliability": item["source"].reliability.value,
            "status": item["status"].value,
            "freshness_minutes": item["freshness_minutes"],
            "issues": item["issues"],
        }
        for item in quality_overview(session)
    ]


@router.get(
    "/runs",
    response_model=RiskRunListResponse,
    summary="List persisted staff-triggered risk runs",
)
def risk_runs(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> RiskRunListResponse:
    del user
    return RiskRunListResponse(
        items=[
            RiskRunListItem(
                run_id=run.id,
                generated_at=run.calculated_at,
                resolution=run.resolution,
                window_hours=run.window_hours,
                cell_count=run.cell_count,
                incident_count=run.incident_count,
                model_version=run.model_version,
                config_hash=run.config_hash,
            )
            for run in list_runs(session, limit=50)
        ]
    )
