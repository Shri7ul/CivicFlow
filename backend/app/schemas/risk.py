"""API schemas for explainable H3 urban risk intelligence."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import RiskCategory


class RiskFactorResponse(BaseModel):
    key: str
    label: str
    raw_value: float | int | str | None
    normalized: float | None
    weight: float
    contribution: float
    available: bool
    explanation: str


class RiskBandResponse(BaseModel):
    category: RiskCategory
    label: str
    color: str
    min_score: float
    max_score: float


class RiskTrendResponse(BaseModel):
    available: bool
    direction: str
    direction_label: str
    delta_score: float
    current_score: float
    previous_score: float
    current_incident_count: int
    previous_incident_count: int
    reason: str


class RiskAssetExposureResponse(BaseModel):
    id: uuid.UUID
    name: str
    asset_type: str
    criticality_score: float
    distance_m: float
    dependency_count: int
    source: str | None


class RiskInfrastructureResponse(BaseModel):
    available: bool
    nearby_asset_count: int
    by_type: dict[str, int]
    dependency_count: int
    normalized_exposure: float | None
    assets: list[RiskAssetExposureResponse]
    dataset: dict
    explanation: str


class RiskCellBrief(BaseModel):
    h3_cell_id: str
    resolution: int
    center_latitude: float
    center_longitude: float
    risk_score: float
    risk_category: RiskCategory
    confidence: float
    confidence_label: str
    incident_count: int
    active_count: int
    trend_direction: str


class RiskCellResponse(BaseModel):
    h3_cell_id: str
    resolution: int
    boundary: dict
    center_latitude: float
    center_longitude: float
    risk_score: float
    incident_activity_score: float
    risk_category: RiskCategory
    confidence: float
    confidence_label: str
    incident_count: int
    active_count: int
    adjusted_incident_count: int
    removed_duplicates: int
    severity_distribution: dict[str, int]
    category_distribution: dict[str, int]
    factors: list[RiskFactorResponse]
    infrastructure: RiskInfrastructureResponse
    trend: RiskTrendResponse
    calculated_at: datetime
    model_version: str
    config_hash: str


class RiskIncidentBrief(BaseModel):
    id: uuid.UUID
    title: str
    category: str
    severity: str
    status: str
    created_at: datetime


class RiskCellDetailResponse(RiskCellResponse):
    incidents: list[RiskIncidentBrief] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class RiskDatasetResponse(BaseModel):
    active_asset_count: int
    authoritative_asset_count: int
    development_or_unknown_asset_count: int
    asset_limit_reached: bool = False
    is_authoritative: bool = False


class RiskSummaryResponse(BaseModel):
    total_cells: int
    current_incident_count: int
    adjusted_incident_count: int
    duplicate_adjusted_count: int
    category_distribution: dict[str, int]
    high_critical_cells: int
    increasing_cells: int
    decreasing_cells: int
    stable_cells: int
    insufficient_trend_cells: int
    mean_risk_score: float
    max_risk_score: float
    mean_incident_activity_score: float
    mean_confidence: float
    exposure_cells: int
    exposure_asset_count: int
    factor_means: dict[str, float]
    top_cells: list[RiskCellBrief]
    dataset: RiskDatasetResponse
    history_coverage: float


class RiskCellsResponse(BaseModel):
    items: list[RiskCellResponse]
    total: int
    offset: int
    limit: int
    resolution: int
    window_hours: int
    window_start: datetime
    window_end: datetime
    generated_at: datetime
    model_version: str
    config_hash: str
    history_coverage: float
    dataset: RiskDatasetResponse
    privacy: dict
    summary: RiskSummaryResponse
    limitations: list[str]


class RiskGeoJSONResponse(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[dict]
    model_version: str
    config_hash: str
    generated_at: datetime
    window_hours: int
    resolution: int
    privacy: dict
    limitations: list[str]


class RiskConfigResponse(BaseModel):
    model_version: str
    config_hash: str
    factor_weights: dict[str, float]
    factor_labels: dict[str, str]
    severity_weights: dict[str, float]
    category_weights: dict[str, float]
    bands: list[RiskBandResponse]
    resolutions: dict[str, int]
    windows: dict[str, int]
    recency_half_life_hours: float
    density_saturation: int
    infrastructure_radius_m: int
    max_incidents: int
    max_cells: int
    privacy_min_incidents: int
    trend_min_incidents: int
    limitations: list[str]


class RiskTrendCellResponse(BaseModel):
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
    current_category: RiskCategory
    confidence: float
    reason: str


class RiskTrendsResponse(BaseModel):
    items: list[RiskTrendCellResponse]
    counts: dict[str, int]
    resolution: int
    window_hours: int
    window_start: datetime
    window_end: datetime
    generated_at: datetime
    model_version: str
    config_hash: str
    privacy: dict
    limitations: list[str]


class RiskInfrastructureSummaryResponse(BaseModel):
    total_cells: int
    exposed_cells: int
    cells_with_authoritative_dataset: int
    by_asset_type: dict[str, int]
    top_assets: list[dict]
    dataset: RiskDatasetResponse
    limitations: list[str]


class RiskBBoxRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_latitude: float | None = Field(default=None, ge=-90, le=90)
    min_longitude: float | None = Field(default=None, ge=-180, le=180)
    max_latitude: float | None = Field(default=None, ge=-90, le=90)
    max_longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def _complete_bbox(self) -> "RiskBBoxRequest":
        values = (
            self.min_latitude,
            self.min_longitude,
            self.max_latitude,
            self.max_longitude,
        )
        if any(value is None for value in values) and not all(
            value is None for value in values
        ):
            raise ValueError("all four bbox coordinates must be supplied together")
        if all(value is not None for value in values):
            assert self.min_latitude is not None
            assert self.min_longitude is not None
            assert self.max_latitude is not None
            assert self.max_longitude is not None
            if self.min_latitude >= self.max_latitude:
                raise ValueError("min_latitude must be less than max_latitude")
            if self.min_longitude >= self.max_longitude:
                raise ValueError("min_longitude must be less than max_longitude")
        return self


class RiskRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resolution: int | None = Field(default=None, ge=5, le=12)
    window_hours: int | None = Field(default=None, ge=1, le=8760)
    bbox: RiskBBoxRequest | None = None
    limit: int = Field(default=500, ge=1, le=2000)


class RiskRunListItem(BaseModel):
    run_id: uuid.UUID
    generated_at: datetime
    resolution: int
    window_hours: int
    cell_count: int
    incident_count: int
    model_version: str
    config_hash: str


class RiskRunListResponse(BaseModel):
    items: list[RiskRunListItem]


class RiskRunResponse(BaseModel):
    run_id: uuid.UUID
    generated_at: datetime
    resolution: int
    window_hours: int
    cell_count: int
    incident_count: int
    model_version: str
    config_hash: str
    summary: RiskSummaryResponse
