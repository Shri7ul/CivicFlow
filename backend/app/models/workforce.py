"""Municipal workforce control records.

These tables implement worker applications, approved worker profiles, incident
assignments, assignment history, an append-only audit stream and direct in-app
notifications. No table in this module authorizes dispatch or real-world action:
every state change is deliberate, server-validated and recorded.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
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
    jsonb_column_type,
)
from app.models.types import enum_column
from app.models.enums import (
    AssignmentStatus,
    WorkerApplicationStatus,
    WorkerStatus,
)


class WorkerApplication(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A citizen's application to become an authorized field worker."""

    __tablename__ = "worker_applications"
    __table_args__ = (
        UniqueConstraint("applicant_id", name="uq_worker_applications_applicant"),
        Index("ix_worker_applications_status_created", "status", "created_at"),
        Index("ix_worker_applications_department", "department_id"),
    )

    applicant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    specialization: Mapped[str] = mapped_column(String(80), nullable=False)
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
    )
    service_area: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    experience: Mapped[str | None] = mapped_column(Text, nullable=True)
    credentials_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[WorkerApplicationStatus] = mapped_column(
        enum_column(WorkerApplicationStatus, "worker_application_status"),
        nullable=False,
        default=WorkerApplicationStatus.PENDING,
        server_default=WorkerApplicationStatus.PENDING.value,
    )
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class WorkerProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Operational profile created only after an explicit ADMIN approval."""

    __tablename__ = "worker_profiles"
    __table_args__ = (
        UniqueConstraint("profile_id", name="uq_worker_profiles_profile"),
        UniqueConstraint("application_id", name="uq_worker_profiles_application"),
        Index("ix_worker_profiles_status_area", "status", "service_area"),
        Index("ix_worker_profiles_department", "department_id"),
    )

    profile_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("worker_applications.id", ondelete="RESTRICT"),
        nullable=False,
    )
    specialization: Mapped[str] = mapped_column(String(80), nullable=False)
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
    )
    service_area: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[WorkerStatus] = mapped_column(
        enum_column(WorkerStatus, "worker_status"),
        nullable=False,
        default=WorkerStatus.ACTIVE,
        server_default=WorkerStatus.ACTIVE.value,
    )
    approved_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    approved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class IncidentAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A deliberate, authorized assignment of one incident to one worker."""

    __tablename__ = "incident_assignments"
    __table_args__ = (
        Index("ix_incident_assignments_incident", "incident_id", "created_at"),
        Index("ix_incident_assignments_worker_status", "worker_id", "status"),
        Index("ix_incident_assignments_status", "status"),
        CheckConstraint(
            "deadline IS NULL OR created_at IS NULL OR deadline >= created_at",
            name="ck_incident_assignments_deadline_after_creation",
        ),
    )

    incident_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("incidents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    worker_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("worker_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    assigned_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[AssignmentStatus] = mapped_column(
        enum_column(AssignmentStatus, "assignment_status"),
        nullable=False,
        default=AssignmentStatus.OFFERED,
        server_default=AssignmentStatus.OFFERED.value,
    )
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    completion_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    events: Mapped[list["IncidentAssignmentEvent"]] = relationship(
        back_populates="assignment", cascade="all, delete-orphan"
    )


class IncidentAssignmentEvent(UUIDPrimaryKeyMixin, Base):
    """Append-only history of assignment state changes."""

    __tablename__ = "incident_assignment_events"
    __table_args__ = (
        Index("ix_incident_assignment_events_assignment", "assignment_id", "created_at"),
        Index("ix_incident_assignment_events_actor", "actor_id"),
    )

    assignment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("incident_assignments.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    from_status: Mapped[AssignmentStatus | None] = mapped_column(
        enum_column(AssignmentStatus, "assignment_event_from"), nullable=True
    )
    to_status: Mapped[AssignmentStatus] = mapped_column(
        enum_column(AssignmentStatus, "assignment_event_to"), nullable=False
    )
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    assignment: Mapped["IncidentAssignment"] = relationship(back_populates="events")


class WorkforceEvent(UUIDPrimaryKeyMixin, Base):
    """Append-only cross-domain audit event. Never editable through the API."""

    __tablename__ = "workforce_events"
    __table_args__ = (
        Index("ix_workforce_events_entity", "entity_type", "entity_id"),
        Index("ix_workforce_events_actor", "actor_id"),
        Index("ix_workforce_events_created", "created_at"),
    )

    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    previous_state: Mapped[str | None] = mapped_column(String(80), nullable=True)
    new_state: Mapped[str | None] = mapped_column(String(80), nullable=True)
    detail: Mapped[dict] = mapped_column(
        "metadata", jsonb_column_type(), nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class WorkforceNotification(UUIDPrimaryKeyMixin, Base):
    """Direct in-app lifecycle message. No credentials or private URLs."""

    __tablename__ = "workforce_notifications"
    __table_args__ = (
        Index("ix_workforce_notifications_recipient_read", "recipient_id", "read_at"),
        Index("ix_workforce_notifications_created", "created_at"),
    )

    recipient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
