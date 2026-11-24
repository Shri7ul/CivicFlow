"""Phase 8 validation API contracts."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DatasetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_key: str = Field(min_length=3, max_length=120)
    name: str = Field(min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=4000)
    source_url: str = Field(min_length=1, max_length=1000)
    license_note: str = Field(min_length=1, max_length=4000)
    region: str = Field(min_length=1, max_length=200)
    period_start: datetime | None = None
    period_end: datetime | None = None
    source_id: uuid.UUID | None = None
    ingestion_run_id: uuid.UUID | None = None
    snapshot_sha256: str = Field(
        min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )
    snapshot_path: str | None = Field(default=None, max_length=1000)
    record_count: int = Field(ge=0, le=50_000)
    schema_version: str = Field(min_length=1, max_length=40)
    metadata: dict = Field(default_factory=dict)

    @field_validator("source_url")
    @classmethod
    def _validate_source_url(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized.startswith(("https://", "http://")):
            raise ValueError("source_url must be an http(s) URL")
        return value.strip()


class DatasetResponse(BaseModel):
    id: uuid.UUID
    dataset_key: str
    name: str
    description: str | None
    source_url: str
    license_note: str
    region: str
    period_start: datetime | None
    period_end: datetime | None
    source_id: uuid.UUID | None
    ingestion_run_id: uuid.UUID | None
    snapshot_sha256: str
    snapshot_path: str | None
    record_count: int
    schema_version: str
    status: str
    metadata: dict
    created_at: datetime


class ExperimentSummary(BaseModel):
    id: uuid.UUID
    experiment_key: str
    protocol_key: str | None
    variant_key: str | None
    name: str
    experiment_type: str
    evidence_kind: str
    status: str
    dataset_id: uuid.UUID | None
    method: str
    split_method: str | None
    record_count: int
    model_name: str | None
    model_version: str | None
    config_hash: str | None
    findings: list
    limitations: list
    started_at: datetime
    completed_at: datetime | None


class ExperimentDetail(ExperimentSummary):
    dataset_version: str | None
    dataset_snapshot_sha256: str | None
    region: str | None
    period_start: datetime | None
    period_end: datetime | None
    metrics: dict
    baselines: dict
    reproducibility: dict
    error_summary: str | None


class ValidationOverview(BaseModel):
    datasets: list[DatasetResponse]
    experiments: list[ExperimentSummary]
    evidence_kinds: list[str]
    limitations: list[str]
