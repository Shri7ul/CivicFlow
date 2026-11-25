"""Strict Phase 14 request contracts.

Client-supplied identity, status, context resolution, authorization and hash
computation are deliberately absent. The server derives or enforces each of
them from the authenticated actor and persisted evidence.
"""

from __future__ import annotations

import ipaddress
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import (
    AttestationStatus,
    BoundarySourceType,
    FieldObservationStatus,
    ModelReadinessLevel,
    ObservationCategory,
    PilotIncidentSeverity,
    ProvenanceKind,
)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return value.astimezone(timezone.utc)


def _sha(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().lower()
    if len(cleaned) != 64 or any(char not in "0123456789abcdef" for char in cleaned):
        raise ValueError("hash must be 64 lowercase hex characters")
    return cleaned


def _public_url(value: str | None) -> str | None:
    if value is None:
        return None
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        raise ValueError("endpoint must be an http(s) URL")
    host = parsed.hostname.lower()
    if host in {"localhost", "metadata", "metadata.google.internal"} or host.endswith(".local"):
        raise ValueError("endpoint host is not permitted")
    blocked = False
    try:
        address = ipaddress.ip_address(host)
        blocked = (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
            or address.is_unspecified
        )
    except ValueError:
        # A hostname is acceptable only when it is not a local/metadata name.
        blocked = host in {"localhost", "metadata", "metadata.google.internal"}
    if blocked:
        raise ValueError("endpoint host must be publicly routable")
    return value.strip()


class BoundaryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    boundary_key: str = Field(min_length=3, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]{2,79}$")
    name: str = Field(min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    pilot_id: uuid.UUID | None = None
    geographic_context_key: str = Field(min_length=3, max_length=32)
    source_type: BoundarySourceType
    source_owner: str = Field(min_length=2, max_length=240)
    source_name: str = Field(min_length=2, max_length=240)
    source_url: str | None = Field(default=None, max_length=1000)
    source_date: datetime
    boundary_version: str = Field(min_length=1, max_length=120)
    crs: str = Field(min_length=3, max_length=80)
    geometry_geojson: dict
    bbox_geojson: list[float] = Field(min_length=4, max_length=4)
    provenance_note: str = Field(min_length=20, max_length=8000)
    license_note: str = Field(min_length=5, max_length=4000)

    @field_validator("source_date")
    @classmethod
    def _date(cls, value: datetime) -> datetime:
        return _utc(value)

    @field_validator("source_url")
    @classmethod
    def _url(cls, value: str | None) -> str | None:
        return _public_url(value)

    @field_validator("crs")
    @classmethod
    def _crs(cls, value: str) -> str:
        if value.strip().upper() not in {"EPSG:4326", "CRS84", "WGS84"}:
            raise ValueError("boundary registration requires a WGS84 CRS")
        return value.strip().upper()


class BoundaryTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = Field(pattern=r"^(SUBMIT|VERIFY|APPROVE|REJECT)$")
    note: str | None = Field(default=None, max_length=4000)
    approval_reference: str | None = Field(default=None, max_length=500)
    rejection_reason: str | None = Field(default=None, max_length=4000)


class ObservationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pilot_id: uuid.UUID | None = None
    observed_at: datetime
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    category: ObservationCategory
    description: str = Field(min_length=10, max_length=4000)
    source_reference: str | None = Field(default=None, max_length=500)
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)
    evidence_sha256: str | None = Field(default=None, max_length=64)
    confidence: float | None = Field(default=None, ge=0, le=1)

    @field_validator("observed_at")
    @classmethod
    def _observed(cls, value: datetime) -> datetime:
        return _utc(value)

    @field_validator("evidence_sha256")
    @classmethod
    def _hash(cls, value: str | None) -> str | None:
        return _sha(value)

    @field_validator("evidence_refs")
    @classmethod
    def _refs(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item and item.strip()]
        if any(len(item) > 500 for item in cleaned):
            raise ValueError("evidence references must be at most 500 characters")
        return cleaned


class ObservationSubmit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str | None = Field(default=None, max_length=2000)


class ObservationReviewerAssign(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reviewer_id: uuid.UUID


class ObservationReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str = Field(pattern=r"^(VERIFIED|REJECTED|REQUIRES_REVISION)$")
    note: str | None = Field(default=None, max_length=4000)
    rejection_reason: str | None = Field(default=None, max_length=4000)
    revision_notes: str | None = Field(default=None, max_length=4000)


class ObservationDuplicate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    duplicate_of_id: uuid.UUID


class DataSourceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_key: str = Field(min_length=3, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]{2,79}$")
    geographic_context_key: str = Field(min_length=3, max_length=32)
    pilot_id: uuid.UUID | None = None
    source_identity: str = Field(min_length=2, max_length=240)
    source_owner: str = Field(min_length=2, max_length=240)
    dataset_name: str = Field(min_length=2, max_length=240)
    dataset_description: str = Field(min_length=10, max_length=4000)
    geographic_scope: str = Field(min_length=2, max_length=300)
    acquisition_method: str = Field(min_length=2, max_length=120)
    endpoint: str | None = Field(default=None, max_length=1000)
    classification: str = Field(pattern=r"^(UNAUTHORIZED|RESEARCH_ONLY)$")
    license_note: str = Field(min_length=5, max_length=4000)
    license_ref: str | None = Field(default=None, max_length=500)
    timestamp_note: str = Field(min_length=5, max_length=2000)
    update_frequency: str | None = Field(default=None, max_length=120)
    data_quality_note: str = Field(min_length=10, max_length=4000)
    schema_version: str = Field(min_length=1, max_length=120)
    provenance_note: str = Field(min_length=10, max_length=4000)
    raw_sha256: str | None = Field(default=None, max_length=64)
    normalized_sha256: str | None = Field(default=None, max_length=64)
    coverage_note: str = Field(min_length=5, max_length=4000)
    missing_data_note: str = Field(min_length=5, max_length=4000)
    confidence_note: str = Field(min_length=5, max_length=4000)
    limitations: str = Field(min_length=10, max_length=4000)
    provenance_kind: ProvenanceKind = ProvenanceKind.OPERATIONAL

    @field_validator("endpoint")
    @classmethod
    def _endpoint(cls, value: str | None) -> str | None:
        return _public_url(value)

    @field_validator("raw_sha256", "normalized_sha256")
    @classmethod
    def _hashes(cls, value: str | None) -> str | None:
        return _sha(value)


class DataSourceAuthorize(BaseModel):
    model_config = ConfigDict(extra="forbid")

    license_ref: str = Field(min_length=3, max_length=500)
    authorization_reference: str = Field(min_length=10, max_length=500)


class DataSourceRevoke(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=10, max_length=4000)


class PilotIncidentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pilot_id: uuid.UUID
    title: str = Field(min_length=3, max_length=240)
    description: str = Field(min_length=10, max_length=4000)
    severity: PilotIncidentSeverity
    source: str = Field(min_length=3, max_length=60)
    related_observation_id: uuid.UUID | None = None
    opened_at: datetime | None = None
    bbox: list[float] | None = Field(default=None, min_length=4, max_length=4)

    @field_validator("opened_at")
    @classmethod
    def _opened(cls, value: datetime | None) -> datetime | None:
        return _utc(value) if value else None


class PilotIncidentTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(pattern=r"^(INVESTIGATING|MITIGATED|RESOLVED|CLOSED)$")
    note: str = Field(min_length=10, max_length=4000)


class PilotIncidentResume(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str = Field(min_length=10, max_length=4000)


class BaselineCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    comparison_key: str = Field(min_length=3, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]{2,79}$")
    pilot_id: uuid.UUID | None = None
    geographic_context_key: str = Field(min_length=3, max_length=32)
    comparison_type: str = Field(min_length=3, max_length=80)
    method: str = Field(min_length=10, max_length=2000)
    baseline_name: str = Field(min_length=2, max_length=240)
    candidate_name: str = Field(min_length=2, max_length=240)
    label_source: str = Field(min_length=10, max_length=4000)
    label_count: int = Field(ge=0, le=10_000_000)
    sample_count: int = Field(ge=0, le=10_000_000)
    baseline_metrics: dict = Field(default_factory=dict)
    candidate_metrics: dict = Field(default_factory=dict)
    notes: str = Field(min_length=10, max_length=4000)
    limitations: str = Field(min_length=10, max_length=4000)


class AttestationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str = Field(min_length=3, max_length=80)
    criterion_key: str = Field(min_length=3, max_length=120, pattern=r"^[a-z0-9][a-z0-9_.-]{2,119}$")
    status: AttestationStatus
    evidence: str = Field(min_length=20, max_length=8000)
    evidence_refs: list[str] = Field(min_length=1, max_length=20)
    blocking: bool = True

    @field_validator("evidence_refs")
    @classmethod
    def _refs(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item and item.strip()]
        if not cleaned:
            raise ValueError("at least one evidence reference is required")
        return cleaned


class ShutdownRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=10, max_length=4000)


class ModelStatusRequest(BaseModel):
    """Descriptive classification request; it never promotes a model."""

    model_config = ConfigDict(extra="forbid")

    geographic_context_key: str = Field(min_length=3, max_length=32)
    level: ModelReadinessLevel
    rationale: str = Field(min_length=10, max_length=2000)
