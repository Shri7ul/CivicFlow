"""Municipal departments."""

from __future__ import annotations

from sqlalchemy import Index, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Department(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "departments"
    __table_args__ = (
        Index("ix_departments_is_active", "is_active"),
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        nullable=False, server_default=text("true")
    )

    incidents: Mapped[list["Incident"]] = relationship(
        back_populates="assigned_department"
    )


# Case-insensitive uniqueness without requiring the citext extension.
Index(
    "uq_departments_name_lower",
    func.lower(Department.name),
    unique=True,
)
