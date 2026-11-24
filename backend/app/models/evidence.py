"""Phase 11 evidence snapshots, ground truth and correlation universes.

These tables are additive evidence infrastructure. They do not activate models,
dispatch resources, or mutate original reports. Snapshot bytes are retained so
that hashes and normalized records can be independently recomputed.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
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
    geometry_type,
    jsonb_column_type,
)
from app.models.enums import (
    EvidenceQualityStatus,
    EvidenceSnapshotKind,
    EvidenceSnapshotStatus,
    GroundTruthSourceType,
    GroundTruthStatus,
    ProvenanceKind,
    SnapshotVerificationStatus,
)
from app.models.types import enum_column


class EvidenceSnapshot(UUIDPrimaryKeyMixin, Base):
    """Immutable acquisition result; raw and normalized bytes are preserved."""

    __tablename__ = "evidence_snapshots"
    __table_args__ = (
        UniqueConstraint("snapshot_key", name="uq_evidence_snapshots_key"),
        UniqueConstraint(
            "source_key", "snapshot_sha256", name="uq_evidence_snapshots_source_hash"
        ),
        CheckConstraint(
            "record_count >= 0 AND raw_record_count >= 0 AND duplicate_count >= 0 "
            "AND invalid_count >= 0 AND missing_fields >= 0 AND byte_size >= 0",
            name="ck_evidence_snapshots_counts",
        ),
        CheckConstraint(
            "validation_dataset_id IS NULL OR infrastructure_source_id IS NULL",
            name="ck_evidence_snapshots_single_link",
        ),
        CheckConstraint(
            "status <> 'VALIDATED' OR (snapshot_sha256 IS NOT NULL "
            "AND length(snapshot_sha256) = 64)",
            name="ck_evidence_snapshots_valid_hash",
        ),
        Index("ix_evidence_snapshots_source_retrieved", "source_key", "retrieved_at"),
        Index("ix_evidence_snapshots_kind_status", "kind", "status"),
        Index("ix_evidence_snapshots_current", "source_key", "is_current"),
        Index("ix_evidence_snapshots_dataset", "validation_dataset_id"),
        Index("ix_evidence_snapshots_infra", "infrastructure_source_id"),
    )

    snapshot_key: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[EvidenceSnapshotKind] = mapped_column(
        enum_column(EvidenceSnapshotKind, "evidence_snapshot_kind"), nullable=False
    )
    provenance_kind: Mapped[ProvenanceKind] = mapped_column(
        enum_column(ProvenanceKind, "evidence_snapshot_provenance"),
        nullable=False,
        server_default=ProvenanceKind.OPERATIONAL.value,
    )
    status: Mapped[EvidenceSnapshotStatus] = mapped_column(
        enum_column(EvidenceSnapshotStatus, "evidence_snapshot_status"),
        nullable=False,
        server_default=EvidenceSnapshotStatus.FETCHING.value,
    )
    source_key: Mapped[str] = mapped_column(String(80), nullable=False)
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    provider: Mapped[str] = mapped_column(String(240), nullable=False)
    license_note: Mapped[str] = mapped_column(Text, nullable=False)
    dataset_version: Mapped[str] = mapped_column(String(120), nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    snapshot_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    schema_version: Mapped[str] = mapped_column(String(40), nullable=False)
    schema_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    record_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    raw_record_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    duplicate_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    invalid_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    missing_fields: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    byte_size: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    media_type: Mapped[str] = mapped_column(
        String(80), nullable=False, server_default="application/json"
    )
    crs: Mapped[str | None] = mapped_column(String(40), nullable=True)
    bbox: Mapped[list] = mapped_column(
        jsonb_column_type(), nullable=False, default=list, server_default=text("'[]'")
    )
    data_period_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    data_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    geographic_coverage: Mapped[str | None] = mapped_column(Text, nullable=True)
    geographic_context_key: Mapped[str] = mapped_column(
        String(32), nullable=False, default="UNKNOWN", server_default="UNKNOWN", index=True
    )
    quality_status: Mapped[EvidenceQualityStatus] = mapped_column(
        enum_column(EvidenceQualityStatus, "evidence_quality_status"),
        nullable=False,
        server_default=EvidenceQualityStatus.UNKNOWN.value,
    )
    quality_checks: Mapped[list] = mapped_column(
        jsonb_column_type(), nullable=False, default=list, server_default=text("'[]'")
    )
    lineage: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict, server_default=text("'{}'")
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_status: Mapped[SnapshotVerificationStatus] = mapped_column(
        enum_column(SnapshotVerificationStatus, "snapshot_verification_status"),
        nullable=False,
        server_default=SnapshotVerificationStatus.PENDING.value,
    )
    verification_checks: Mapped[list] = mapped_column(
        jsonb_column_type(), nullable=False, default=list, server_default=text("'[]'")
    )
    verification_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_current: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    supersedes_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("evidence_snapshots.id", ondelete="RESTRICT"),
        nullable=True,
    )
    validation_dataset_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("validation_datasets.id", ondelete="RESTRICT"),
        nullable=True,
    )
    infrastructure_source_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("infrastructure_sources.id", ondelete="RESTRICT"),
        nullable=True,
    )
    raw_content: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    normalized_content: Mapped[bytes | None] = mapped_column(
        LargeBinary, nullable=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class EvidenceSnapshotEvent(UUIDPrimaryKeyMixin, Base):
    """Append-only acquisition/verification audit event."""

    __tablename__ = "evidence_snapshot_events"
    __table_args__ = (
        Index("ix_evidence_snapshot_events_snapshot", "snapshot_id", "created_at"),
    )

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("evidence_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    from_status: Mapped[EvidenceSnapshotStatus | None] = mapped_column(
        enum_column(EvidenceSnapshotStatus, "snapshot_event_from"), nullable=True
    )
    to_status: Mapped[EvidenceSnapshotStatus] = mapped_column(
        enum_column(EvidenceSnapshotStatus, "snapshot_event_to"), nullable=False
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class GroundTruthRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An evidence assertion about a physical incident; never auto-verified."""

    __tablename__ = "ground_truth_records"
    __table_args__ = (
        UniqueConstraint("record_key", name="uq_ground_truth_records_key"),
        UniqueConstraint(
            "source_type", "source_reference", name="uq_ground_truth_source_reference"
        ),
        CheckConstraint(
            "uncertainty IS NULL OR (uncertainty >= 0 AND uncertainty <= 1)",
            name="ck_ground_truth_uncertainty",
        ),
        CheckConstraint(
            "status IN ('UNVERIFIED','IN_REVIEW') OR (verified_by IS NOT NULL "
            "AND verified_at IS NOT NULL AND verification_method IS NOT NULL)",
            name="ck_ground_truth_decision_identity",
        ),
        Index("ix_ground_truth_status_created", "status", "created_at"),
        Index("ix_ground_truth_incident", "incident_id"),
        Index("ix_ground_truth_location_gist", "location", postgresql_using="gist"),
    )

    record_key: Mapped[str] = mapped_column(String(120), nullable=False)
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("incidents.id", ondelete="RESTRICT"),
        nullable=True,
    )
    source_type: Mapped[GroundTruthSourceType] = mapped_column(
        enum_column(GroundTruthSourceType, "ground_truth_source_type"), nullable=False
    )
    provenance_kind: Mapped[ProvenanceKind] = mapped_column(
        enum_column(ProvenanceKind, "ground_truth_provenance"),
        nullable=False,
        server_default=ProvenanceKind.OPERATIONAL.value,
    )
    geographic_context_key: Mapped[str] = mapped_column(
        String(32), nullable=False, default="UNKNOWN", server_default="UNKNOWN", index=True
    )
    source_name: Mapped[str] = mapped_column(String(240), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    incident_type: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    uncertainty: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    location: Mapped[str | None] = mapped_column(
        geometry_type("POINT"), nullable=True
    )
    sensitive: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    status: Mapped[GroundTruthStatus] = mapped_column(
        enum_column(GroundTruthStatus, "ground_truth_status"),
        nullable=False,
        server_default=GroundTruthStatus.UNVERIFIED.value,
    )
    verification_method: Mapped[str | None] = mapped_column(String(120), nullable=True)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    evidence_refs: Mapped[list] = mapped_column(
        jsonb_column_type(), nullable=False, default=list, server_default=text("'[]'")
    )
    verification_evidence_refs: Mapped[list] = mapped_column(
        jsonb_column_type(), nullable=False, default=list, server_default=text("'[]'")
    )
    verification_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )


class GroundTruthEvent(UUIDPrimaryKeyMixin, Base):
    """Append-only verification history with server-derived actor identity."""

    __tablename__ = "ground_truth_events"
    __table_args__ = (
        Index("ix_ground_truth_events_record", "record_id", "created_at"),
    )

    record_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ground_truth_records.id", ondelete="RESTRICT"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    from_status: Mapped[GroundTruthStatus | None] = mapped_column(
        enum_column(GroundTruthStatus, "ground_truth_event_from"), nullable=True
    )
    to_status: Mapped[GroundTruthStatus] = mapped_column(
        enum_column(GroundTruthStatus, "ground_truth_event_to"), nullable=False
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_refs: Mapped[list] = mapped_column(
        jsonb_column_type(), nullable=False, default=list, server_default=text("'[]'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class CorrelationUniverse(UUIDPrimaryKeyMixin, Base):
    """Immutable reference-universe attestation for correlation evaluation."""

    __tablename__ = "correlation_universes"
    __table_args__ = (
        UniqueConstraint("universe_key", name="uq_correlation_universes_key"),
        CheckConstraint(
            "reference_size IS NULL OR reference_size >= 0",
            name="ck_correlation_universes_size",
        ),
        CheckConstraint(
            "reference_complete = false OR (reference_size IS NOT NULL "
            "AND reference_note IS NOT NULL)",
            name="ck_correlation_universes_complete",
        ),
        Index("ix_correlation_universes_provenance", "provenance_kind"),
    )

    universe_key: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    provenance_kind: Mapped[ProvenanceKind] = mapped_column(
        enum_column(ProvenanceKind, "correlation_universe_provenance"), nullable=False
    )
    geographic_context_key: Mapped[str] = mapped_column(
        String(32), nullable=False, default="UNKNOWN", server_default="UNKNOWN", index=True
    )
    reference_complete: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    reference_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reference_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    candidate_method: Mapped[str] = mapped_column(String(80), nullable=False)
    candidate_method_version: Mapped[str] = mapped_column(String(40), nullable=False)
    reference_dataset_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("evidence_snapshots.id", ondelete="RESTRICT"),
        nullable=True,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
