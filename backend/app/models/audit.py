"""Audit trail for privileged application-role changes."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin
from app.models.enums import Role
from app.models.types import enum_column


class RoleChangeAudit(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "role_change_audits"
    __table_args__ = (
        Index("ix_role_change_audits_actor_id", "actor_id"),
        Index("ix_role_change_audits_target_profile_id", "target_profile_id"),
        Index("ix_role_change_audits_created_at", "created_at"),
    )

    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    old_role: Mapped[Role] = mapped_column(
        enum_column(Role, "audit_old_role"), nullable=False
    )
    new_role: Mapped[Role] = mapped_column(
        enum_column(Role, "audit_new_role"), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    actor: Mapped["Profile | None"] = relationship(
        back_populates="role_changes_performed", foreign_keys=[actor_id]
    )
    target: Mapped["Profile | None"] = relationship(
        back_populates="role_changes_received", foreign_keys=[target_profile_id]
    )
