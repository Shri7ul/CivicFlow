"""Schemas for explainable Phase 4 incident intelligence."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import (
    IncidentCategory,
    IncidentSeverity,
    IncidentStatus,
    RelationshipStatus,
    RelationshipType,
)


class IncidentSummary(BaseModel):
    id: uuid.UUID
    title: str
    category: IncidentCategory
    severity: IncidentSeverity
    status: IncidentStatus


class IntelligenceSignal(BaseModel):
    key: str
    label: str
    value: float | str | bool | None
    weight: float
    contribution: float
    explanation: str


class IncidentCandidate(BaseModel):
    incident: IncidentSummary
    distance_m: float
    time_delta_seconds: int
    text_similarity: float
    confidence: float
    reasons: list[str] = Field(default_factory=list)
    signals: list[IntelligenceSignal] = Field(default_factory=list)


class RelationshipResponse(BaseModel):
    id: uuid.UUID
    incident_a_id: uuid.UUID
    incident_b_id: uuid.UUID
    other_incident: IncidentSummary
    relationship_type: RelationshipType
    status: RelationshipStatus
    confidence: float
    signals: dict = Field(default_factory=dict)
    note: str | None
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RelationshipReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    other_incident_id: uuid.UUID
    relationship_type: RelationshipType = RelationshipType.RELATED
    status: RelationshipStatus
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    signals: dict = Field(default_factory=dict)
    note: str | None = Field(default=None, max_length=500)

    @field_validator("note")
    @classmethod
    def _clean_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class AssetRef(BaseModel):
    id: uuid.UUID
    name: str
    asset_type: str
    criticality_score: float


class InfrastructureContext(BaseModel):
    asset: AssetRef
    distance_m: float
    relationship: str
    dependency_count: int


class ImpactPath(BaseModel):
    root_asset: AssetRef
    affected_asset: AssetRef
    path: list[AssetRef] = Field(default_factory=list)
    depth: int
    impact_type: str
    confidence: float
    rationale: str


class IncidentIntelligenceResponse(BaseModel):
    incident_id: uuid.UUID
    generated_at: datetime
    duplicate_candidates: list[IncidentCandidate] = Field(default_factory=list)
    related_candidates: list[IncidentCandidate] = Field(default_factory=list)
    confirmed_relationships: list[RelationshipResponse] = Field(
        default_factory=list
    )
    infrastructure: list[InfrastructureContext] = Field(default_factory=list)
    potential_impacts: list[ImpactPath] = Field(default_factory=list)
    thresholds: dict[str, float | int] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)


class InfrastructureAssetResponse(BaseModel):
    id: uuid.UUID
    name: str
    asset_type: str
    location_wkt: str
    description: str | None
    criticality_score: float
    is_active: bool
    metadata: dict = Field(default_factory=dict)
