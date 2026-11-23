"""Application profile linked to a Supabase Auth identity."""

from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, Index, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import Role
from app.models.types import enum_column


class Profile(TimestampMixin, Base):
    """CivicFlow application profile.

    ``id`` is supplied by the Supabase Auth provisioning path and must equal
    ``auth.users.id``. It intentionally has no UUID default so a profile cannot
    be created without an authenticated identity.
    """

    __tablename__ = "profiles"
    __table_args__ = (
        CheckConstraint("length(trim(full_name)) > 0", name="full_name_not_blank"),
        Index("ix_profiles_role_is_active", "role", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    role: Mapped[Role] = mapped_column(
        enum_column(Role, "profile_role"),
        nullable=False,
        server_default=Role.CITIZEN.value,
    )
    is_active: Mapped[bool] = mapped_column(
        nullable=False, server_default=text("true")
    )

    reported_incidents: Mapped[list["Incident"]] = relationship(
        back_populates="reporter", foreign_keys="Incident.reporter_id"
    )
    uploaded_evidence: Mapped[list["IncidentEvidence"]] = relationship(
        back_populates="uploader", foreign_keys="IncidentEvidence.uploaded_by"
    )
    scenarios: Mapped[list["Scenario"]] = relationship(
        back_populates="creator", foreign_keys="Scenario.created_by"
    )
    incident_status_events: Mapped[list["IncidentStatusEvent"]] = relationship(
        back_populates="actor"
    )
    role_changes_performed: Mapped[list["RoleChangeAudit"]] = relationship(
        back_populates="actor", foreign_keys="RoleChangeAudit.actor_id"
    )
    role_changes_received: Mapped[list["RoleChangeAudit"]] = relationship(
        back_populates="target", foreign_keys="RoleChangeAudit.target_profile_id"
    )
