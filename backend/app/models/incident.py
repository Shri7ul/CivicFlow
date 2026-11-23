"""Incident and evidence schema foundations."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
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
    point_geography_type,
)
from app.models.enums import IncidentCategory, IncidentSeverity, IncidentStatus
from app.models.types import enum_column


class Incident(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "incidents"
    __table_args__ = (
        CheckConstraint(
            "resolved_at IS NULL OR resolved_at >= created_at",
            name="resolved_after_created",
        ),
        Index("ix_incidents_status_severity", "status", "severity"),
        Index("ix_incidents_category", "category"),
        Index("ix_incidents_reporter_id", "reporter_id"),
        Index("ix_incidents_assigned_department_id", "assigned_department_id"),
        Index("ix_incidents_created_at", "created_at"),
        Index("ix_incidents_location_gist", "location", postgresql_using="gist"),
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[IncidentCategory] = mapped_column(
        enum_column(IncidentCategory, "incident_category"), nullable=False
    )
    severity: Mapped[IncidentSeverity] = mapped_column(
        enum_column(IncidentSeverity, "incident_severity"), nullable=False
    )
    status: Mapped[IncidentStatus] = mapped_column(
        enum_column(IncidentStatus, "incident_status"),
        nullable=False,
        server_default=IncidentStatus.OPEN.value,
    )
    location: Mapped[str] = mapped_column(
        point_geography_type(), nullable=False
    )
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reporter_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    assigned_department_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    reporter: Mapped["Profile"] = relationship(
        back_populates="reported_incidents", foreign_keys=[reporter_id]
    )
    assigned_department: Mapped["Department | None"] = relationship(
        back_populates="incidents"
    )
    evidence: Mapped[list["IncidentEvidence"]] = relationship(
        back_populates="incident"
    )
    cluster_membership: Mapped["IncidentClusterMember | None"] = relationship(
        back_populates="incident", uselist=False
    )
    status_events: Mapped[list["IncidentStatusEvent"]] = relationship(
        back_populates="incident",
        order_by="IncidentStatusEvent.created_at",
    )


class IncidentEvidence(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "incident_evidence"
    __table_args__ = (
        CheckConstraint("file_size > 0", name="file_size_positive"),
        CheckConstraint(
            "file_size <= 10485760", name="file_size_max"
        ),
        CheckConstraint(
            "mime_type IN ('image/jpeg', 'image/png', 'image/webp')",
            name="allowed_mime_type",
        ),
        UniqueConstraint("storage_path", name="storage_path_unique"),
        Index("ix_incident_evidence_incident_id", "incident_id"),
        Index("ix_incident_evidence_uploaded_by", "uploaded_by"),
        Index("ix_incident_evidence_created_at", "created_at"),
        Index(
            "ix_incident_evidence_incident_created",
            "incident_id",
            "created_at",
        ),
    )

    incident_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("incidents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(127), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    incident: Mapped["Incident"] = relationship(back_populates="evidence")
    uploader: Mapped["Profile"] = relationship(
        back_populates="uploaded_evidence", foreign_keys=[uploaded_by]
    )


class IncidentStatusEvent(UUIDPrimaryKeyMixin, Base):
    """Immutable lifecycle history for an incident."""

    __tablename__ = "incident_status_events"
    __table_args__ = (
        Index(
            "ix_incident_status_events_incident_created",
            "incident_id",
            "created_at",
        ),
        Index("ix_incident_status_events_actor_id", "actor_id"),
        CheckConstraint(
            "from_status IS NULL OR from_status <> to_status",
            name="status_change_required",
        ),
    )

    incident_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("incidents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    from_status: Mapped[IncidentStatus | None] = mapped_column(
        enum_column(IncidentStatus, "incident_status_event_from"),
        nullable=True,
    )
    to_status: Mapped[IncidentStatus] = mapped_column(
        enum_column(IncidentStatus, "incident_status_event_to"),
        nullable=False,
    )
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    incident: Mapped["Incident"] = relationship(back_populates="status_events")
    actor: Mapped["Profile | None"] = relationship(
        back_populates="incident_status_events",
        foreign_keys=[actor_id],
    )
