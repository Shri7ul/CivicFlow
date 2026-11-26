"""Weather assessment orchestration, persistence and fault tolerance."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser
from app.core.config import Settings
from app.core.exceptions import AppError
from app.models import (
    Incident,
    IncidentAssignment,
    Role,
    WeatherAssessment,
    WeatherAssessmentStatus,
    WorkerProfile,
)
from app.services.incidents import get_incident, parse_point
from app.weather import rules
from app.weather.errors import WeatherProviderError, invalid_coordinates
from app.weather.provider import WeatherProvider, build_provider

ATTRIBUTION = {
    "open-meteo": "Weather data by Open-Meteo.com (CC BY 4.0)",
    "mock": "Simulated weather data (MOCK provider; not observed conditions)",
}
DEFAULT_ATTRIBUTION = "Weather provider attribution unavailable"


def attribution_for(provider: str) -> str:
    return ATTRIBUTION.get(provider, DEFAULT_ATTRIBUTION)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _status_value(record: WeatherAssessment) -> str:
    status = record.status
    return str(status.value if hasattr(status, "value") else status)


def _freshness_seconds(record: WeatherAssessment, now: datetime) -> float:
    retrieved = record.retrieved_at
    if retrieved.tzinfo is None:
        retrieved = retrieved.replace(tzinfo=timezone.utc)
    return max(0.0, (now - retrieved).total_seconds())


def _cache_seconds(settings: Settings) -> int:
    return settings.weather_cache_ttl_minutes * 60


def _within_retry_window(record: WeatherAssessment, settings: Settings, now: datetime) -> bool:
    if record.last_attempt_at is None:
        return False
    attempted = record.last_attempt_at
    if attempted.tzinfo is None:
        attempted = attempted.replace(tzinfo=timezone.utc)
    return (now - attempted).total_seconds() < _cache_seconds(settings)


def _valid_coordinates(latitude: float, longitude: float) -> bool:
    return -90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0


def _error_assessment(code: str, message: str) -> dict:
    return {
        "status": "ERROR",
        "rule_engine_version": rules.RULE_ENGINE_VERSION,
        "error_code": code,
        "explanation": message,
        "uncertainty": (
            "No weather data was retrieved. No impact conclusion can be drawn "
            "from this assessment."
        ),
        "decision_note": rules.DECISION_NOTE,
        "signals": [],
    }


def _disabled_assessment() -> dict:
    return {
        "status": "DISABLED",
        "rule_engine_version": rules.RULE_ENGINE_VERSION,
        "explanation": "Weather assessment is disabled in this deployment.",
        "uncertainty": rules.UNCERTAINTY,
        "decision_note": rules.DECISION_NOTE,
        "signals": [],
    }


def ensure_assessment(
    session: Session,
    incident: Incident,
    settings: Settings,
    *,
    force: bool = False,
    reason: str | None = None,
    provider: WeatherProvider | None = None,
) -> WeatherAssessment:
    """Return the incident's assessment, fetching only when useful.

    Quota discipline: a fresh OK record is reused; a failed attempt is not
    retried until the cache TTL elapses unless ``force`` is set. On provider
    failure an existing good snapshot is retained and marked STALE, so the UI
    can show last-known data with an explicit stale label instead of inventing
    a replacement.
    """
    now = _now()
    existing = session.scalar(
        select(WeatherAssessment).where(WeatherAssessment.incident_id == incident.id)
    )

    if not force and existing is not None:
        current_status = _status_value(existing)
        if current_status == WeatherAssessmentStatus.OK.value and _freshness_seconds(existing, now) <= _cache_seconds(settings):
            return existing
        if current_status in (
            WeatherAssessmentStatus.ERROR.value,
            WeatherAssessmentStatus.STALE.value,
        ) and _within_retry_window(existing, settings, now):
            return existing

    if not settings.weather_enabled:
        return _write_disabled(session, incident, existing, now)

    try:
        try:
            latitude, longitude = parse_point(incident.location)
        except AppError as exc:
            raise invalid_coordinates() from exc
        if not _valid_coordinates(latitude, longitude):
            raise invalid_coordinates()
        selected = provider or build_provider(settings)
        snapshot = selected.fetch(latitude, longitude)
        result = rules.assess(incident, snapshot, settings)
    except WeatherProviderError as exc:
        return _write_failure(session, incident, existing, exc, now, reason)

    if existing is None:
        record = WeatherAssessment(
            id=uuid.uuid4(),
            incident_id=incident.id,
            created_at=now,
        )
    else:
        record = existing
    record.latitude = latitude
    record.longitude = longitude
    record.provider = snapshot.provider
    record.retrieved_at = snapshot.retrieved_at
    record.observed_at = _parse_iso(snapshot.current.observed_at)
    record.forecast_from = _parse_iso(result["weather_summary"]["forecast_from"])
    record.forecast_to = _parse_iso(result["weather_summary"]["forecast_to"])
    record.weather_snapshot = snapshot.as_dict()
    record.assessment = result
    record.rule_engine_version = rules.RULE_ENGINE_VERSION
    record.status = WeatherAssessmentStatus.OK
    record.error_code = None
    record.last_attempt_at = now
    record.refresh_count = (record.refresh_count or 0) + 1 if existing is not None else 1
    session.add(record)
    session.flush()
    return record


def _parse_iso(value: str | datetime | None) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _write_failure(
    session: Session,
    incident: Incident,
    existing: WeatherAssessment | None,
    error: WeatherProviderError,
    now: datetime,
    reason: str | None,
) -> WeatherAssessment:
    if existing is not None and existing.weather_snapshot:
        # Stale-while-error: keep the last good evidence, label it STALE.
        existing.status = WeatherAssessmentStatus.STALE
        existing.error_code = error.code
        existing.last_attempt_at = now
        existing.refresh_count = (existing.refresh_count or 1) + 1
        retained = dict(existing.assessment or {})
        retained["status"] = "STALE"
        retained["stale_reason"] = error.code
        if reason:
            retained["refresh_reason"] = reason
        existing.assessment = retained
        session.add(existing)
        session.flush()
        return existing

    if existing is None:
        record = WeatherAssessment(
            id=uuid.uuid4(), incident_id=incident.id, created_at=now
        )
    else:
        record = existing
    try:
        latitude, longitude = parse_point(incident.location)
    except Exception:
        latitude, longitude = 0.0, 0.0
    record.latitude = latitude
    record.longitude = longitude
    record.provider = "unavailable"
    record.retrieved_at = now
    record.weather_snapshot = {}
    record.assessment = _error_assessment(error.code, error.message)
    record.rule_engine_version = rules.RULE_ENGINE_VERSION
    record.status = WeatherAssessmentStatus.ERROR
    record.error_code = error.code
    record.last_attempt_at = now
    record.refresh_count = (record.refresh_count or 0) + 1 if existing is not None else 1
    session.add(record)
    session.flush()
    return record


def _write_disabled(
    session: Session,
    incident: Incident,
    existing: WeatherAssessment | None,
    now: datetime,
) -> WeatherAssessment:
    if existing is None:
        record = WeatherAssessment(
            id=uuid.uuid4(), incident_id=incident.id, created_at=now
        )
    else:
        record = existing
    try:
        latitude, longitude = parse_point(incident.location)
    except Exception:
        latitude, longitude = 0.0, 0.0
    record.latitude = latitude
    record.longitude = longitude
    record.provider = "disabled"
    record.retrieved_at = now
    record.weather_snapshot = {}
    record.assessment = _disabled_assessment()
    record.rule_engine_version = rules.RULE_ENGINE_VERSION
    record.status = WeatherAssessmentStatus.DISABLED
    record.error_code = "weather_disabled"
    record.last_attempt_at = now
    record.refresh_count = (record.refresh_count or 0) + 1 if existing is not None else 1
    session.add(record)
    session.flush()
    return record


def assert_weather_visible(
    session: Session, user: AuthenticatedUser, incident_id: uuid.UUID
) -> Incident:
    """Citizens see own incidents; workers only assigned incidents; admins all."""
    incident = get_incident(session, incident_id, user)
    if user.profile.role is Role.WORKER:
        worker = session.scalar(
            select(WorkerProfile).where(WorkerProfile.profile_id == user.profile.id)
        )
        assignment = None
        if worker is not None:
            assignment = session.scalar(
                select(IncidentAssignment).where(
                    IncidentAssignment.incident_id == incident_id,
                    IncidentAssignment.worker_id == worker.id,
                )
            )
        if assignment is None:
            raise AppError(
                "Incident not found.",
                status_code=404,
                code="incident_not_found",
            )
    return incident


def to_response(record: WeatherAssessment, settings: Settings):
    from app.schemas.weather import WeatherAssessmentResponse

    now = _now()
    stale = _status_value(record) == WeatherAssessmentStatus.STALE.value or (
        _freshness_seconds(record, now) > _cache_seconds(settings)
    )
    return WeatherAssessmentResponse(
        id=record.id,
        incident_id=record.incident_id,
        status=record.status.value
        if hasattr(record.status, "value")
        else str(record.status),
        provider=record.provider,
        retrieved_at=record.retrieved_at,
        observed_at=record.observed_at,
        forecast_from=record.forecast_from,
        forecast_to=record.forecast_to,
        weather_snapshot=record.weather_snapshot or {},
        assessment=record.assessment or {},
        rule_engine_version=record.rule_engine_version,
        error_code=record.error_code,
        refresh_count=record.refresh_count,
        last_attempt_at=record.last_attempt_at,
        stale=stale,
        source_attribution=attribution_for(record.provider),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )
