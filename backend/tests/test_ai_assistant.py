"""Civic AI assistant tests: Groq path, deterministic fallback and RBAC."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.auth.jwt import get_token_verifier
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.main import create_app
from app.models import Profile, Role
from app.services.ai import local_insights, suggest_triage
from tests.auth_support import make_settings, make_token, make_verifier

INCIDENT = {
    "title": "Blocked storm drain",
    "description": "Water pooling on the road after heavy rain.",
    "category": "DRAINAGE",
    "severity": "HIGH",
    "latitude": 23.8103,
    "longitude": 90.4125,
    "address": "Road 12, Dhanmondi",
}


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any] | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict[str, Any]:
        return self._payload


class FakeClient:
    status_code = 200
    payload: dict[str, Any] = {}

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def post(self, url: str, json: dict[str, Any], headers: dict[str, str]) -> FakeResponse:
        assert "/chat/completions" in url
        assert headers["Authorization"].startswith("Bearer ")
        return FakeResponse(self.status_code, self.payload)


def _profile(session: Session) -> Profile:
    profile = Profile(id=uuid.uuid4(), full_name="Citizen", role=Role.CITIZEN, is_active=True)
    session.add(profile)
    session.commit()
    return profile


def _client(session: Session, settings: Settings) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_token_verifier] = lambda: make_verifier(make_settings())
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def _auth(profile: Profile) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(sub=profile.id)}"}


def test_no_key_returns_labelled_deterministic_summary() -> None:
    result = local_insights([], make_settings())
    assert result["available"] is False
    assert result["source"] == "deterministic"
    assert result["summary"]
    assert "advisory only" in result["limitations"]
    assert result["model"] is None


def test_groq_response_is_used_when_key_is_configured(monkeypatch: Any) -> None:
    FakeClient.status_code = 200
    FakeClient.payload = {
        "choices": [{"message": {"content": "Your area looks calm today."}}]
    }
    monkeypatch.setattr("app.services.ai.httpx.Client", FakeClient)
    settings = make_settings(groq_api_key=SecretStr("test-key"))
    result = local_insights([], settings)
    assert result["available"] is True
    assert result["source"] == "groq"
    assert result["summary"] == "Your area looks calm today."


def test_groq_failure_falls_back_without_new_numbers(monkeypatch: Any) -> None:
    FakeClient.status_code = 500
    FakeClient.payload = {}
    monkeypatch.setattr("app.services.ai.httpx.Client", FakeClient)
    settings = make_settings(groq_api_key=SecretStr("test-key"))
    result = local_insights([], settings)
    assert result["available"] is False
    assert result["source"] == "deterministic"
    assert result["incident_count"] == 0


def test_triage_suggests_category_and_severity_from_text() -> None:
    settings = make_settings()
    result = suggest_triage("Collapsed bridge after flood", "Road closed", settings)
    assert result["suggested_category"] is not None
    assert result["suggested_severity"] is not None
    assert result["source"] == "deterministic"
    assert "advisory" in result["limitations"].lower()


def test_ai_api_uses_same_incident_visibility(db_session: Session) -> None:
    settings = make_settings()
    citizen = _profile(db_session)
    client = _client(db_session, settings)
    headers = _auth(citizen)

    created = client.post("/api/v1/incidents", json=INCIDENT, headers=headers)
    assert created.status_code == 201, created.text

    config = client.get("/api/v1/ai/config", headers=headers)
    assert config.status_code == 200
    assert config.json()["available"] is False

    insights = client.get("/api/v1/ai/insights", headers=headers)
    assert insights.status_code == 200, insights.text
    body = insights.json()
    assert body["source"] == "deterministic"
    assert body["incident_count"] == 1
    assert isinstance(body["highlights"], list)

    triage = client.post(
        "/api/v1/ai/triage",
        json={"title": "Broken drain", "description": "Flood on road"},
        headers=headers,
    )
    assert triage.status_code == 200, triage.text
    assert triage.json()["suggested_severity"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


def test_ai_endpoints_require_authentication(db_session: Session) -> None:
    client = _client(db_session, make_settings())
    assert client.get("/api/v1/ai/insights").status_code in {401, 403}
    assert client.get("/api/v1/ai/config").status_code in {401, 403}
