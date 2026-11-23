"""Authentication and profile API schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import Role


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    phone: str | None
    role: Role
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProvisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, min_length=1, max_length=200)


class ProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=32)


class RoleUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Role
    reason: str | None = Field(default=None, max_length=500)
