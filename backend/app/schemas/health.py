"""Health endpoint schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["healthy"] = "healthy"
    service: str = Field(description="Public service identifier")
    environment: str = Field(description="Deployment environment")
    version: str = Field(description="API version")


class DatabaseHealthResponse(BaseModel):
    status: Literal["healthy", "unhealthy", "not_configured"]
    database: Literal["reachable", "unreachable", "not_configured"]
    message: str


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    build_version: str
    database: Literal["reachable", "unreachable", "not_configured"]
    message: str


class DependencyHealthResponse(BaseModel):
    status: Literal["operational", "degraded"]
    build_version: str
    database: Literal["reachable", "unreachable", "not_configured"]
    auth_verification_configured: bool
    evidence_storage_configured: bool
