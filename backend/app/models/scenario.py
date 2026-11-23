"""Scenario simulation foundations (no simulation engine)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    jsonb_column_type,
)
from app.models.enums import ScenarioStatus
from app.models.types import enum_column


class Scenario(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "scenarios"
    __table_args__ = (
        Index("ix_scenarios_created_by", "created_by"),
        Index("ix_scenarios_status", "status"),
        Index("ix_scenarios_created_at", "created_at"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    parameters: Mapped[dict] = mapped_column(
        jsonb_column_type(),
        nullable=False,
        default=dict,
        server_default=text("'{}'"),
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[ScenarioStatus] = mapped_column(
        enum_column(ScenarioStatus, "scenario_status"),
        nullable=False,
        server_default=ScenarioStatus.DRAFT.value,
    )

    creator: Mapped["Profile"] = relationship(
        back_populates="scenarios", foreign_keys=[created_by]
    )
    results: Mapped[list["ScenarioResult"]] = relationship(
        back_populates="scenario", cascade="all, delete-orphan"
    )


class ScenarioResult(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "scenario_results"
    __table_args__ = (
        Index("ix_scenario_results_scenario_id", "scenario_id"),
        Index("ix_scenario_results_calculated_at", "calculated_at"),
    )

    scenario_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("scenarios.id", ondelete="CASCADE"),
        nullable=False,
    )
    result: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict
    )
    summary: Mapped[dict | None] = mapped_column(
        jsonb_column_type(), nullable=True
    )
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    scenario: Mapped["Scenario"] = relationship(back_populates="results")
