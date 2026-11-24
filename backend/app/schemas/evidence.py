"""Strict Phase 11 request schemas.

Server-owned identity, status and hash fields are deliberately absent. URLs are
not accepted from clients; acquisition uses an allowlisted source key.
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import GroundTruthSourceType, ProvenanceKind


class AcquireRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_key: str = Field(
        min_length=3, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]{2,79}$"
    )


class GroundTruthCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: GroundTruthSourceType
    source_name: str = Field(min_length=2, max_length=240)
    source_reference: str | None = Field(default=None, max_length=500)
    incident_id: uuid.UUID | None = None
    incident_type: str = Field(min_length=2, max_length=80)
    description: str = Field(min_length=10, max_length=4000)
    uncertainty: float | None = Field(default=None, ge=0, le=1)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    sensitive: bool = True
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("evidence_refs")
    @classmethod
    def _refs(cls, value: list[str]) -> list[str]:
        cleaned = []
        for item in value:
            text = item.strip()
            if not text or len(text) > 500:
                raise ValueError("evidence references must be 1..500 characters")
            cleaned.append(text)
        return cleaned

    @model_validator(mode="after")
    def _location_pair(self) -> "GroundTruthCreate":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be supplied together")
        return self


class GroundTruthSubmit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str | None = Field(default=None, max_length=2000)
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)


class GroundTruthReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["VERIFIED", "REJECTED", "INSUFFICIENT_EVIDENCE"]
    verification_method: str = Field(min_length=3, max_length=120)
    note: str = Field(min_length=10, max_length=4000)
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("evidence_refs")
    @classmethod
    def _refs(cls, value: list[str]) -> list[str]:
        cleaned = []
        for item in value:
            text = item.strip()
            if not text or len(text) > 500:
                raise ValueError("evidence references must be 1..500 characters")
            cleaned.append(text)
        return cleaned


class CorrelationUniverseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    universe_key: str = Field(
        min_length=3, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]{2,79}$"
    )
    name: str = Field(min_length=3, max_length=240)
    description: str | None = Field(default=None, max_length=4000)
    version: str = Field(min_length=1, max_length=40)
    provenance_kind: ProvenanceKind
    reference_complete: bool = False
    reference_size: int | None = Field(default=None, ge=0, le=100_000_000)
    reference_note: str | None = Field(default=None, max_length=4000)
    candidate_method: str = Field(min_length=2, max_length=80)
    candidate_method_version: str = Field(min_length=1, max_length=40)
    reference_dataset_snapshot_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _complete_evidence(self) -> "CorrelationUniverseCreate":
        if self.reference_complete and self.reference_size is None:
            raise ValueError("reference_size is required for a complete universe")
        if self.reference_complete and not (
            self.reference_note and self.reference_note.strip()
        ):
            raise ValueError("reference_note is required for a complete universe")
        return self
