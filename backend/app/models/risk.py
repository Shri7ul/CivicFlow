"""Spatial risk aggregation and historical assessment foundations."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
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
from app.models.enums import RiskEntityType, RiskLevel
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
