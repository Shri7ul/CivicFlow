"""H3 aggregation, temporal comparison, and explainable cell scoring."""

from __future__ import annotations

import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable
from uuid import UUID

import h3
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    DependencyEdge,
    Incident,
    IncidentRelationship,
    IncidentStatus,
    InfrastructureAsset,
    RelationshipStatus,
    RelationshipType,
)
from app.risk.config import RiskConfig
from app.risk.exposure import (
    InfrastructureExposure,
    RiskAsset,
    compute_exposure,
)
from app.risk.geo import bbox_contains
from app.risk.scoring import (
    IncidentAggregate,
    IncidentRecord,
    InfrastructureFactor,
    ScoringResult,
    TrendResult,
    aggregate_incidents,
    aggregate_records,
    calculate_trend,
    deduplicate_incidents,
    score_aggregate,
    spatial_concentration,
    trend_signal,
)
from app.services.incidents import parse_point

STABLE_DELTA = 3.0
MAX_ASSETS = 5000


class RiskQueryError(Exception):
    """A bounded/validated risk query cannot be completed."""

    def __init__(self, message: str, *, code: str = "invalid_risk_query") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class RiskQuery:
    resolution: int
    window_hours: int
    bbox: tuple[float, float, float, float] | None = None
    limit: int = 100
    offset: int = 0
    min_score: float | None = None
    category: str | None = None


@dataclass(frozen=True)
class RiskCellResult:
    h3_cell_id: str
    resolution: int
    boundary: dict
    boundary_wkt: str
    center_latitude: float
    center_longitude: float
    risk_score: float
    incident_activity_score: float
    risk_category: str
    confidence: float
    confidence_label: str
    incident_count: int
    active_count: int
    adjusted_incident_count: int
    removed_duplicates: int
    severity_distribution: dict[str, int]
    category_distribution: dict[str, int]
    factors: tuple
    infrastructure: InfrastructureExposure
    trend: TrendResult
    model_version: str
    config_hash: str


@dataclass(frozen=True)
class RiskComputation:
    query: RiskQuery
    config: RiskConfig
    generated_at: datetime
    window_start: datetime
    window_end: datetime
    cells: tuple[RiskCellResult, ...]
    current_incidents: tuple[IncidentRecord, ...]
    previous_incidents: tuple[IncidentRecord, ...]
    history_coverage: float
    previous_history_coverage: float
    dataset: dict
    limitations: tuple[str, ...]
    duration_ms: int


@dataclass(frozen=True)
class RiskTrendCell:
    h3_cell_id: str
    resolution: int
    boundary: dict
    center_latitude: float
    center_longitude: float
    current_score: float
    previous_score: float
    delta_score: float
    direction: str
    direction_label: str
    current_incident_count: int
    previous_incident_count: int
    current_category: str
    confidence: float
    trend_reason: str


def _boundary(cell: str) -> tuple[dict, str, float, float]:
    latlngs = [
        (float(latitude), float(longitude))
        for latitude, longitude in h3.cell_to_boundary(cell)
    ]
    if latlngs[0] != latlngs[-1]:
        latlngs.append(latlngs[0])
    coordinates = [[longitude, latitude] for latitude, longitude in latlngs]
    wkt = "POLYGON((" + ", ".join(
        f"{longitude:.7f} {latitude:.7f}"
        for latitude, longitude in latlngs
    ) + "))"
    center_lat, center_lng = h3.cell_to_latlng(cell)
    return (
        {"type": "Polygon", "coordinates": [coordinates]},
        wkt,
        float(center_lat),
        float(center_lng),
    )


def _load_incidents(
    session: Session,
    *,
    start: datetime,
    end: datetime,
    bbox: tuple[float, float, float, float] | None,
    max_incidents: int,
) -> list[IncidentRecord]:
    statement = select(
        Incident.id,
        Incident.location,
        Incident.created_at,
        Incident.severity,
        Incident.category,
        Incident.status,
        Incident.reporter_id,
    ).where(Incident.created_at >= start, Incident.created_at <= end)
    if (
        bbox is not None
        and session.bind is not None
        and session.bind.dialect.name == "postgresql"
    ):
        min_lat, min_lon, max_lat, max_lon = bbox
        envelope = func.ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)
        # Incidents are stored as geography. Casting the envelope to geography
        # keeps the query sargable for the GIST index instead of converting
        # every incident geometry on the fly.
        envelope_geography = func.ST_GeogFromText(func.ST_AsText(envelope))
        statement = statement.where(
            func.ST_Intersects(Incident.location, envelope_geography)
        )
    rows = session.execute(
        statement.order_by(Incident.created_at).limit(max_incidents + 1)
    ).all()
    if len(rows) > max_incidents:
        raise RiskQueryError(
            "The requested risk query exceeds the incident limit. Narrow the "
            "bounding box or time window.",
            code="risk_query_too_large",
        )
    records: list[IncidentRecord] = []
    for row in rows:
        latitude, longitude = parse_point(row.location)
        if not bbox_contains(latitude, longitude, bbox):
            continue
        created_at = row.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        records.append(
            IncidentRecord(
                id=row.id,
                latitude=latitude,
                longitude=longitude,
                created_at=created_at,
                severity=row.severity,
                category=row.category,
                status=row.status,
                reporter_id=row.reporter_id,
            )
        )
    return records


def _load_assets(
    session: Session,
) -> tuple[list[RiskAsset], dict[UUID, int]]:
    assets = session.scalars(
        select(InfrastructureAsset)
        .where(InfrastructureAsset.is_active.is_(True))
        .limit(MAX_ASSETS)
    ).all()
    asset_ids = [asset.id for asset in assets]
    if asset_ids:
        edges = session.scalars(
            select(DependencyEdge).where(
                or_(
                    DependencyEdge.source_asset_id.in_(asset_ids),
                    DependencyEdge.target_asset_id.in_(asset_ids),
                )
            )
        ).all()
    else:
        edges = []
    counts: Counter[UUID] = Counter()
    for edge in edges:
        counts[edge.source_asset_id] += 1
        counts[edge.target_asset_id] += 1
    return (
        [
            RiskAsset(
                id=asset.id,
                name=asset.name,
                asset_type=asset.asset_type,
                criticality_score=float(asset.criticality_score),
                geometry_wkt=asset.location,
                source=(asset.metadata_json or {}).get("source"),
                metadata=asset.metadata_json or {},
            )
            for asset in assets
        ],
        dict(counts),
    )


def _confirmed_duplicate_pairs(
    session: Session, incident_ids: set[UUID]
) -> list[tuple[UUID, UUID]]:
    if not incident_ids:
        return []
    incident_id_list = list(incident_ids)
    relationships = session.scalars(
        select(IncidentRelationship).where(
            IncidentRelationship.status == RelationshipStatus.CONFIRMED,
            IncidentRelationship.relationship_type == RelationshipType.DUPLICATE,
            or_(
                IncidentRelationship.incident_a_id.in_(incident_id_list),
                IncidentRelationship.incident_b_id.in_(incident_id_list),
            ),
        )
    ).all()
    pairs: list[tuple[UUID, UUID]] = []
    for relationship in relationships:
        if (
            relationship.incident_a_id in incident_ids
            and relationship.incident_b_id in incident_ids
        ):
            pairs.append(
                (relationship.incident_a_id, relationship.incident_b_id)
            )
    return pairs


def _coverage(
    session: Session, *, start: datetime, end: datetime
) -> float:
    """Fraction of a requested window covered by available incident history."""
    earliest = session.scalar(select(func.min(Incident.created_at)))
    if earliest is None:
        return 0.0
    if earliest.tzinfo is None:
        earliest = earliest.replace(tzinfo=timezone.utc)
    start = start if start.tzinfo else start.replace(tzinfo=timezone.utc)
    end = end if end.tzinfo else end.replace(tzinfo=timezone.utc)
    if end <= start:
        return 0.0
    if earliest <= start:
        return 1.0
    if earliest >= end:
        return 0.0
    return max(
        0.0,
        min(
            1.0,
            (end - earliest).total_seconds()
            / (end - start).total_seconds(),
        ),
    )


def _incident_factor(
    exposure: InfrastructureExposure,
) -> InfrastructureFactor:
    return InfrastructureFactor(
        normalized=exposure.normalized,
        available=exposure.available,
        explanation=exposure.explanation,
        metadata={
            "nearby_asset_count": exposure.nearby_asset_count,
            "by_type": exposure.by_type,
            "dependency_count": exposure.dependency_count,
            "dataset": exposure.dataset,
        },
    )


def _score_cell(
    *,
    current_raw: Iterable[IncidentRecord],
    current_adjusted: Iterable[IncidentRecord],
    previous_raw: Iterable[IncidentRecord],
    previous_adjusted: Iterable[IncidentRecord],
    center_latitude: float,
    center_longitude: float,
    resolution: int,
    assets: list[RiskAsset],
    dependency_counts: dict[UUID, int],
    config: RiskConfig,
    now: datetime,
    history_coverage: float,
    previous_history_coverage: float,
) -> tuple[IncidentAggregate, ScoringResult, TrendResult, InfrastructureExposure]:
    current_aggregate = aggregate_records(current_raw, current_adjusted)
    previous_aggregate = aggregate_records(previous_raw, previous_adjusted)
    exposure = compute_exposure(
        latitude=center_latitude,
        longitude=center_longitude,
        assets=assets,
        dependency_counts=dependency_counts,
        radius_m=config.infrastructure_radius_m,
    )
    edge_length = h3.average_hexagon_edge_length(resolution, unit="m")
    current_spatial = spatial_concentration(
        current_aggregate.adjusted_incidents,
        center_latitude=center_latitude,
        center_longitude=center_longitude,
        cell_edge_length_m=edge_length,
    )
    previous_spatial = spatial_concentration(
        previous_aggregate.adjusted_incidents,
        center_latitude=center_latitude,
        center_longitude=center_longitude,
        cell_edge_length_m=edge_length,
    )
    current_trend = trend_signal(
        current_count=len(current_aggregate.adjusted_incidents),
        previous_count=len(previous_aggregate.adjusted_incidents),
        minimum_incidents=config.trend_min_incidents,
        history_coverage=previous_history_coverage,
    )
    score = score_aggregate(
        current_aggregate,
        config=config,
        now=now,
        infrastructure=_incident_factor(exposure),
        history_coverage=history_coverage,
        spatial_value=current_spatial,
        trend_value=current_trend,
    )
    previous_score = score_aggregate(
        previous_aggregate,
        config=config,
        now=now,
        infrastructure=InfrastructureFactor(
            normalized=None,
            available=False,
            explanation="Infrastructure exposure is excluded from trend comparison.",
            metadata={},
        ),
        history_coverage=history_coverage,
        spatial_value=previous_spatial,
    ).incident_activity_score
    trend = calculate_trend(
        current_score=score.incident_activity_score,
        previous_score=previous_score,
        current_count=len(current_aggregate.adjusted_incidents),
        previous_count=len(previous_aggregate.adjusted_incidents),
        config=config,
        stable_delta=STABLE_DELTA,
        history_coverage=previous_history_coverage,
    )
    return current_aggregate, score, trend, exposure


class RiskEngine:
    """Compute deterministic H3 risk cells from bounded incident queries."""

    def __init__(self, session: Session, config: RiskConfig) -> None:
        self.session = session
        self.config = config

    def validate(self, query: RiskQuery) -> None:
        if not self.config.min_resolution <= query.resolution <= self.config.max_resolution:
            raise RiskQueryError(
                f"resolution must be between {self.config.min_resolution} and "
                f"{self.config.max_resolution}",
                code="invalid_resolution",
            )
        if not 1 <= query.window_hours <= self.config.max_window_hours:
            raise RiskQueryError(
                f"window_hours must be between 1 and {self.config.max_window_hours}",
                code="invalid_window",
            )
        if query.limit < 1 or query.limit > self.config.max_cells:
            raise RiskQueryError(
                f"limit must be between 1 and {self.config.max_cells}",
                code="invalid_limit",
            )
        if query.bbox is not None:
            min_lat, min_lon, max_lat, max_lon = query.bbox
            if not (
                -90 <= min_lat < max_lat <= 90
                and -180 <= min_lon < max_lon <= 180
            ):
                raise RiskQueryError(
                    "bbox must be an ordered WGS84 bounding box",
                    code="invalid_bbox",
                )

    def compute(
        self,
        query: RiskQuery,
        *,
        include_previous_only: bool = False,
    ) -> RiskComputation:
        started = time.perf_counter()
        self.validate(query)
        now = datetime.now(timezone.utc)
        window_end = now
        window_start = now - timedelta(hours=query.window_hours)
        previous_start = window_start - timedelta(hours=query.window_hours)
        incidents = _load_incidents(
            self.session,
            start=previous_start,
            end=window_end,
            bbox=query.bbox,
            max_incidents=self.config.max_incidents,
        )
        current_incidents = [
            incident for incident in incidents if incident.created_at >= window_start
        ]
        previous_incidents = [
            incident for incident in incidents if incident.created_at < window_start
        ]
        current_by_cell: dict[str, list[IncidentRecord]] = defaultdict(list)
        previous_by_cell: dict[str, list[IncidentRecord]] = defaultdict(list)
        for incident in current_incidents:
            cell = h3.latlng_to_cell(
                incident.latitude, incident.longitude, query.resolution
            )
            current_by_cell[cell].append(incident)
        for incident in previous_incidents:
            cell = h3.latlng_to_cell(
                incident.latitude, incident.longitude, query.resolution
            )
            previous_by_cell[cell].append(incident)

        all_incident_ids = {incident.id for incident in incidents}
        duplicate_pairs = _confirmed_duplicate_pairs(
            self.session, all_incident_ids
        )
        # Deduplicate globally across the whole loaded horizon before assigning
        # cells. This prevents a confirmed duplicate cluster from being counted
        # once in the current window and again in the comparison window, and
        # also prevents boundary straddling from inflating adjacent cells.
        adjusted_all = deduplicate_incidents(incidents, duplicate_pairs)
        current_adjusted = [
            incident
            for incident in adjusted_all
            if incident.created_at >= window_start
        ]
        previous_adjusted = [
            incident
            for incident in adjusted_all
            if incident.created_at < window_start
        ]
        current_adjusted_by_cell: dict[str, list[IncidentRecord]] = defaultdict(list)
        previous_adjusted_by_cell: dict[str, list[IncidentRecord]] = defaultdict(list)
        for incident in current_adjusted:
            current_adjusted_by_cell[
                h3.latlng_to_cell(
                    incident.latitude, incident.longitude, query.resolution
                )
            ].append(incident)
        for incident in previous_adjusted:
            previous_adjusted_by_cell[
                h3.latlng_to_cell(
                    incident.latitude, incident.longitude, query.resolution
                )
            ].append(incident)

        assets, dependency_counts = _load_assets(self.session)
        coverage = _coverage(
            self.session, start=window_start, end=window_end
        )
        previous_coverage = _coverage(
            self.session, start=previous_start, end=window_start
        )
        cells: list[RiskCellResult] = []
        for cell, current in current_by_cell.items():
            boundary, wkt, center_lat, center_lng = _boundary(cell)
            aggregate, score, trend, exposure = _score_cell(
                current_raw=current,
                current_adjusted=current_adjusted_by_cell.get(cell, []),
                previous_raw=previous_by_cell.get(cell, []),
                previous_adjusted=previous_adjusted_by_cell.get(cell, []),
                center_latitude=center_lat,
                center_longitude=center_lng,
                resolution=query.resolution,
                assets=assets,
                dependency_counts=dependency_counts,
                config=self.config,
                now=now,
                history_coverage=coverage,
                previous_history_coverage=previous_coverage,
            )
            cells.append(
                RiskCellResult(
                    h3_cell_id=cell,
                    resolution=query.resolution,
                    boundary=boundary,
                    boundary_wkt=wkt,
                    center_latitude=center_lat,
                    center_longitude=center_lng,
                    risk_score=score.risk_score,
                    incident_activity_score=score.incident_activity_score,
                    risk_category=score.risk_category.value,
                    confidence=score.confidence,
                    confidence_label=score.confidence_label,
                    incident_count=len(aggregate.raw_incidents),
                    active_count=aggregate.active_count,
                    adjusted_incident_count=len(aggregate.adjusted_incidents),
                    removed_duplicates=aggregate.removed_duplicates,
                    severity_distribution=aggregate.severity_counts,
                    category_distribution=aggregate.category_counts,
                    factors=score.factors,
                    infrastructure=exposure,
                    trend=trend,
                    model_version=self.config.model_version,
                    config_hash=self.config.config_hash,
                )
            )
        if include_previous_only:
            existing = {cell.h3_cell_id for cell in cells}
            for cell, previous in previous_by_cell.items():
                if len(cells) >= self.config.max_cells:
                    break
                if cell in existing:
                    continue
                previous_adjusted = previous_adjusted_by_cell.get(cell, [])
                if not previous_adjusted:
                    continue
                boundary, wkt, center_lat, center_lng = _boundary(cell)
                previous_aggregate = aggregate_records(
                    previous, previous_adjusted
                )
                previous_spatial = spatial_concentration(
                    previous_aggregate.adjusted_incidents,
                    center_latitude=center_lat,
                    center_longitude=center_lng,
                    cell_edge_length_m=h3.average_hexagon_edge_length(
                        query.resolution, unit="m"
                    ),
                )
                previous_score = score_aggregate(
                    previous_aggregate,
                    config=self.config,
                    now=now,
                    infrastructure=InfrastructureFactor(
                        normalized=None,
                        available=False,
                        explanation="No current-period incidents.",
                        metadata={},
                    ),
                    history_coverage=coverage,
                    spatial_value=previous_spatial,
                )
                trend = calculate_trend(
                    current_score=0.0,
                    previous_score=previous_score.incident_activity_score,
                    current_count=0,
                    previous_count=len(previous_aggregate.adjusted_incidents),
                    config=self.config,
                    stable_delta=STABLE_DELTA,
                    history_coverage=previous_coverage,
                )
                cells.append(
                    RiskCellResult(
                        h3_cell_id=cell,
                        resolution=query.resolution,
                        boundary=boundary,
                        boundary_wkt=wkt,
                        center_latitude=center_lat,
                        center_longitude=center_lng,
                        risk_score=0.0,
                        incident_activity_score=0.0,
                        risk_category="MINIMAL",
                        confidence=0.0,
                        confidence_label="low",
                        incident_count=0,
                        active_count=0,
                        adjusted_incident_count=0,
                        removed_duplicates=previous_aggregate.removed_duplicates,
                        severity_distribution={},
                        category_distribution={},
                        factors=(),
                        infrastructure=compute_exposure(
                            latitude=center_lat,
                            longitude=center_lng,
                            assets=assets,
                            dependency_counts=dependency_counts,
                            radius_m=self.config.infrastructure_radius_m,
                        ),
                        trend=trend,
                        model_version=self.config.model_version,
                        config_hash=self.config.config_hash,
                    )
                )
        cells.sort(key=lambda cell: (-cell.risk_score, cell.h3_cell_id))
        if len(cells) > self.config.max_cells:
            raise RiskQueryError(
                f"The query produced more than {self.config.max_cells} cells. "
                "Narrow the bounding box or choose a coarser resolution.",
                code="risk_too_many_cells",
            )
        dataset = {
            "active_asset_count": len(assets),
            "authoritative_asset_count": sum(
                1
                for asset in assets
                if asset.metadata.get("authoritative") is True
            ),
            "development_or_unknown_asset_count": sum(
                1
                for asset in assets
                if asset.metadata.get("authoritative") is not True
            ),
            "asset_limit_reached": len(assets) >= MAX_ASSETS,
        }
        limitations = [
            "Risk is a transparent decision-support score, not a prediction, "
            "confirmed impact, or replacement for field assessment.",
            "Observed incident activity is combined with inferred infrastructure "
            "exposure; the API reports both scores separately.",
            "Dependency exposure is geospatial association and is not a "
            "confirmed service outage or cascade.",
            "Only WORKER/ADMIN-confirmed DUPLICATE relationships adjust incident "
            "activity; unresolved suggestions are not treated as truth.",
            "Citizen responses apply a minimum-cell-count privacy rule and "
            "never expose another Citizen's incident details.",
            "Infrastructure records are development/unknown-provenance data "
            "unless the deployment has loaded an authoritative dataset.",
        ]
        if dataset["asset_limit_reached"]:
            limitations.append(
                f"Infrastructure asset loading is capped at {MAX_ASSETS}; "
                "exposure may be incomplete."
            )
        if coverage < 1.0 or previous_coverage < 1.0:
            limitations.append(
                "Historical coverage is incomplete for the requested current "
                "or comparison window; confidence is reduced and trends may "
                "be unavailable."
            )
        return RiskComputation(
            query=query,
            config=self.config,
            generated_at=now,
            window_start=window_start,
            window_end=window_end,
            cells=tuple(cells),
            current_incidents=tuple(current_incidents),
            previous_incidents=tuple(previous_incidents),
            history_coverage=round(coverage, 3),
            previous_history_coverage=round(previous_coverage, 3),
            dataset=dataset,
            limitations=tuple(limitations),
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
