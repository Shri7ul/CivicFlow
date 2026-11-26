"""Pydantic contracts for the municipal workforce APIs."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import (
    AssignmentStatus,
    WorkerApplicationStatus,
    WorkerStatus,
)

ReviewDecision = Literal["APPROVE", "REJECT", "REQUEST_INFO", "UNDER_REVIEW"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _nonblank(value: str | None, field: str) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field} must not be blank")
    return cleaned


class WorkerApplicationCreate(_Strict):
    full_name: str = Field(min_length=2, max_length=200)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=254)
    specialization: str = Field(min_length=2, max_length=80)
    department_id: uuid.UUID | None = None
    service_area: str = Field(min_length=2, max_length=200)
    address: str | None = Field(default=None, max_length=500)
    experience: str | None = Field(default=None, max_length=5000)
    credentials_note: str | None = Field(default=None, max_length=2000)

    @field_validator(
        "full_name",
        "specialization",
        "service_area",
        "phone",
        "email",
        "address",
        "experience",
        "credentials_note",
    )
    @classmethod
    def clean(cls, value: str | None, info) -> str | None:
        return _nonblank(value, info.field_name)


class ApplicationReviewRequest(_Strict):
    decision: ReviewDecision
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("note")
    @classmethod
    def clean_note(cls, value: str | None) -> str | None:
        return _nonblank(value, "note")


class WorkerApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    applicant_id: uuid.UUID
    full_name: str
    phone: str | None
    email: str | None
    specialization: str
    department_id: uuid.UUID | None
    service_area: str
    address: str | None
    experience: str | None
    credentials_note: str | None
    status: WorkerApplicationStatus
    review_note: str | None
    reviewer_id: uuid.UUID | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ApplicationListResponse(BaseModel):
    items: list[WorkerApplicationResponse]
    total: int
    limit: int
    offset: int


class WorkerProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    profile_id: uuid.UUID
    application_id: uuid.UUID
    specialization: str
    department_id: uuid.UUID | None
    service_area: str
    status: WorkerStatus
    approved_by: uuid.UUID
    approved_at: datetime
    full_name: str | None = None
    active_assignments: int = 0
    total_assignments: int = 0


class WorkerListResponse(BaseModel):
    items: list[WorkerProfileResponse]
    total: int
    limit: int
    offset: int


class AssignmentCandidateResponse(BaseModel):
    worker_profile_id: uuid.UUID
    profile_id: uuid.UUID
    full_name: str
    specialization: str
    service_area: str
    department_id: uuid.UUID | None
    active_assignments: int
    area_match: bool
    specialization_match: bool
    eligible: bool
    rationale: str


class CandidateListResponse(BaseModel):
    incident_id: uuid.UUID
    items: list[AssignmentCandidateResponse]


class AssignmentCreateRequest(_Strict):
    incident_id: uuid.UUID
    worker_profile_id: uuid.UUID
    note: str | None = Field(default=None, max_length=1000)
    deadline: datetime | None = None

    @field_validator("note")
    @classmethod
    def clean_note(cls, value: str | None) -> str | None:
        return _nonblank(value, "note")


class ReassignRequest(_Strict):
    worker_profile_id: uuid.UUID
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("note")
    @classmethod
    def clean_note(cls, value: str | None) -> str | None:
        return _nonblank(value, "note")


class AssignmentNoteRequest(_Strict):
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("note")
    @classmethod
    def clean_note(cls, value: str | None) -> str | None:
        return _nonblank(value, "note")


class ProgressRequest(_Strict):
    note: str | None = Field(default=None, max_length=1000)
    progress_percent: int = Field(default=0, ge=0, le=100)


class CompletionRequest(_Strict):
    note: str = Field(min_length=3, max_length=2000)
    evidence_note: str | None = Field(default=None, max_length=1000)

    @field_validator("note", "evidence_note")
    @classmethod
    def clean(cls, value: str | None, info) -> str | None:
        return _nonblank(value, info.field_name)


class VerificationRequest(_Strict):
    approve: bool
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("note")
    @classmethod
    def clean_note(cls, value: str | None) -> str | None:
        return _nonblank(value, "note")


class AssignmentEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    from_status: AssignmentStatus | None
    to_status: AssignmentStatus
    note: str | None
    actor_id: uuid.UUID
    created_at: datetime


class AssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    incident_id: uuid.UUID
    worker_profile_id: uuid.UUID = Field(validation_alias="worker_id")
    assigned_by: uuid.UUID
    status: AssignmentStatus
    rationale: str | None
    note: str | None
    completion_note: str | None
    review_note: str | None
    deadline: datetime | None
    completed_at: datetime | None
    verified_at: datetime | None
    created_at: datetime
    updated_at: datetime
    events: list[AssignmentEventResponse] = Field(default_factory=list)


class AssignmentListResponse(BaseModel):
    items: list[AssignmentResponse]
    total: int
    limit: int
    offset: int


class AdminOverviewResponse(BaseModel):
    total_incidents: int
    unreviewed_incidents: int
    verified_awaiting_assignment: int
    assigned_incidents: int
    in_progress_incidents: int
    awaiting_verification: int
    verified_completed: int
    resolved_incidents: int
    rejected_incidents: int
    pending_applications: int
    active_workers: int
    suspended_workers: int


class WorkforceEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_id: uuid.UUID | None
    action: str
    entity_type: str
    entity_id: uuid.UUID
    previous_state: str | None
    new_state: str | None
    detail: dict
    created_at: datetime


class EventListResponse(BaseModel):
    items: list[WorkforceEventResponse]
    total: int
    limit: int
    offset: int


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    title: str
    body: str
    entity_type: str | None
    entity_id: uuid.UUID | None
    read_at: datetime | None
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    total: int
    unread: int
