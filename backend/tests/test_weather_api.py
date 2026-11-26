"""Weather assessment API, RBAC and fault-tolerance integration tests."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.jwt import get_token_verifier
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.main import create_app
from app.models import (
    Incident,
    IncidentAssignment,
    Profile,
    Role,
    WorkerApplication,
    WorkerApplicationStatus,
    WorkerProfile,
    WorkerStatus,
)
from tests.auth_support import make_settings, make_token, make_verifier
from app.weather.errors import WeatherProviderError
from app.weather.provider import MockProvider, WeatherSnapshot

INCIDENT = {
    "title": "Blocked storm drain",
    "description": "Water pooling on the road after heavy rain.",
    "category": "DRAINAGE",
    "severity": "HIGH",
    "latitude": 23.8103,
    "longitude": 90.4125,
    "address": "Road 12, Dhanmondi",
}


class SpyProvider:
    def __init__(self, delegate: Any) -> None:
        self.name = "mock"
        self.delegate = delegate
        self.calls = 0

    def fetch(self, latitude: float, longitude: float) -> WeatherSnapshot:
        self.calls += 1
        return self.delegate.fetch(latitude, longitude)


def _profile(session: Session, role: Role = Role.CITIZEN, name: str = "User") -> Profile:
    profile = Profile(id=uuid.uuid4(), full_name=name, role=role, is_active=True)
    session.add(profile)
    session.commit()
    return profile


def _auth(profile: Profile) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(sub=profile.id)}"}


def _client(session: Session, settings: Settings) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_token_verifier] = lambda: make_verifier(make_settings())
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def _report(client: TestClient, citizen: Profile, **overrides: Any) -> str:
    response = client.post(
        "/api/v1/incidents", json={**INCIDENT, **overrides}, headers=_auth(citizen)
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _assign_worker(
    session: Session, admin: Profile, worker: Profile, incident_id: str
) -> None:
    application = WorkerApplication(
        applicant_id=worker.id,
        full_name=worker.full_name or "Worker",
        specialization="Drainage",
        service_area="Dhanmondi",
        status=WorkerApplicationStatus.APPROVED,
        reviewer_id=admin.id,
    )
    session.add(application)
    session.flush()
    worker_profile = WorkerProfile(
        profile_id=worker.id,
        application_id=application.id,
        specialization="Drainage",
        service_area="Dhanmondi",
        status=WorkerStatus.ACTIVE,
        approved_by=admin.id,
    )
    session.add(worker_profile)
    session.flush()
    session.add(
        IncidentAssignment(
            incident_id=uuid.UUID(incident_id),
            worker_id=worker_profile.id,
            assigned_by=admin.id,
            status="OFFERED",
        )
    )
    session.commit()


def test_assessment_is_created_cached_and_reported_with_provenance(
    db_session: Session, monkeypatch: Any
) -> None:
    settings = make_settings(weather_enabled=False, weather_provider="mock")
    client = _client(db_session, settings)
    citizen = _profile(db_session, name="Reporter")
    incident_id = _report(client, citizen)
    assert db_session.query(Incident).filter(Incident.id == uuid.UUID(incident_id)).count() == 1

    spy = SpyProvider(MockProvider("heavy_rain"))
    monkeypatch.setattr("app.weather.service.build_provider", lambda _settings: spy)
    settings.weather_enabled = True

    url = f"/api/v1/weather/incidents/{incident_id}/assessment"
    first = client.get(url, headers=_auth(citizen))
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["status"] == "OK"
    assert body["provider"] == "mock"
    assert body["rule_engine_version"] == "weather-impact-v1"
    assert "Open-Meteo" not in body["source_attribution"]  # mock is labelled
    assert "MOCK" in body["source_attribution"]
    assert body["weather_snapshot"]["current"]["precipitation_mm"] == 18.0
    assert "R-RAIN-DRAINAGE" in body["assessment"]["rule_ids"]
    assert spy.calls == 1

    second = client.get(url, headers=_auth(citizen))
    assert second.status_code == 200
    assert second.json()["id"] == body["id"]
    assert spy.calls == 1  # cache prevented a second external request


def test_admin_refresh_is_forced_and_other_roles_are_blocked(
    db_session: Session, monkeypatch: Any
) -> None:
    settings = make_settings(weather_enabled=False, weather_provider="mock")
    client = _client(db_session, settings)
    citizen = _profile(db_session, name="Reporter")
    admin = _profile(db_session, Role.ADMIN, "Admin")
    incident_id = _report(client, citizen)

    spy = SpyProvider(MockProvider("clear"))
    monkeypatch.setattr("app.weather.service.build_provider", lambda _settings: spy)
    settings.weather_enabled = True

    url = f"/api/v1/weather/incidents/{incident_id}/assessment"
    assert client.get(url, headers=_auth(citizen)).status_code == 200
    refresh_url = f"{url}/refresh"
    denied = client.post(refresh_url, json={}, headers=_auth(citizen))
    assert denied.status_code == 403

    refreshed = client.post(
        refresh_url,
        json={"reason": "routine review"},
        headers=_auth(admin),
    )
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["refresh_count"] == 2
    assert refreshed.json()["assessment"]["signals"] == []
    assert spy.calls == 2

    config = client.get("/api/v1/weather/config", headers=_auth(admin))
    assert config.status_code == 200
    assert config.json()["enabled"] is True
    assert config.json()["api_key_configured"] is False
    assert "key" not in json_keys(config.json())
    assert client.get("/api/v1/weather/config", headers=_auth(citizen)).status_code == 403


def json_keys(payload: dict[str, Any]) -> set[str]:
    return set(payload.keys())


def test_worker_visibility_requires_an_assignment(
    db_session: Session, monkeypatch: Any
) -> None:
    settings = make_settings(weather_enabled=False, weather_provider="mock")
    client = _client(db_session, settings)
    admin = _profile(db_session, Role.ADMIN, "Admin")
    reporter = _profile(db_session, name="Reporter")
    worker = _profile(db_session, Role.WORKER, "Worker")
    incident_id = _report(client, reporter)

    spy = SpyProvider(MockProvider("clear"))
    monkeypatch.setattr("app.weather.service.build_provider", lambda _settings: spy)
    settings.weather_enabled = True
    url = f"/api/v1/weather/incidents/{incident_id}/assessment"

    assert client.get(url, headers=_auth(worker)).status_code == 404
    _assign_worker(db_session, admin, worker, incident_id)
    response = client.get(url, headers=_auth(worker))
    assert response.status_code == 200, response.text


def test_provider_failure_keeps_last_good_snapshot_as_stale(
    db_session: Session, monkeypatch: Any
) -> None:
    settings = make_settings(weather_enabled=False, weather_provider="mock")
    client = _client(db_session, settings)
    citizen = _profile(db_session, name="Reporter")
    admin = _profile(db_session, Role.ADMIN, "Admin")
    incident_id = _report(client, citizen)

    spy = SpyProvider(MockProvider("heavy_rain"))
    monkeypatch.setattr("app.weather.service.build_provider", lambda _settings: spy)
    settings.weather_enabled = True
    url = f"/api/v1/weather/incidents/{incident_id}/assessment"
    good = client.get(url, headers=_auth(citizen)).json()

    spy.delegate = FailingProvider(
        WeatherProviderError("provider_timeout", "The provider did not respond.")
    )
    refreshed = client.post(
        f"{url}/refresh", json={"reason": "outage test"}, headers=_auth(admin)
    )
    assert refreshed.status_code == 200, refreshed.text
    stale = refreshed.json()
    assert stale["status"] == "STALE"
    assert stale["stale"] is True
    assert stale["error_code"] == "provider_timeout"
    assert stale["weather_snapshot"] == good["weather_snapshot"]
    assert stale["assessment"]["status"] == "STALE"
    assert stale["assessment"]["stale_reason"] == "provider_timeout"


class FailingProvider:
    def __init__(self, error: WeatherProviderError) -> None:
        self.name = "mock"
        self._error = error

    def fetch(self, latitude: float, longitude: float) -> WeatherSnapshot:
        raise self._error


def test_first_attempt_failure_is_explicit_not_fabricated(
    db_session: Session, monkeypatch: Any
) -> None:
    settings = make_settings(weather_enabled=False, weather_provider="mock")
    client = _client(db_session, settings)
    citizen = _profile(db_session, name="Reporter")
    incident_id = _report(client, citizen)
    settings.weather_enabled = True

    monkeypatch.setattr(
        "app.weather.service.build_provider",
        lambda _settings: FailingProvider(
            WeatherProviderError("malformed_response", "bad provider payload")
        ),
    )
    response = client.get(
        f"/api/v1/weather/incidents/{incident_id}/assessment", headers=_auth(citizen)
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ERROR"
    assert body["error_code"] == "malformed_response"
    assert body["weather_snapshot"] == {}
    assert body["assessment"]["signals"] == []
    assert "No weather data was retrieved" in body["assessment"]["uncertainty"]


def test_disabled_environment_has_explicit_fallback(
    db_session: Session, monkeypatch: Any
) -> None:
    settings = make_settings(weather_enabled=False, weather_provider="mock")
    client = _client(db_session, settings)
    citizen = _profile(db_session, name="Reporter")
    incident_id = _report(client, citizen)

    def _unexpected(_settings: Settings):
        raise AssertionError("provider must not be built when weather is disabled")

    monkeypatch.setattr("app.weather.service.build_provider", _unexpected)
    response = client.get(
        f"/api/v1/weather/incidents/{incident_id}/assessment", headers=_auth(citizen)
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "DISABLED"
    assert body["weather_snapshot"] == {}
    assert "disabled" in body["assessment"]["explanation"]


def test_other_citizen_cannot_read_assessment(db_session: Session) -> None:
    settings = make_settings(weather_enabled=False, weather_provider="mock")
    client = _client(db_session, settings)
    reporter = _profile(db_session, name="Reporter")
    stranger = _profile(db_session, name="Stranger")
    incident_id = _report(client, reporter)
    response = client.get(
        f"/api/v1/weather/incidents/{incident_id}/assessment", headers=_auth(stranger)
    )
    assert response.status_code == 404
