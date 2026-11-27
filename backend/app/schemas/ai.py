"""Schemas for the optional Civic AI assistant."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import IncidentCategory, IncidentSeverity


class AIConfigResponse(BaseModel):
    available: bool
    provider: str
    model: str | None = None


class AIInsightsResponse(BaseModel):
    available: bool
    source: str
    summary: str
    highlights: list[str]
    limitations: str
    generated_at: datetime
    incident_count: int
    model: str | None = None


class TriageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=4000)


class TriageResponse(BaseModel):
    available: bool
    source: str
    suggested_category: IncidentCategory | None = None
    suggested_severity: IncidentSeverity | None = None
    rationale: str
    limitations: str
    model: str | None = None
