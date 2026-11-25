"""Phase 14 controlled-pilot control records.

These tables are preparation and governance controls. They never authorize a
pilot, a model or a real-world civic action by themselves. Every status change
is explicit, server-validated and accompanied by an append-only event row.
No table in this module writes risk scores, dispatches resources, or mutates a
citizen-facing incident.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
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
    point_geography_type,
)
from app.models.enums import (
    AttestationStatus,
    BoundarySourceType,
    DataSourceAuthorization,
    FieldObservationStatus,
    ModelReadinessLevel,
    ObservationCategory,
    PilotBoundaryStatus,
    PilotIncidentSeverity,
    PilotIncidentStatus,
    ProvenanceKind,
)
from app.models.types import enum_column


class PilotBoundary(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Registered, hashed candidate pilot boundary. Approval is never automatic."""

    __tablename__ = "pilot_boundaries"
    __table_args__ = (
        UniqueConstraint("boundary_key", name="uq_pilot_boundaries_key"),
        CheckConstraint(
            "length(integrity_sha256) = 64", name="ck_pilot_boundaries_integrity_sha256"
        ),
        Index("ix_pilot_boundaries_context_status", "geographic_context_key", "status"),
        Index("ix_pilot_boundaries_pilot", "pilot_id"),
    )

    boundary_key: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    pilot_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("pilots.id", ondelete="SET NULL"), nullable=True
    )
    geographic_context_key: Mapped[str] = mapped_column(
        String(32), nullable=False, default="UNKNOWN", server_default="UNKNOWN"
    )
    source_type: Mapped[BoundarySourceType] = mapped_column(
        enum_column(BoundarySourceType, "boundary_source_type"), nullable=False
    )
    source_owner: Mapped[str] = mapped_column(String(240), nullable=False)
    source_name: Mapped[str] = mapped_column(String(240), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    boundary_version: Mapped[str] = mapped_column(String(120), nullable=False)
    crs: Mapped[str] = mapped_column(String(80), nullable=False)
    geometry_geojson: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False
    )
    bbox_geojson: Mapped[list] = mapped_column(jsonb_column_type(), nullable=False)
    coordinate_validation: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict, server_default=text("'{}'")
    )
    geometry_validation: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict, server_default=text("'{}'")
    )
    provenance_note: Mapped[str] = mapped_column(Text, nullable=False)
    license_note: Mapped[str] = mapped_column(Text, nullable=False)
    integrity_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[PilotBoundaryStatus] = mapped_column(
        enum_column(PilotBoundaryStatus, "boundary_status"),
        nullable=False,
        server_default=PilotBoundaryStatus.UNVERIFIED.value,
    )
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )


class PilotBoundaryEvent(UUIDPrimaryKeyMixin, Base):
    """Append-only boundary verification trail."""

    __tablename__ = "pilot_boundary_events"
    __table_args__ = (Index("ix_pilot_boundary_events_boundary", "boundary_id", "created_at"),)

    boundary_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("pilot_boundaries.id", ondelete="RESTRICT"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    from_status: Mapped[PilotBoundaryStatus | None] = mapped_column(
        enum_column(PilotBoundaryStatus, "boundary_event_from"), nullable=True
    )
    to_status: Mapped[PilotBoundaryStatus] = mapped_column(
        enum_column(PilotBoundaryStatus, "boundary_event_to"), nullable=False
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    actor_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class FieldObservation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A human field observation. VERIFIED status is not ground truth by itself."""

    __tablename__ = "field_observations"
    __table_args__ = (
        UniqueConstraint("observation_key", name="uq_field_observations_key"),
        UniqueConstraint(
            "observer_id", "source_reference", name="uq_field_observations_observer_ref"
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_field_observations_confidence",
        ),
        CheckConstraint(
            "latitude IS NULL OR longitude IS NULL OR "
            "(latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)",
            name="ck_field_observations_coordinates",
        ),
        Index("ix_field_observations_context_status", "geographic_context_key", "status"),
        Index("ix_field_observations_pilot", "pilot_id"),
        Index("ix_field_observations_observer", "observer_id"),
        Index("ix_field_observations_reviewer", "reviewer_id"),
    )

    observation_key: Mapped[str] = mapped_column(String(80), nullable=False)
    pilot_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("pilots.id", ondelete="SET NULL"), nullable=True
    )
    geographic_context_key: Mapped[str] = mapped_column(
        String(32), nullable=False, default="UNKNOWN", server_default="UNKNOWN"
    )
    observer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    observer_role_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    location: Mapped[str | None] = mapped_column(point_geography_type(), nullable=True)
    category: Mapped[ObservationCategory] = mapped_column(
        enum_column(ObservationCategory, "observation_category"), nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_refs: Mapped[list] = mapped_column(
        jsonb_column_type(), nullable=False, default=list, server_default=text("'[]'")
    )
    evidence_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provenance_kind: Mapped[ProvenanceKind] = mapped_column(
        enum_column(ProvenanceKind, "observation_provenance"),
        nullable=False,
        server_default=ProvenanceKind.OPERATIONAL.value,
    )
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[FieldObservationStatus] = mapped_column(
        enum_column(FieldObservationStatus, "observation_status"),
        nullable=False,
        server_default=FieldObservationStatus.DRAFT.value,
    )
    revision: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    decision: Mapped[str | None] = mapped_column(String(40), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    revision_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    duplicate_of_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("field_observations.id", ondelete="SET NULL"),
        nullable=True,
    )
    ground_truth_record_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ground_truth_records.id", ondelete="RESTRICT"),
        nullable=True,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )


class FieldObservationEvent(UUIDPrimaryKeyMixin, Base):
    """Append-only revision and review history for a field observation."""

    __tablename__ = "field_observation_events"
    __table_args__ = (
        Index("ix_field_observation_events_observation", "observation_id", "created_at"),
    )

    observation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("field_observations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    from_status: Mapped[FieldObservationStatus | None] = mapped_column(
        enum_column(FieldObservationStatus, "observation_event_from"), nullable=True
    )
    to_status: Mapped[FieldObservationStatus] = mapped_column(
        enum_column(FieldObservationStatus, "observation_event_to"), nullable=False
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    actor_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class PilotDataSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Registered source with explicit access authorization and provenance."""

    __tablename__ = "pilot_data_sources"
    __table_args__ = (
        UniqueConstraint("source_key", name="uq_pilot_data_sources_key"),
        CheckConstraint(
            "raw_sha256 IS NULL OR length(raw_sha256) = 64",
            name="ck_pilot_data_sources_raw_sha",
        ),
        CheckConstraint(
            "normalized_sha256 IS NULL OR length(normalized_sha256) = 64",
            name="ck_pilot_data_sources_normalized_sha",
        ),
        Index(
            "ix_pilot_data_sources_context_status",
            "geographic_context_key",
            "access_authorization",
        ),
    )

    source_key: Mapped[str] = mapped_column(String(80), nullable=False)
    geographic_context_key: Mapped[str] = mapped_column(
        String(32), nullable=False, default="UNKNOWN", server_default="UNKNOWN"
    )
    pilot_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("pilots.id", ondelete="SET NULL"), nullable=True
    )
    source_identity: Mapped[str] = mapped_column(String(240), nullable=False)
    source_owner: Mapped[str] = mapped_column(String(240), nullable=False)
    dataset_name: Mapped[str] = mapped_column(String(240), nullable=False)
    dataset_description: Mapped[str] = mapped_column(Text, nullable=False)
    geographic_scope: Mapped[str] = mapped_column(String(300), nullable=False)
    acquisition_method: Mapped[str] = mapped_column(String(120), nullable=False)
    endpoint: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    access_authorization: Mapped[DataSourceAuthorization] = mapped_column(
        enum_column(DataSourceAuthorization, "data_source_authorization"),
        nullable=False,
        server_default=DataSourceAuthorization.UNAUTHORIZED.value,
    )
    license_note: Mapped[str] = mapped_column(Text, nullable=False)
    license_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    timestamp_note: Mapped[str] = mapped_column(Text, nullable=False)
    update_frequency: Mapped[str | None] = mapped_column(String(120), nullable=True)
    data_quality_note: Mapped[str] = mapped_column(Text, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(120), nullable=False)
    provenance_note: Mapped[str] = mapped_column(Text, nullable=False)
    raw_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    normalized_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    coverage_note: Mapped[str] = mapped_column(Text, nullable=False)
    missing_data_note: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_note: Mapped[str] = mapped_column(Text, nullable=False)
    limitations: Mapped[str] = mapped_column(Text, nullable=False)
    authorized_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    authorized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )


class PilotIncident(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Pilot-scoped operational incident. Never triggers real-world response."""

    __tablename__ = "pilot_incidents"
    __table_args__ = (
        UniqueConstraint("incident_key", name="uq_pilot_incidents_key"),
        Index("ix_pilot_incidents_pilot_status", "pilot_id", "status"),
        Index("ix_pilot_incidents_severity", "severity", "status"),
    )

    incident_key: Mapped[str] = mapped_column(String(80), nullable=False)
    pilot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("pilots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    geographic_context_key: Mapped[str] = mapped_column(
        String(32), nullable=False, default="UNKNOWN", server_default="UNKNOWN"
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[PilotIncidentSeverity] = mapped_column(
        enum_column(PilotIncidentSeverity, "pilot_incident_severity"), nullable=False
    )
    status: Mapped[PilotIncidentStatus] = mapped_column(
        enum_column(PilotIncidentStatus, "pilot_incident_status"),
        nullable=False,
        server_default=PilotIncidentStatus.OPEN.value,
    )
    source: Mapped[str] = mapped_column(String(60), nullable=False)
    related_observation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("field_observations.id", ondelete="SET NULL"),
        nullable=True,
    )
    processing_stopped: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    impact_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    investigating_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    mitigated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )


class PilotIncidentEvent(UUIDPrimaryKeyMixin, Base):
    """Append-only incident trail."""

    __tablename__ = "pilot_incident_events"
    __table_args__ = (Index("ix_pilot_incident_events_incident", "incident_id", "created_at"),)

    incident_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("pilot_incidents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    from_status: Mapped[PilotIncidentStatus | None] = mapped_column(
        enum_column(PilotIncidentStatus, "pilot_incident_event_from"), nullable=True
    )
    to_status: Mapped[PilotIncidentStatus] = mapped_column(
        enum_column(PilotIncidentStatus, "pilot_incident_event_to"), nullable=False
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    actor_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class BaselineComparison(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Documented comparison run. Metrics are null when the label set is invalid."""

    __tablename__ = "baseline_comparisons"
    __table_args__ = (
        UniqueConstraint("comparison_key", name="uq_baseline_comparisons_key"),
        Index("ix_baseline_comparisons_context", "geographic_context_key", "created_at"),
        Index("ix_baseline_comparisons_pilot", "pilot_id"),
    )

    comparison_key: Mapped[str] = mapped_column(String(80), nullable=False)
    pilot_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("pilots.id", ondelete="SET NULL"), nullable=True
    )
    geographic_context_key: Mapped[str] = mapped_column(
        String(32), nullable=False, default="UNKNOWN", server_default="UNKNOWN"
    )
    comparison_type: Mapped[str] = mapped_column(String(80), nullable=False)
    method: Mapped[str] = mapped_column(String(240), nullable=False)
    baseline_name: Mapped[str] = mapped_column(String(240), nullable=False)
    candidate_name: Mapped[str] = mapped_column(String(240), nullable=False)
    label_source: Mapped[str] = mapped_column(Text, nullable=False)
    label_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    baseline_metrics: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict, server_default=text("'{}'")
    )
    candidate_metrics: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict, server_default=text("'{}'")
    )
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    limitations: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )


class PilotShutdown(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Non-destructive shutdown record. Historical rows are never deleted."""

    __tablename__ = "pilot_shutdowns"
    __table_args__ = (
        UniqueConstraint("shutdown_key", name="uq_pilot_shutdowns_key"),
        Index("ix_pilot_shutdowns_pilot", "pilot_id", "created_at"),
    )

    shutdown_key: Mapped[str] = mapped_column(String(80), nullable=False)
    pilot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("pilots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    preserved_counts: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict, server_default=text("'{}'")
    )
    evidence_preserved: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    audit_preserved: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    provenance_preserved: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    decisions_preserved: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    incidents_preserved: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    model_activation_disabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    reauthorization_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    performed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )


class Phase14Attestation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Human/manual prerequisite attestation for the final readiness gate."""

    __tablename__ = "phase14_attestations"
    __table_args__ = (
        UniqueConstraint(
            "category", "criterion_key", name="uq_phase14_attestations_criterion"
        ),
        Index("ix_phase14_attestations_category", "category"),
        Index("ix_phase14_attestations_status", "status"),
    )

    category: Mapped[str] = mapped_column(String(80), nullable=False)
    criterion_key: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[AttestationStatus] = mapped_column(
        enum_column(AttestationStatus, "phase14_attestation_status"), nullable=False
    )
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_refs: Mapped[list] = mapped_column(
        jsonb_column_type(), nullable=False, default=list, server_default=text("'[]'")
    )
    blocking: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    assessed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    assessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class Phase14AttestationEvent(UUIDPrimaryKeyMixin, Base):
    """Append-only attestation change trail."""

    __tablename__ = "phase14_attestation_events"
    __table_args__ = (
        Index("ix_phase14_attestation_events_attestation", "attestation_id", "created_at"),
    )

    attestation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("phase14_attestations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    from_status: Mapped[AttestationStatus | None] = mapped_column(
        enum_column(AttestationStatus, "phase14_attestation_event_from"), nullable=True
    )
    to_status: Mapped[AttestationStatus] = mapped_column(
        enum_column(AttestationStatus, "phase14_attestation_event_to"), nullable=False
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    actor_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


# Explicit classification of the Dhaka model state. This is descriptive only:
# no code path promotes a model based on this value.
DHAKA_MODEL_READINESS_LEVEL = ModelReadinessLevel.RESEARCH_ONLY.value
