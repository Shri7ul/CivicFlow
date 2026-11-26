"""Persisted weather-aware incident impact assessments.

One assessment is kept per incident. A refresh replaces the snapshot and the
assessment in place; a failed refresh retains the last good data and marks the
row STALE so a provider outage never fabricates or deletes evidence.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    jsonb_column_type,
)
from app.models.enums import WeatherAssessmentStatus


class WeatherAssessment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "weather_assessments"
    __table_args__ = (
        Index("ix_weather_assessments_retrieved", "retrieved_at"),
        Index("ix_weather_assessments_status", "status"),
    )

    incident_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, unique=True
    )
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    observed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    forecast_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    forecast_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    weather_snapshot: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict
    )
    assessment: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict
    )
    rule_engine_version: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[WeatherAssessmentStatus] = mapped_column(
        String(20), nullable=False, default=WeatherAssessmentStatus.OK
    )
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    refresh_count: Mapped[int] = mapped_column(nullable=False, default=1)
