"""Incident, department, and lifecycle API schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import (
    IncidentCategory,
    IncidentSeverity,
    IncidentStatus,
)


class ProfileSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str


class DepartmentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class DepartmentResponse(DepartmentSummary):
    description: str | None
    is_active: bool


class StatusEventResponse(BaseModel):
    id: uuid.UUID
    from_status: IncidentStatus | None
    to_status: IncidentStatus
    note: str | None
    actor: ProfileSummary | None
    created_at: datetime


def _strip_required(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("must not be blank")
    return cleaned


class IncidentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10, max_length=10000)
    category: IncidentCategory
    severity: IncidentSeverity
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    address: str | None = Field(default=None, max_length=500)

    @field_validator("title", "description")
    @classmethod
    def _required_text(cls, value: str) -> str:
        return _strip_required(value)

    @field_validator("address")
    @classmethod
    def _optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class IncidentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, min_length=10, max_length=10000)
    category: IncidentCategory | None = None
    severity: IncidentSeverity | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    address: str | None = Field(default=None, max_length=500)

    @field_validator("title", "description")
    @classmethod
    def _optional_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _strip_required(value)

    @field_validator("address")
    @classmethod
    def _optional_address(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class IncidentStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: IncidentStatus
    department_id: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=500)

    @field_validator("note")
    @classmethod
    def _optional_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class EvidenceResponse(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    file_name: str
    mime_type: str
    file_size: int
    uploader: ProfileSummary
    created_at: datetime


class EvidenceUrlResponse(BaseModel):
    signed_url: str
    expires_in: int


class IncidentResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    category: IncidentCategory
    severity: IncidentSeverity
    status: IncidentStatus
    latitude: float
    longitude: float
    address: str | None
    reporter: ProfileSummary
    assigned_department: DepartmentSummary | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime
    history: list[StatusEventResponse] = Field(default_factory=list)
    evidence: list[EvidenceResponse] = Field(default_factory=list)


class IncidentListResponse(BaseModel):
    items: list[IncidentResponse]
    total: int
    page: int
    page_size: int
    pages: int
