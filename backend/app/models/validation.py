"""Phase 8 empirical validation datasets and immutable experiment records."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    jsonb_column_type,
)
from app.models.enums import (
    ValidationDatasetStatus,
    ValidationEvidenceKind,
    ValidationExperimentType,
    ValidationStatus,
)
from app.models.types import enum_column


class ValidationDataset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A fixed public dataset snapshot linked to provenance-rich ingestion."""

    __tablename__ = "validation_datasets"
    __table_args__ = (
        UniqueConstraint("dataset_key", name="uq_validation_datasets_key"),
        CheckConstraint("record_count >= 0", name="ck_validation_datasets_count"),
        CheckConstraint(
            "period_start IS NULL OR period_end IS NULL OR period_end >= period_start",
            name="ck_validation_datasets_period",
        ),
        Index("ix_validation_datasets_source", "source_id"),
        Index("ix_validation_datasets_status", "status"),
    )

    dataset_key: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    license_note: Mapped[str] = mapped_column(Text, nullable=False)
    region: Mapped[str] = mapped_column(String(200), nullable=False)
    geographic_context_key: Mapped[str] = mapped_column(
        String(32), nullable=False, default="UNKNOWN", server_default="UNKNOWN", index=True
    )
    period_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("data_sources.id", ondelete="RESTRICT"),
        nullable=True,
    )
    ingestion_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ingestion_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    snapshot_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshot_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    record_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    schema_version: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[ValidationDatasetStatus] = mapped_column(
        enum_column(ValidationDatasetStatus, "validation_dataset_status"),
        nullable=False,
        server_default=ValidationDatasetStatus.REGISTERED.value,
    )
    dataset_metadata: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict, server_default=text("'{}'")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )


class ValidationExperiment(UUIDPrimaryKeyMixin, Base):
    """Persisted, non-overwriting result of one bounded validation run."""

    __tablename__ = "validation_experiments"
    __table_args__ = (
        UniqueConstraint("experiment_key", name="uq_validation_experiments_key"),
        CheckConstraint(
            "record_count >= 0", name="ck_validation_experiments_count"
        ),
        Index("ix_validation_experiments_dataset_created", "dataset_id", "created_at"),
        Index("ix_validation_experiments_type_status", "experiment_type", "status"),
        Index("ix_validation_experiments_evidence", "evidence_kind"),
        Index(
            "ix_validation_experiments_protocol",
            "protocol_key",
            "variant_key",
        ),
    )

    experiment_key: Mapped[str] = mapped_column(String(120), nullable=False)
    protocol_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    variant_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    dataset_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("validation_datasets.id", ondelete="SET NULL"),
        nullable=True,
    )
    dataset_version: Mapped[str | None] = mapped_column(String(160), nullable=True)
    dataset_snapshot_sha256: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    experiment_type: Mapped[ValidationExperimentType] = mapped_column(
        enum_column(ValidationExperimentType, "validation_experiment_type"),
        nullable=False,
    )
    evidence_kind: Mapped[ValidationEvidenceKind] = mapped_column(
        enum_column(ValidationEvidenceKind, "validation_evidence_kind"),
        nullable=False,
    )
    status: Mapped[ValidationStatus] = mapped_column(
        enum_column(ValidationStatus, "validation_status"),
        nullable=False,
        server_default=ValidationStatus.RUNNING.value,
    )
    method: Mapped[str] = mapped_column(String(160), nullable=False)
    split_method: Mapped[str | None] = mapped_column(String(160), nullable=True)
    region: Mapped[str | None] = mapped_column(String(200), nullable=True)
    period_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    record_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    model_name: Mapped[str | None] = mapped_column(String(40), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    config_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metrics: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict, server_default=text("'{}'")
    )
    baselines: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict, server_default=text("'{}'")
    )
    findings: Mapped[list] = mapped_column(
        jsonb_column_type(), nullable=False, default=list, server_default=text("'[]'")
    )
    limitations: Mapped[list] = mapped_column(
        jsonb_column_type(), nullable=False, default=list, server_default=text("'[]'")
    )
    reproducibility: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict, server_default=text("'{}'")
    )
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
