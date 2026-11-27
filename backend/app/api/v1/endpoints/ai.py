"""Civic AI assistant endpoints (optional Groq key, deterministic fallback)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser, require_active_user
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.schemas.ai import (
    AIConfigResponse,
    AIInsightsResponse,
    TriageRequest,
    TriageResponse,
)
from app.services.ai import ai_available, local_insights, suggest_triage
from app.services.incidents import list_incidents

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db_session)]
ActiveUser = Annotated[AuthenticatedUser, Depends(require_active_user)]
AppSettings = Annotated[Settings, Depends(get_settings)]


@router.get("/config", response_model=AIConfigResponse, summary="Civic AI availability")
def ai_config(settings: AppSettings, user: ActiveUser) -> AIConfigResponse:
    available = ai_available(settings)
    return AIConfigResponse(
        available=available,
        provider="groq" if available else "deterministic",
        model=settings.groq_model if available else None,
    )


@router.get(
    "/insights",
    response_model=AIInsightsResponse,
    summary="Local insights for the signed-in citizen",
)
def ai_insights(
    user: ActiveUser,
    session: DbSession,
    settings: AppSettings,
) -> AIInsightsResponse:
    # Reuse the incident service so visibility rules are identical to the
    # citizen dashboard and no extra data is exposed.
    visible = list_incidents(session, user=user, page=1, page_size=100)
    return AIInsightsResponse(**local_insights(visible.items, settings))


@router.post(
    "/triage",
    response_model=TriageResponse,
    summary="Advisory category/severity helper for a draft report",
)
def ai_triage(
    payload: TriageRequest,
    user: ActiveUser,
    settings: AppSettings,
) -> TriageResponse:
    return TriageResponse(
        **suggest_triage(payload.title, payload.description, settings)
    )
