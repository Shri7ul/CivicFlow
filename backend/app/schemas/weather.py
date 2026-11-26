"""Weather assessment API schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WeatherAssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    incident_id: uuid.UUID
    status: str
    provider: str
    retrieved_at: datetime
    observed_at: datetime | None
    forecast_from: datetime | None
    forecast_to: datetime | None
    weather_snapshot: dict[str, Any]
    assessment: dict[str, Any]
    rule_engine_version: str
    error_code: str | None
    refresh_count: int
    last_attempt_at: datetime | None
    stale: bool
    source_attribution: str
    created_at: datetime
    updated_at: datetime


class WeatherConfigResponse(BaseModel):
    enabled: bool
    provider: str
    rule_engine_version: str
    cache_ttl_minutes: int
    forecast_hours: int
    api_key_configured: bool
    source_attribution: str


class WeatherRefreshRequest(_Strict):
    reason: str | None = Field(default=None, max_length=300)
