"""Weather assessment API.

Reads are scoped to the caller's visible incidents; refresh is ADMIN-only so
citizens and workers cannot consume provider quota.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser, require_active_user, require_admin
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.schemas.weather import (
    WeatherAssessmentResponse,
    WeatherConfigResponse,
    WeatherRefreshRequest,
)
from app.services.incidents import get_incident
from app.weather import rules
from app.weather.service import assert_weather_visible, attribution_for, ensure_assessment, to_response

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db_session)]
AdminUser = Annotated[AuthenticatedUser, Depends(require_admin)]
ActiveUser = Annotated[AuthenticatedUser, Depends(require_active_user)]
AppSettings = Annotated[Settings, Depends(get_settings)]


@router.get(
    "/incidents/{incident_id}/assessment",
    response_model=WeatherAssessmentResponse,
    summary="Read or create the weather assessment for a visible incident",
)
def read_assessment(
    incident_id: uuid.UUID,
    user: ActiveUser,
    session: DbSession,
    settings: AppSettings,
) -> WeatherAssessmentResponse:
    incident = assert_weather_visible(session, user, incident_id)
    record = ensure_assessment(session, incident, settings)
    return to_response(record, settings)


@router.post(
    "/incidents/{incident_id}/assessment/refresh",
    response_model=WeatherAssessmentResponse,
    summary="Force a weather reassessment (ADMIN)",
)
def refresh_assessment(
    incident_id: uuid.UUID,
    admin: AdminUser,
    session: DbSession,
    settings: AppSettings,
    payload: WeatherRefreshRequest | None = None,
) -> WeatherAssessmentResponse:
    incident = get_incident(session, incident_id, admin)
    record = ensure_assessment(
        session,
        incident,
        settings,
        force=True,
        reason=payload.reason if payload else None,
    )
    return to_response(record, settings)


@router.get(
    "/config",
    response_model=WeatherConfigResponse,
    summary="Read non-sensitive weather configuration (ADMIN)",
)
def read_config(
    _admin: AdminUser,
    settings: AppSettings,
) -> WeatherConfigResponse:
    return WeatherConfigResponse(
        enabled=settings.weather_enabled,
        provider=settings.weather_provider,
        rule_engine_version=rules.RULE_ENGINE_VERSION,
        cache_ttl_minutes=settings.weather_cache_ttl_minutes,
        forecast_hours=settings.weather_forecast_hours,
        api_key_configured=settings.weather_api_key is not None,
        source_attribution=attribution_for(settings.weather_provider),
    )
