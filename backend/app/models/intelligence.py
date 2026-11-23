"""Reviewable incident correlation and duplicate relationships."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
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
from app.models.enums import RelationshipStatus, RelationshipType
from app.models.types import enum_column


class IncidentRelationship(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A reviewed relationship between two incidents.

    The pair is stored canonically (``incident_a_id < incident_b_id``) so a
    relationship cannot be duplicated by submitting the reverse pair. The
    engine only creates suggestions on read; a WORKER/ADMIN must explicitly
    confirm or dismiss one through the API.
    """

    __tablename__ = "incident_relationships"
    __table_args__ = (
        CheckConstraint(
            "incident_a_id <> incident_b_id",
            name="different_incidents",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="confidence_range",
        ),
        UniqueConstraint(
            "incident_a_id",
            "incident_b_id",
            "relationship_type",
            name="relationship_logical_unique",
        ),
        Index("ix_incident_relationships_a", "incident_a_id"),
        Index("ix_incident_relationships_b", "incident_b_id"),
        Index("ix_incident_relationships_status", "status"),
        Index("ix_incident_relationships_reviewed_by", "reviewed_by"),
    )

    incident_a_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("incidents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    incident_b_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("incidents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    relationship_type: Mapped[RelationshipType] = mapped_column(
        enum_column(RelationshipType, "relationship_type"), nullable=False
    )
    status: Mapped[RelationshipStatus] = mapped_column(
        enum_column(RelationshipStatus, "relationship_status"), nullable=False
    )
    confidence: Mapped[Decimal] = mapped_column(
        Numeric(4, 3), nullable=False, server_default=text("1.0")
    )
    signals: Mapped[dict] = mapped_column(
        jsonb_column_type(),
        nullable=False,
        default=dict,
        server_default=text("'{}'"),
    )
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    incident_a: Mapped["Incident"] = relationship(
        foreign_keys=[incident_a_id]
    )
    incident_b: Mapped["Incident"] = relationship(
        foreign_keys=[incident_b_id]
    )
    reviewer: Mapped["Profile | None"] = relationship(
        foreign_keys=[reviewed_by]
    )
