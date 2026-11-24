"""Schemas for Phase 7 governance, ingestion, alerts, and approvals."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import (
    AlertRuleType,
    AlertSeverity,
    AlertStatus,
    DataQualityStatus,
    DecisionReviewStatus,
    EvaluationMethod,
    EvaluationStatus,
    IngestionStatus,
    SourceReliability,
    SourceStatus,
)


class ModelRegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_name: Literal["risk", "decision"]
    version: str = Field(min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("version")
    @classmethod
    def _version_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("version must not be blank")
        return value


class ModelActivateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str | None = Field(default=None, max_length=2000)


class ModelVersionResponse(BaseModel):
    id: uuid.UUID
    model_name: str
    version: str
    config_hash: str
    description: str | None
    is_active: bool
    activated_at: datetime | None
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class EvaluationSampleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    predicted_score: float = Field(ge=0, le=100)
    observed: int = Field(ge=0, le=1)
    cell_id: str | None = Field(default=None, max_length=64)
    observed_at: datetime | None = None


class EvaluationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_version_id: uuid.UUID
    method: EvaluationMethod
    dataset_label: str = Field(min_length=1, max_length=200)
    is_synthetic: bool = False
    threshold: float = Field(default=50, ge=0, le=100)
    include_spatial: bool = False
    time_split: bool = False
    samples: list[EvaluationSampleIn] = Field(min_length=1, max_length=10000)


class EvaluationResponse(BaseModel):
    id: uuid.UUID
    model_version_id: uuid.UUID
    method: EvaluationMethod
    status: EvaluationStatus
    dataset_label: str
    is_synthetic: bool
    ground_truth_available: bool
    split_strategy: str
    sample_count: int
    metrics: dict
    slices: dict
    warnings: list
    created_by: uuid.UUID | None
    created_at: datetime


class SourceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_key: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=64)
    access_method: str = Field(min_length=1, max_length=120)
    license_note: str | None = Field(default=None, max_length=5000)
    reliability: SourceReliability
    status: SourceStatus = SourceStatus.ACTIVE
    adapter: str = Field(default="manual", min_length=1, max_length=120)
    freshness_target_minutes: int = Field(default=1440, ge=1, le=525600)
    retry_limit: int = Field(default=3, ge=0, le=20)
    required_fields: list[str] = Field(default_factory=list, max_length=50)
    metadata: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def _normalise(self) -> "SourceCreate":
        self.source_key = self.source_key.strip().lower()
        self.name = self.name.strip()
        if not self.name or not self.source_key:
            raise ValueError("source_key and name must not be empty")
        return self

    @field_validator("required_fields")
    @classmethod
    def _required_fields(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})


class SourceResponse(BaseModel):
    id: uuid.UUID
    source_key: str
    name: str
    category: str
    access_method: str
    license_note: str | None
    reliability: SourceReliability
    status: SourceStatus
    adapter: str
    freshness_target_minutes: int
    retry_limit: int
    metadata: dict
    created_at: datetime
    updated_at: datetime


class RecordIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    external_id: str = Field(min_length=1, max_length=200)
    payload: dict
    observed_at: datetime | None = None
    provenance: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def _payload_size(self) -> "RecordIn":
        encoded = json.dumps(
            {"payload": self.payload, "provenance": self.provenance},
            default=str,
            separators=(",", ":"),
        )
        if len(encoded.encode("utf-8")) > 32_768:
            raise ValueError("record payload/provenance exceeds the 32 KiB limit")
        return self


class IngestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: str = Field(min_length=1, max_length=120)
    records: list[RecordIn] = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def _batch_size(self) -> "IngestionRequest":
        total = sum(
            len(
                json.dumps(item.payload, default=str, separators=(",", ":")).encode(
                    "utf-8"
                )
            )
            for item in self.records
        )
        if total > 2_000_000:
            raise ValueError("batch payload exceeds the 2 MB limit")
        return self


class IngestionRunResponse(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    idempotency_key: str
    status: IngestionStatus
    started_at: datetime
    completed_at: datetime | None
    records_received: int
    records_valid: int
    records_invalid: int
    records_duplicate: int
    records_upserted: int
    schema_fingerprint: str | None
    error_summary: str | None
    retry_count: int


class QualitySnapshotResponse(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    status: DataQualityStatus
    freshness_minutes: int | None
    records_total: int
    invalid_records: int
    duplicate_records: int
    missing_fields: int
    coverage: dict
    issues: list
    schema_fingerprint: str | None
    recorded_at: datetime


class QualityItemResponse(BaseModel):
    source: SourceResponse
    status: DataQualityStatus
    freshness_minutes: int | None
    issues: list
    snapshot: QualitySnapshotResponse | None


class AlertRuleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=160)
    rule_type: AlertRuleType
    metric: str = Field(min_length=1, max_length=80)
    operator: Literal[">=", ">", "<=", "<", "=="] = ">="
    threshold_value: float | None = Field(default=None, ge=0)
    severity: AlertSeverity
    scope: dict = Field(default_factory=dict)
    cooldown_minutes: int = Field(default=60, ge=0, le=10080)
    dedupe_window_minutes: int = Field(default=1440, ge=0, le=10080)
    is_enabled: bool = True
    in_app_enabled: bool = True

    @model_validator(mode="after")
    def _threshold(self) -> "AlertRuleCreate":
        if self.rule_type == AlertRuleType.RISK_THRESHOLD and self.threshold_value is None:
            raise ValueError("threshold_value is required for a risk threshold rule")
        return self


class AlertRuleResponse(BaseModel):
    id: uuid.UUID
    name: str
    rule_type: AlertRuleType
    metric: str
    operator: str
    threshold_value: float | None
    severity: AlertSeverity
    scope: dict
    cooldown_minutes: int
    dedupe_window_minutes: int
    is_enabled: bool
    in_app_enabled: bool
    created_at: datetime
    updated_at: datetime


class AlertResponse(BaseModel):
    id: uuid.UUID
    rule_id: uuid.UUID | None
    severity: AlertSeverity
    status: AlertStatus
    title: str
    message: str
    dedupe_key: str
    context: dict
    triggered_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None


class NotificationResponse(BaseModel):
    id: uuid.UUID
    alert_id: uuid.UUID
    channel: str
    delivery_status: str
    dedupe_key: str
    created_at: datetime
    delivered_at: datetime | None
    read_at: datetime | None


class PreferenceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    in_app_enabled: bool | None = None
    minimum_severity: AlertSeverity | None = None


class ReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    simulation_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    comment: str | None = Field(default=None, max_length=5000)


class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: DecisionReviewStatus
    comment: str | None = Field(default=None, max_length=5000)


class ReviewResponse(BaseModel):
    id: uuid.UUID
    scenario_id: uuid.UUID
    simulation_id: uuid.UUID | None
    title: str
    status: DecisionReviewStatus
    submitted_by: uuid.UUID | None
    submitted_by_name: str | None
    reviewed_by: uuid.UUID | None
    reviewed_by_name: str | None
    submitted_at: datetime | None
    reviewed_at: datetime | None
    decision_note: str | None
    created_at: datetime
    updated_at: datetime
    execution_authorized: bool
    dispatch_performed: bool
    reservations_created: bool
