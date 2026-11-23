"""Spatial risk aggregation and historical assessment foundations."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
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
    RiskCategory,
    RiskEntityType,
    RiskLevel,
    TrendDirection,
)
from app.models.types import enum_column


class RiskCell(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "risk_cells"
    __table_args__ = (
        CheckConstraint(
            "resolution >= 0 AND resolution <= 15", name="resolution_range"
        ),
        CheckConstraint(
            "current_risk_score >= 0 AND current_risk_score <= 100",
            name="risk_score_range",
        ),
        CheckConstraint("incident_count >= 0", name="incident_count_nonnegative"),
        UniqueConstraint("h3_cell_id", name="h3_cell_unique"),
        Index("ix_risk_cells_resolution", "resolution"),
        Index("ix_risk_cells_current_risk_score", "current_risk_score"),
        Index(
            "ix_risk_cells_boundary_gist",
            "boundary",
            postgresql_using="gist",
        ),
    )

    h3_cell_id: Mapped[str] = mapped_column(String(32), nullable=False)
    resolution: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    boundary: Mapped[str] = mapped_column(
        geometry_type("POLYGON"), nullable=False
    )
    current_risk_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default=text("0")
    )
    incident_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class RiskAssessment(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "risk_assessments"
    __table_args__ = (
        CheckConstraint(
            "score >= 0 AND score <= 100", name="assessment_score_range"
        ),
        Index(
            "ix_risk_assessments_entity",
            "entity_type",
            "entity_id",
            "assessed_at",
        ),
        Index("ix_risk_assessments_model_version", "model_version"),
        Index("ix_risk_assessments_risk_level", "risk_level"),
    )

    # Polymorphic reference. A database FK is deliberately not used because
    # assessments can target incidents, assets, departments, risk cells, or
    # scenarios; integrity is enforced by the application layer.
    entity_type: Mapped[RiskEntityType] = mapped_column(
        enum_column(RiskEntityType, "risk_entity_type"), nullable=False
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False
    )
    score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    risk_level: Mapped[RiskLevel] = mapped_column(
        enum_column(RiskLevel, "risk_level"), nullable=False
    )
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    explanation: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict
    )
    assessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class RiskModelRun(UUIDPrimaryKeyMixin, Base):
    """Immutable metadata for a persisted risk calculation.

    On-demand API responses do not require a persisted run. WORKER/ADMIN users
    can explicitly persist a run for audit/history; snapshots are tied to the
    exact model version and configuration hash used to produce them.
    """

    __tablename__ = "risk_model_runs"
    __table_args__ = (
        CheckConstraint("resolution >= 5 AND resolution <= 12", name="run_resolution_range"),
        CheckConstraint("window_hours >= 1", name="run_window_positive"),
        CheckConstraint("cell_count >= 0", name="run_cell_count_nonnegative"),
        Index("ix_risk_model_runs_calculated_at", "calculated_at"),
        Index("ix_risk_model_runs_model_version", "model_version"),
        Index("ix_risk_model_runs_requested_by", "requested_by"),
    )

    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    resolution: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    window_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    window_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    query_parameters: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict, server_default=text("'{}'")
    )
    incident_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    cell_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    duration_ms: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    summary: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict, server_default=text("'{}'")
    )
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class RiskCellSnapshot(UUIDPrimaryKeyMixin, Base):
    """Persisted, explainable risk aggregation for one H3 cell in one run."""

    __tablename__ = "risk_cell_snapshots"
    __table_args__ = (
        CheckConstraint("resolution >= 5 AND resolution <= 12", name="snapshot_resolution_range"),
        CheckConstraint(
            "risk_score >= 0 AND risk_score <= 100", name="snapshot_score_range"
        ),
        CheckConstraint(
            "incident_activity_score >= 0 AND incident_activity_score <= 100",
            name="snapshot_activity_score_range",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="snapshot_confidence_range"
        ),
        CheckConstraint("incident_count >= 0", name="snapshot_incident_count_nonnegative"),
        UniqueConstraint("run_id", "h3_cell_id", name="snapshot_run_cell_unique"),
        Index("ix_risk_cell_snapshots_run_score", "run_id", "risk_score"),
        Index("ix_risk_cell_snapshots_h3_cell_id", "h3_cell_id"),
        Index("ix_risk_cell_snapshots_resolution", "resolution"),
        Index(
            "ix_risk_cell_snapshots_boundary_gist",
            "boundary",
            postgresql_using="gist",
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("risk_model_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    h3_cell_id: Mapped[str] = mapped_column(String(32), nullable=False)
    resolution: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    boundary: Mapped[str] = mapped_column(geometry_type("POLYGON"), nullable=False)
    risk_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    incident_activity_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    risk_category: Mapped[RiskCategory] = mapped_column(
        enum_column(RiskCategory, "risk_category"), nullable=False
    )
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    incident_count: Mapped[int] = mapped_column(Integer, nullable=False)
    active_count: Mapped[int] = mapped_column(Integer, nullable=False)
    adjusted_incident_count: Mapped[int] = mapped_column(Integer, nullable=False)
    severity_distribution: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict, server_default=text("'{}'")
    )
    category_distribution: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict, server_default=text("'{}'")
    )
    factor_contributions: Mapped[list[dict]] = mapped_column(
        jsonb_column_type(), nullable=False, default=list, server_default=text("'[]'")
    )
    available_factors: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict, server_default=text("'{}'")
    )
    infrastructure_exposure: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict, server_default=text("'{}'")
    )
    trend: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict, server_default=text("'{}'")
    )
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
