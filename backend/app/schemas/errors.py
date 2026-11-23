"""API error response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    code: str = Field(description="Stable machine-readable error code")
    message: str = Field(description="Safe, human-readable error message")
    details: list[dict[str, Any]] | None = Field(
        default=None, description="Optional structured error details"
    )


class ErrorResponse(BaseModel):
    error: ErrorBody
