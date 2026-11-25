"""Regression tests for API contract defects found in the recovery audit.

These tests verify that documented request payloads and response schemas are
actually honoured by the application, rather than silently discarded or left
undeclared. No production data, migration or external service is involved.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.api.v1.endpoints.validation as validation_endpoint
from app.auth.dependencies import get_token_verifier
from app.db.session import get_db_session
from app.main import create_app
from app.models import Profile, Role
from app.models.phase14 import FieldObservationEvent
from app.validation.service import ValidationError
from tests.auth_support import make_settings, make_token, make_verifier


def _profile(session: Session, role: Role) -> Profile:
    profile = Profile(id=uuid.uuid4(), full_name=role.value.title(), role=role, is_active=True)
    session.add(profile)
    session.commit()
    return profile


def _client(session: Session) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_token_verifier] = lambda: make_verifier(make_settings())
    return TestClient(app)


def _auth(profile: Profile) -> dict[str, str]:
    return {
        "Authorization": "Bearer "
        + make_token(sub=profile.id, email=f"{profile.id}@example.com")
    }


def test_risk_cells_declares_response_schema() -> None:
    """The union return type must be declared so OpenAPI and validation work."""
    schema = create_app().openapi()
    operation = schema["paths"]["/api/v1/risk/cells"]["get"]
    content = operation["responses"]["200"]["content"]
    assert "application/json" in content
    assert content["application/json"]["schema"]


def test_observation_submit_note_is_persisted_in_history(db_session: Session) -> None:
    """A submitted note must reach the append-only event log, not be discarded."""
    observer = _profile(db_session, Role.WORKER)
    observation_payload = {
        "observed_at": "2026-11-26T00:00:00+00:00",
        "latitude": 23.79,
        "longitude": 90.4,
        "category": "DRAINAGE",
        "description": "Structural test observation for note persistence.",
        "source_reference": f"recovery-{uuid.uuid4().hex[:10]}",
        "evidence_refs": ["evidence:recovery-test"],
        "evidence_sha256": "a" * 64,
        "confidence": 0.7,
    }
    with _client(db_session) as client:
        created = client.post(
            "/api/v1/governance/phase14/observations",
            json=observation_payload,
            headers=_auth(observer),
        )
        assert created.status_code == 201
        observation_id = created.json()["id"]
        submitted = client.post(
            f"/api/v1/governance/phase14/observations/{observation_id}/submit",
            json={"note": "Checked against municipal drain register."},
            headers=_auth(observer),
        )
        assert submitted.status_code == 200

    events = db_session.scalars(
        select(FieldObservationEvent).where(
            FieldObservationEvent.observation_id == uuid.UUID(observation_id)
        )
    ).all()
    submit_events = [event for event in events if event.action == "SUBMITTED"]
    assert len(submit_events) == 1
    assert submit_events[0].note == "Checked against municipal drain register."


def test_validation_correlation_error_is_structured_422(
    db_session: Session, monkeypatch: Any
) -> None:
    """Engine validation failures must not surface as unstructured 500s."""
    worker = _profile(db_session, Role.WORKER)

    def _raise(*_args: Any, **_kwargs: Any) -> None:
        raise ValidationError("No eligible dataset", code="dataset_unavailable")

    monkeypatch.setattr(validation_endpoint, "run_correlation_experiment", _raise)
    with _client(db_session) as client:
        response = client.post(
            "/api/v1/validation/experiments/correlation", headers=_auth(worker)
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "dataset_unavailable"


def test_validation_decision_error_is_structured_422(
    db_session: Session, monkeypatch: Any
) -> None:
    worker = _profile(db_session, Role.WORKER)

    def _raise(*_args: Any, **_kwargs: Any) -> None:
        raise ValidationError("Missing evidence", code="evidence_unavailable")

    monkeypatch.setattr(validation_endpoint, "run_decision_experiment", _raise)
    with _client(db_session) as client:
        response = client.post(
            "/api/v1/validation/experiments/decision", headers=_auth(worker)
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "evidence_unavailable"
