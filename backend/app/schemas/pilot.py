"""Phase 10 pilot, review, correlation, registry and readiness contracts."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import (
    CorrelationDecision,
    InfrastructureValidationStatus,
    PilotMode,
    PilotReviewerRole,
    PilotTransitionAction,
    ReadinessStatus,
    RiskReviewStatus,
)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return value.astimezone(timezone.utc)


def _clean_list(values: list[str], *, label: str) -> list[str]:
    cleaned = [value.strip() for value in values if value and value.strip()]
    if not cleaned:
        raise ValueError(f"{label} must contain at least one non-empty value")
    if len(cleaned) > 20:
        raise ValueError(f"{label} may contain at most 20 values")
    return cleaned


class PilotCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pilot_key: str = Field(min_length=3, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]{2,79}$")
    name: str = Field(min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    mode: PilotMode = PilotMode.SIMULATION
    region: str = Field(min_length=3, max_length=240)
    bbox: list[float] | None = Field(default=None, min_length=4, max_length=4)
    start_date: datetime
    end_date: datetime
    eligible_categories: list[str] = Field(min_length=1, max_length=20)
    evaluation_protocol: str = Field(min_length=20, max_length=8000)
    operational_restrictions: list[str] = Field(min_length=1, max_length=20)
    data_sources: list[str] = Field(min_length=1, max_length=20)
    evaluation_criteria: list[str] = Field(min_length=1, max_length=20)
    owner_id: uuid.UUID | None = None

    @field_validator("start_date", "end_date")
    @classmethod
    def _timezone(cls, value: datetime) -> datetime:
        return _utc(value)

    @field_validator("eligible_categories")
    @classmethod
    def _categories(cls, value: list[str]) -> list[str]:
        allowed = {
            "ROADS",
            "DRAINAGE",
            "SANITATION",
            "UTILITIES",
            "PUBLIC_SAFETY",
            "HEALTH",
            "PARKS",
            "TRANSPORTATION",
            "OTHER",
        }
        cleaned = _clean_list(value, label="eligible_categories")
        unknown = [item for item in cleaned if item not in allowed]
        if unknown:
            raise ValueError(f"unsupported incident category: {unknown[0]}")
        return cleaned

    @field_validator("operational_restrictions", "data_sources", "evaluation_criteria")
    @classmethod
    def _lists(cls, value: list[str]) -> list[str]:
        return _clean_list(value, label="list")

    @field_validator("bbox")
    @classmethod
    def _bbox(cls, value: list[float] | None) -> list[float] | None:
        if value is None:
            return None
        min_lat, min_lon, max_lat, max_lon = value
        if not (-90 <= min_lat < max_lat <= 90):
            raise ValueError("bbox latitude range is invalid")
        if not (-180 <= min_lon < max_lon <= 180):
            raise ValueError("bbox longitude range is invalid")
        return value

    @model_validator(mode="after")
    def _date_order(self) -> "PilotCreate":
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class PilotTransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: PilotTransitionAction
    note: str | None = Field(default=None, max_length=2000)


class PilotReviewerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: uuid.UUID
    role: PilotReviewerRole = PilotReviewerRole.REVIEWER


class RiskReviewCaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: uuid.UUID
    cell_id: uuid.UUID
    pilot_id: uuid.UUID | None = None
    assigned_reviewer_id: uuid.UUID | None = None


class RiskReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: RiskReviewStatus
    note: str | None = Field(default=None, max_length=4000)
    requested_evidence: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _explanation(self) -> "RiskReviewDecision":
        if self.status in {
            RiskReviewStatus.ACCEPTED,
            RiskReviewStatus.REJECTED,
            RiskReviewStatus.NEEDS_INVESTIGATION,
            RiskReviewStatus.NEEDS_MORE_DATA,
        } and not (self.note and self.note.strip()):
            raise ValueError("a reviewer note is required for this decision")
        if self.status == RiskReviewStatus.NEEDS_MORE_DATA and not (
            self.requested_evidence and self.requested_evidence.strip()
        ):
            raise ValueError("requested_evidence is required for NEEDS_MORE_DATA")
        return self


class CorrelationCandidateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_incident_id: uuid.UUID
    target_incident_id: uuid.UUID
    similarity_score: float = Field(ge=0, le=1)
    method: str = Field(min_length=2, max_length=80)
    method_version: str = Field(min_length=1, max_length=40)
    universe_key: str = Field(min_length=2, max_length=80)
    universe_reference_complete: bool = False
    reference_universe_size: int | None = Field(default=None, ge=0, le=100000)
    reference_note: str | None = Field(default=None, max_length=2000)
    synthetic_fixture: bool
    generated_at: datetime | None = None

    @field_validator("generated_at")
    @classmethod
    def _generated(cls, value: datetime | None) -> datetime | None:
        return _utc(value) if value else None

    @model_validator(mode="after")
    def _pair(self) -> "CorrelationCandidateCreate":
        if self.source_incident_id == self.target_incident_id:
            raise ValueError("a candidate requires two distinct incidents")
        if self.universe_reference_complete and not (
            self.reference_note and self.reference_note.strip()
        ):
            raise ValueError("reference_note is required for a complete reference universe")
        if self.universe_reference_complete and self.reference_universe_size is None:
            raise ValueError("reference_universe_size is required for a complete reference universe")
        return self


class CorrelationReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: CorrelationDecision
    note: str | None = Field(default=None, max_length=2000)
    explanation: str | None = Field(default=None, max_length=4000)


class InfrastructureSourceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_key: str = Field(min_length=3, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]{2,79}$")
    name: str = Field(min_length=3, max_length=200)
    category: str = Field(min_length=2, max_length=60)
    source_url: str = Field(min_length=8, max_length=1000)
    provider: str = Field(min_length=2, max_length=200)
    license_note: str = Field(min_length=5, max_length=2000)
    retrieved_at: datetime
    dataset_version: str = Field(min_length=1, max_length=120)
    geographic_coverage: str = Field(min_length=2, max_length=300)
    crs: str = Field(min_length=2, max_length=120)
    schema_version: str = Field(min_length=1, max_length=80)
    snapshot_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    update_frequency: str | None = Field(default=None, max_length=120)
    known_limitations: str | None = Field(default=None, max_length=4000)
    metadata: dict = Field(default_factory=dict)

    @field_validator("source_url")
    @classmethod
    def _url(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized.startswith(("https://", "http://")):
            raise ValueError("source_url must be an http(s) URL")
        return value.strip()

    @field_validator("retrieved_at")
    @classmethod
    def _retrieved(cls, value: datetime) -> datetime:
        return _utc(value)

    @field_validator("category")
    @classmethod
    def _category(cls, value: str) -> str:
        allowed = {
            "ROADS",
            "BRIDGES",
            "PUBLIC_FACILITIES",
            "WATER",
            "DRAINAGE",
            "EMERGENCY_FACILITIES",
            "TRANSIT",
            "OTHER",
        }
        normalized = value.strip().upper()
        if normalized not in allowed:
            raise ValueError("unsupported infrastructure category")
        return normalized


class InfrastructureValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: InfrastructureValidationStatus
    note: str = Field(min_length=10, max_length=4000)

    @field_validator("status")
    @classmethod
    def _status(cls, value: InfrastructureValidationStatus) -> InfrastructureValidationStatus:
        if value == InfrastructureValidationStatus.PENDING:
            raise ValueError("validation decisions cannot return a source to PENDING")
        return value


MANUAL_READINESS_CATEGORIES = (
    "security",
    "reviewer_training",
    "incident_escalation",
    "deployment_rollback",
)


class ReadinessEvidenceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str
    criterion_key: str = Field(min_length=3, max_length=80, pattern=r"^[a-z0-9][a-z0-9_.-]{2,79}$")
    status: ReadinessStatus
    evidence: str = Field(min_length=20, max_length=8000)
    evidence_refs: list[str] = Field(min_length=1, max_length=10)
    blocking: bool = True
    owner_id: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("category")
    @classmethod
    def _category(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in MANUAL_READINESS_CATEGORIES:
            raise ValueError("this readiness category is derived and cannot be attested manually")
        return normalized

    @field_validator("evidence_refs")
    @classmethod
    def _refs(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item and item.strip()]
        if not cleaned:
            raise ValueError("at least one evidence reference is required")
        return cleaned
