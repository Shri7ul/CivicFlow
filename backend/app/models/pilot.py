"""Phase 10 controlled-pilot, review, traceability and readiness models.

These tables extend the existing risk and validation workspaces. No table can
activate a model, dispatch a unit, reserve a resource, or mutate an incident.
Review and transition rows are append-only evidence, not editable state.
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
    jsonb_column_type,
)
from app.models.enums import (
    CorrelationDecision,
    InfrastructureValidationStatus,
    PilotMode,
    PilotReviewerRole,
    PilotStatus,
    PilotTransitionAction,
    ReadinessStatus,
    RiskReviewStatus,
)
from app.models.types import enum_column


class Pilot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A bounded, human-approved evaluation plan. Never an operational order."""

    __tablename__ = "pilots"
    __table_args__ = (
        UniqueConstraint("pilot_key", name="uq_pilots_key"),
        CheckConstraint(
"start_date <= end_date", name="ck_pilots_date_order"
        ),
        CheckConstraint(
"status IN ('DRAFT','PENDING_APPROVAL','APPROVED','ACTIVE','PAUSED','COMPLETED','REJECTED','TERMINATED','ARCHIVED')",
            name="ck_pilots_status",
        ),
        Index("ix_pilots_status_created", "status", "created_at"),
        Index("ix_pilots_owner", "owner_id"),
    )

    pilot_key: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[PilotStatus] = mapped_column(
        enum_column(PilotStatus, "pilot_status"),
        nullable=False,
        server_default=PilotStatus.DRAFT.value,
    )
    mode: Mapped[PilotMode] = mapped_column(
        enum_column(PilotMode, "pilot_mode"),
        nullable=False,
        server_default=PilotMode.SIMULATION.value,
    )
    region: Mapped[str] = mapped_column(String(240), nullable=False)
    geographic_context_key: Mapped[str] = mapped_column(
        String(32), nullable=False, default="UNKNOWN", server_default="UNKNOWN", index=True
    )
    bbox: Mapped[list] = mapped_column(
        jsonb_column_type(), nullable=False, default=list, server_default=text("'[]'")
    )
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    eligible_categories: Mapped[list] = mapped_column(
        jsonb_column_type(), nullable=False, default=list, server_default=text("'[]'")
    )
    evaluation_protocol: Mapped[str] = mapped_column(Text, nullable=False)
    operational_restrictions: Mapped[list] = mapped_column(
        jsonb_column_type(), nullable=False, default=list, server_default=text("'[]'")
    )
    data_sources: Mapped[list] = mapped_column(
        jsonb_column_type(), nullable=False, default=list, server_default=text("'[]'")
    )
    evaluation_criteria: Mapped[list] = mapped_column(
        jsonb_column_type(), nullable=False, default=list, server_default=text("'[]'")
    )
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    activated_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    paused_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    paused_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    pause_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    terminated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    terminated_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    termination_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    activation_readiness: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict, server_default=text("'{}'")
    )


class PilotReviewer(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "pilot_reviewers"
    __table_args__ = (
        UniqueConstraint("pilot_id", "profile_id", name="uq_pilot_reviewers_pair"),
        Index("ix_pilot_reviewers_profile", "profile_id"),
    )

    pilot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("pilots.id", ondelete="CASCADE"),
        nullable=False,
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[PilotReviewerRole] = mapped_column(
        enum_column(PilotReviewerRole, "pilot_reviewer_role"),
        nullable=False,
        server_default=PilotReviewerRole.REVIEWER.value,
    )
    added_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class PilotTransition(UUIDPrimaryKeyMixin, Base):
    """Append-only lifecycle event; database trigger blocks update/delete."""

    __tablename__ = "pilot_transitions"
    __table_args__ = (
        Index("ix_pilot_transitions_pilot_created", "pilot_id", "created_at"),
        Index("ix_pilot_transitions_actor", "actor_id"),
    )

    pilot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("pilots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    from_status: Mapped[PilotStatus | None] = mapped_column(
        enum_column(PilotStatus, "pilot_transition_from"), nullable=True
    )
    to_status: Mapped[PilotStatus] = mapped_column(
        enum_column(PilotStatus, "pilot_transition_to"), nullable=False
    )
    action: Mapped[PilotTransitionAction] = mapped_column(
        enum_column(PilotTransitionAction, "pilot_transition_action"),
        nullable=False,
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


class RiskReviewCase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Human review of one persisted risk cell; never edits risk evidence."""

    __tablename__ = "risk_review_cases"
    __table_args__ = (
        UniqueConstraint("run_id", "cell_id", name="uq_risk_review_cases_run_cell"),
        Index("ix_risk_review_cases_status_updated", "status", "updated_at"),
        Index("ix_risk_review_cases_pilot", "pilot_id"),
        Index("ix_risk_review_cases_run", "run_id"),
        Index("ix_risk_review_cases_assigned", "assigned_reviewer_id"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("risk_model_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    cell_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("risk_cell_snapshots.id", ondelete="CASCADE"),
        nullable=False,
    )
    pilot_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("pilots.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[RiskReviewStatus] = mapped_column(
        enum_column(RiskReviewStatus, "risk_review_status"),
        nullable=False,
        server_default=RiskReviewStatus.UNREVIEWED.value,
    )
    assigned_reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_decision_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class RiskReviewEvent(UUIDPrimaryKeyMixin, Base):
    """Append-only reviewer decision. Original risk rows are never rewritten."""

    __tablename__ = "risk_review_events"
    __table_args__ = (
        Index("ix_risk_review_events_case_created", "case_id", "created_at"),
        Index("ix_risk_review_events_actor", "actor_id"),
    )

    case_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("risk_review_cases.id", ondelete="RESTRICT"),
        nullable=False,
    )
    from_status: Mapped[RiskReviewStatus | None] = mapped_column(
        enum_column(RiskReviewStatus, "risk_review_from"), nullable=True
    )
    to_status: Mapped[RiskReviewStatus] = mapped_column(
        enum_column(RiskReviewStatus, "risk_review_to"), nullable=False
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class CorrelationCandidate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A generated incident pair awaiting independent human labels."""

    __tablename__ = "correlation_candidates"
    __table_args__ = (
        UniqueConstraint("candidate_key", name="uq_correlation_candidates_key"),
        UniqueConstraint(
            "source_incident_id",
            "target_incident_id",
            "method_version",
            name="uq_correlation_candidates_pair_method",
        ),
        CheckConstraint(
            "source_incident_id <> target_incident_id",
            name="ck_correlation_candidates_distinct",
        ),
        CheckConstraint(
            "similarity_score >= 0 AND similarity_score <= 1",
            name="ck_correlation_candidates_score",
        ),
        CheckConstraint(
            "reference_universe_size IS NULL OR reference_universe_size >= 0",
            name="ck_correlation_candidates_reference_size",
        ),
        Index("ix_correlation_candidates_universe", "universe_key", "created_at"),
        Index("ix_correlation_candidates_method", "method", "method_version"),
    )

    candidate_key: Mapped[str] = mapped_column(String(80), nullable=False)
    source_incident_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_incident_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
    )
    similarity_score: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    method: Mapped[str] = mapped_column(String(80), nullable=False)
    method_version: Mapped[str] = mapped_column(String(40), nullable=False)
    universe_key: Mapped[str] = mapped_column(String(80), nullable=False)
    universe_reference_complete: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    reference_universe_size: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    reference_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Explicit provenance, not inferred from the incident rows. Nullable for
    # pre-0019 rows where provenance was not recorded; new API rows require it.
    synthetic_fixture: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )


class CorrelationReview(UUIDPrimaryKeyMixin, Base):
    """One immutable reviewer label per candidate and reviewer."""

    __tablename__ = "correlation_reviews"
    __table_args__ = (
        UniqueConstraint(
            "candidate_id", "reviewer_id", name="uq_correlation_reviews_candidate_reviewer"
        ),
        Index("ix_correlation_reviews_candidate", "candidate_id", "created_at"),
        Index("ix_correlation_reviews_reviewer", "reviewer_id"),
    )

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("correlation_candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewer_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    decision: Mapped[CorrelationDecision] = mapped_column(
        enum_column(CorrelationDecision, "correlation_decision"), nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class InfrastructureSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Registry entry only: no asset row is created or implied."""

    __tablename__ = "infrastructure_sources"
    __table_args__ = (
        UniqueConstraint("source_key", name="uq_infrastructure_sources_key"),
        CheckConstraint(
            "length(snapshot_sha256) = 64 OR snapshot_sha256 IS NULL",
            name="ck_infrastructure_sources_sha256",
        ),
        Index("ix_infrastructure_sources_status", "validation_status"),
        Index("ix_infrastructure_sources_category", "category"),
    )

    source_key: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(60), nullable=False)
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    provider: Mapped[str] = mapped_column(String(200), nullable=False)
    license_note: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    dataset_version: Mapped[str] = mapped_column(String(120), nullable=False)
    geographic_coverage: Mapped[str] = mapped_column(String(300), nullable=False)
    crs: Mapped[str] = mapped_column(String(120), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(80), nullable=False)
    validation_status: Mapped[InfrastructureValidationStatus] = mapped_column(
        enum_column(InfrastructureValidationStatus, "infrastructure_validation_status"),
        nullable=False,
        server_default=InfrastructureValidationStatus.PENDING.value,
    )
    snapshot_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    update_frequency: Mapped[str | None] = mapped_column(String(120), nullable=True)
    known_limitations: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict] = mapped_column(
        "metadata",
        jsonb_column_type(),
        nullable=False,
        default=dict,
        server_default=text("'{}'"),
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )


class InfrastructureSourceEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "infrastructure_source_events"
    __table_args__ = (
        Index("ix_infrastructure_source_events_source", "source_id", "created_at"),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("infrastructure_sources.id", ondelete="RESTRICT"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    from_status: Mapped[InfrastructureValidationStatus | None] = mapped_column(
        enum_column(InfrastructureValidationStatus, "infra_event_from"), nullable=True
    )
    to_status: Mapped[InfrastructureValidationStatus] = mapped_column(
        enum_column(InfrastructureValidationStatus, "infra_event_to"), nullable=False
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


class ReadinessEvidence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Manual attestation row for criteria the database cannot derive."""

    __tablename__ = "readiness_evidence"
    __table_args__ = (
        UniqueConstraint("category", "criterion_key", name="uq_readiness_evidence_criterion"),
        Index("ix_readiness_evidence_category", "category"),
        Index("ix_readiness_evidence_status", "status"),
    )

    category: Mapped[str] = mapped_column(String(60), nullable=False)
    criterion_key: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[ReadinessStatus] = mapped_column(
        enum_column(ReadinessStatus, "readiness_evidence_status"), nullable=False
    )
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_refs: Mapped[list] = mapped_column(
        jsonb_column_type(), nullable=False, default=list, server_default=text("'[]'")
    )
    blocking: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    assessed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    assessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class ReadinessEvidenceEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "readiness_evidence_events"
    __table_args__ = (
        Index("ix_readiness_evidence_events_evidence", "evidence_id", "created_at"),
    )

    evidence_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("readiness_evidence.id", ondelete="RESTRICT"),
        nullable=False,
    )
    from_status: Mapped[ReadinessStatus | None] = mapped_column(
        enum_column(ReadinessStatus, "readiness_event_from"), nullable=True
    )
    to_status: Mapped[ReadinessStatus] = mapped_column(
        enum_column(ReadinessStatus, "readiness_event_to"), nullable=False
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