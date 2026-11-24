"""Phase 7 governance, ingestion, evaluation, alerting, and approval models.

All operational tables are staff-only. Approval is a planning governance action:
it never dispatches units, reserves resources, or mutates an incident.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    jsonb_column_type,
)
from app.models.enums import (
    AlertRuleType,
    AlertSeverity,
    AlertStatus,
    DataQualityStatus,
    DecisionReviewStatus,
    EvaluationMethod,
    EvaluationStatus,
    IngestionStatus,
    ModelLifecycleAction,
    NotificationChannel,
    NotificationDeliveryStatus,
    SourceReliability,
    SourceStatus,
)
from app.models.types import enum_column


class ModelVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Registered, reproducible model configuration."""

    __tablename__ = "model_versions"
    __table_args__ = (
        UniqueConstraint("model_name", "version", name="uq_model_versions_name_version"),
        CheckConstraint(
            "model_name IN ('risk', 'decision')",
            name="ck_model_versions_model_name",
        ),
        CheckConstraint("config_hash <> ''", name="ck_model_versions_hash_not_blank"),
        Index("ix_model_versions_name_active", "model_name", "is_active"),
        Index(
            "uq_model_versions_one_active",
            "model_name",
            unique=True,
            postgresql_where=text("is_active"),
            sqlite_where=text("is_active"),
        ),
        Index("ix_model_versions_created_at", "created_at"),
    )

    model_name: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    config: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict, server_default=text("'{}'")
    )
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )

    events: Mapped[list["ModelVersionEvent"]] = relationship(
        back_populates="model_version",
        foreign_keys="ModelVersionEvent.model_version_id",
        cascade="all, delete-orphan",
    )
    evaluations: Mapped[list["ModelEvaluation"]] = relationship(
        back_populates="model_version", cascade="all, delete-orphan"
    )


class ModelVersionEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "model_version_events"
    __table_args__ = (
        Index("ix_model_version_events_version", "model_version_id", "created_at"),
        Index("ix_model_version_events_actor", "actor_id"),
    )

    model_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("model_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    previous_model_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("model_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[ModelLifecycleAction] = mapped_column(
        enum_column(ModelLifecycleAction, "model_lifecycle_action"), nullable=False
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    model_version: Mapped["ModelVersion"] = relationship(
        back_populates="events", foreign_keys=[model_version_id]
    )


class ModelEvaluation(UUIDPrimaryKeyMixin, Base):
    """Persisted evaluation record. Synthetic fixtures are never production evidence."""

    __tablename__ = "model_evaluations"
    __table_args__ = (
        CheckConstraint("sample_count >= 0", name="ck_model_evaluations_sample_count"),
        Index("ix_model_evaluations_version", "model_version_id", "created_at"),
        Index("ix_model_evaluations_status", "status"),
        Index("ix_model_evaluations_created_by", "created_by"),
    )

    model_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("model_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    method: Mapped[EvaluationMethod] = mapped_column(
        enum_column(EvaluationMethod, "evaluation_method"), nullable=False
    )
    status: Mapped[EvaluationStatus] = mapped_column(
        enum_column(EvaluationStatus, "evaluation_status"), nullable=False
    )
    dataset_label: Mapped[str] = mapped_column(String(200), nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    ground_truth_available: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    split_strategy: Mapped[str] = mapped_column(String(32), nullable=False)
    sample_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    metrics: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict, server_default=text("'{}'")
    )
    slices: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict, server_default=text("'{}'")
    )
    config: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict, server_default=text("'{}'")
    )
    warnings: Mapped[list] = mapped_column(
        jsonb_column_type(), nullable=False, default=list, server_default=text("'[]'")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    model_version: Mapped["ModelVersion"] = relationship(back_populates="evaluations")


class DataSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Registered ingestion source. No source is seeded as authoritative."""

    __tablename__ = "data_sources"
    __table_args__ = (
        UniqueConstraint("source_key", name="uq_data_sources_source_key"),
        CheckConstraint(
            "freshness_target_minutes >= 1",
            name="ck_data_sources_freshness_target_positive",
        ),
        CheckConstraint(
            "retry_limit >= 0 AND retry_limit <= 20",
            name="ck_data_sources_retry_limit",
        ),
        Index("ix_data_sources_status", "status"),
        Index("ix_data_sources_reliability", "reliability"),
    )

    source_key: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    access_method: Mapped[str] = mapped_column(String(120), nullable=False)
    license_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reliability: Mapped[SourceReliability] = mapped_column(
        enum_column(SourceReliability, "source_reliability"), nullable=False
    )
    status: Mapped[SourceStatus] = mapped_column(
        enum_column(SourceStatus, "source_status"),
        nullable=False,
        server_default=SourceStatus.ACTIVE.value,
    )
    adapter: Mapped[str] = mapped_column(String(120), nullable=False)
    freshness_target_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1440")
    )
    retry_limit: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("3")
    )
    metadata_json: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict, server_default=text("'{}'")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )


class IngestionRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ingestion_runs"
    __table_args__ = (
        UniqueConstraint(
            "source_id", "idempotency_key", name="uq_ingestion_runs_source_idempotency"
        ),
        CheckConstraint(
            "records_received >= 0 AND records_valid >= 0 AND records_invalid >= 0 "
            "AND records_duplicate >= 0 AND records_upserted >= 0",
            name="ck_ingestion_runs_counts_nonnegative",
        ),
        Index("ix_ingestion_runs_source_started", "source_id", "started_at"),
        Index("ix_ingestion_runs_status", "status"),
        Index("ix_ingestion_runs_started_at", "started_at"),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("data_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[IngestionStatus] = mapped_column(
        enum_column(IngestionStatus, "ingestion_status"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    records_received: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    records_valid: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    records_invalid: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    records_duplicate: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    records_upserted: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    schema_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provenance: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict, server_default=text("'{}'")
    )
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )


class IngestedRecord(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ingested_records"
    __table_args__ = (
        UniqueConstraint(
            "source_id", "external_id", name="uq_ingested_records_source_external"
        ),
        Index("ix_ingested_records_source_seen", "source_id", "last_seen_at"),
        Index("ix_ingested_records_payload_hash", "payload_hash"),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("data_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict, server_default=text("'{}'")
    )
    observed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    provenance: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict, server_default=text("'{}'")
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class DataQualitySnapshot(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "data_quality_snapshots"
    __table_args__ = (
        CheckConstraint(
            "freshness_minutes IS NULL OR freshness_minutes >= 0",
            name="ck_data_quality_snapshots_freshness",
        ),
        CheckConstraint(
            "invalid_records >= 0 AND duplicate_records >= 0 AND missing_fields >= 0",
            name="ck_data_quality_snapshots_counts",
        ),
        Index("ix_data_quality_snapshots_source_recorded", "source_id", "recorded_at"),
        Index("ix_data_quality_snapshots_status", "status"),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("data_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[DataQualityStatus] = mapped_column(
        enum_column(DataQualityStatus, "data_quality_status"), nullable=False
    )
    freshness_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    records_total: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    invalid_records: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    duplicate_records: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    missing_fields: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    coverage: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict, server_default=text("'{}'")
    )
    issues: Mapped[list] = mapped_column(
        jsonb_column_type(), nullable=False, default=list, server_default=text("'[]'")
    )
    schema_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class AlertRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "alert_rules"
    __table_args__ = (
        CheckConstraint(
            "cooldown_minutes >= 0 AND cooldown_minutes <= 10080",
            name="ck_alert_rules_cooldown",
        ),
        CheckConstraint(
            "dedupe_window_minutes >= 0 AND dedupe_window_minutes <= 10080",
            name="ck_alert_rules_dedupe_window",
        ),
        CheckConstraint(
            "threshold_value IS NULL OR threshold_value >= 0",
            name="ck_alert_rules_threshold_nonnegative",
        ),
        Index("ix_alert_rules_enabled", "is_enabled"),
        Index("ix_alert_rules_type", "rule_type"),
    )

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    rule_type: Mapped[AlertRuleType] = mapped_column(
        enum_column(AlertRuleType, "alert_rule_type"), nullable=False
    )
    metric: Mapped[str] = mapped_column(String(80), nullable=False)
    operator: Mapped[str] = mapped_column(String(8), nullable=False)
    threshold_value: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    severity: Mapped[AlertSeverity] = mapped_column(
        enum_column(AlertSeverity, "alert_severity"), nullable=False
    )
    scope: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict, server_default=text("'{}'")
    )
    cooldown_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("60")
    )
    dedupe_window_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1440")
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    in_app_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )


class Alert(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_rule_triggered", "rule_id", "triggered_at"),
        Index("ix_alerts_status_severity", "status", "severity"),
        Index("ix_alerts_dedupe_key", "dedupe_key"),
    )

    rule_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("alert_rules.id", ondelete="SET NULL"),
        nullable=True,
    )
    severity: Mapped[AlertSeverity] = mapped_column(
        enum_column(AlertSeverity, "alert_severity_value"), nullable=False
    )
    status: Mapped[AlertStatus] = mapped_column(
        enum_column(AlertStatus, "alert_status"),
        nullable=False,
        server_default=AlertStatus.ACTIVE.value,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(200), nullable=False)
    context: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict, server_default=text("'{}'")
    )
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Notification(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint(
            "alert_id", "recipient_id", "channel", name="uq_notifications_alert_recipient"
        ),
        Index("ix_notifications_recipient_read", "recipient_id", "read_at"),
        Index("ix_notifications_delivery_status", "delivery_status"),
    )

    alert_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("alerts.id", ondelete="CASCADE"),
        nullable=False,
    )
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        enum_column(NotificationChannel, "notification_channel"),
        nullable=False,
        server_default=NotificationChannel.IN_APP.value,
    )
    delivery_status: Mapped[NotificationDeliveryStatus] = mapped_column(
        enum_column(NotificationDeliveryStatus, "notification_delivery_status"),
        nullable=False,
        server_default=NotificationDeliveryStatus.PENDING.value,
    )
    dedupe_key: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (Index("ix_notification_preferences_updated", "updated_at"),)

    profile_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    in_app_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    minimum_severity: Mapped[AlertSeverity] = mapped_column(
        enum_column(AlertSeverity, "preference_alert_severity"),
        nullable=False,
        server_default=AlertSeverity.INFO.value,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class DecisionReview(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Human review of a persisted planning simulation; never execution."""

    __tablename__ = "decision_reviews"
    __table_args__ = (
        Index("ix_decision_reviews_scenario_created", "scenario_id", "created_at"),
        Index("ix_decision_reviews_status", "status"),
        Index("ix_decision_reviews_submitted_by", "submitted_by"),
        Index("ix_decision_reviews_reviewed_by", "reviewed_by"),
        Index(
            "uq_decision_reviews_active_simulation",
            "scenario_id",
            "simulation_id",
            unique=True,
            postgresql_where=text(
                "status IN ('SUBMITTED', 'APPROVED', 'REVISION_REQUESTED')"
            ),
            sqlite_where=text(
                "status IN ('SUBMITTED', 'APPROVED', 'REVISION_REQUESTED')"
            ),
        ),
    )

    scenario_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("decision_scenarios.id", ondelete="CASCADE"),
        nullable=False,
    )
    simulation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("decision_simulations.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[DecisionReviewStatus] = mapped_column(
        enum_column(DecisionReviewStatus, "decision_review_status"),
        nullable=False,
        server_default=DecisionReviewStatus.DRAFT.value,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class DecisionReviewEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "decision_review_events"
    __table_args__ = (
        Index("ix_decision_review_events_review", "review_id", "created_at"),
        Index("ix_decision_review_events_actor", "actor_id"),
    )

    review_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("decision_reviews.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_status: Mapped[DecisionReviewStatus | None] = mapped_column(
        enum_column(DecisionReviewStatus, "review_event_from_status"), nullable=True
    )
    to_status: Mapped[DecisionReviewStatus] = mapped_column(
        enum_column(DecisionReviewStatus, "review_event_to_status"), nullable=False
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
