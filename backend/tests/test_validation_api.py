"""Validation workspace RBAC and API tests."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.jwt import get_token_verifier
from app.db.session import get_db_session
from app.main import create_app
from app.models import Profile, Role
from tests.auth_support import make_settings, make_token, make_verifier


def _profile(session: Session, role: Role, name: str) -> Profile:
    profile = Profile(id=uuid.uuid4(), full_name=name, role=role, is_active=True)
    session.add(profile)
    session.commit()
    return profile


def _client(session: Session) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_token_verifier] = lambda: make_verifier(
        make_settings()
    )
    return TestClient(app)


def _auth(profile: Profile) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(sub=profile.id)}"}


def test_validation_rbac_and_dataset_registration(db_session: Session) -> None:
    admin = _profile(db_session, Role.ADMIN, "Admin")
    worker = _profile(db_session, Role.WORKER, "Worker")
    citizen = _profile(db_session, Role.CITIZEN, "Citizen")
    with _client(db_session) as client:
        assert client.get("/api/v1/validation/overview").status_code == 401
        assert client.get(
            "/api/v1/validation/overview", headers=_auth(citizen)
        ).status_code == 403
        assert client.get(
            "/api/v1/validation/overview", headers=_auth(worker)
        ).status_code == 200
        payload = {
            "dataset_key": "fixture-api",
            "name": "Fixture API dataset",
            "source_url": "https://example.invalid/data",
            "license_note": "fixture only",
            "region": "fixture",
            "snapshot_sha256": "a" * 64,
            "record_count": 2,
            "schema_version": "fixture-v1",
        }
        assert client.post(
            "/api/v1/validation/datasets", headers=_auth(worker), json=payload
        ).status_code == 403
        created = client.post(
            "/api/v1/validation/datasets", headers=_auth(admin), json=payload
        )
        assert created.status_code == 201, created.text
        dataset = created.json()
        assert dataset["status"] == "INSUFFICIENT"
        same = client.post(
            "/api/v1/validation/datasets", headers=_auth(admin), json=payload
        )
        assert same.status_code == 201
        assert same.json()["id"] == dataset["id"]
        changed = {**payload, "snapshot_sha256": "b" * 64}
        conflict = client.post(
            "/api/v1/validation/datasets", headers=_auth(admin), json=changed
        )
        assert conflict.status_code == 409
        assert client.post(
            "/api/v1/validation/datasets",
            headers=_auth(admin),
            json={**payload, "dataset_key": "unsafe-url", "source_url": "javascript:alert(1)"},
        ).status_code == 422
        assert client.post(
            "/api/v1/validation/datasets",
            headers=_auth(admin),
            json={**payload, "dataset_key": "short-hash", "snapshot_sha256": "abc"},
        ).status_code == 422
        overview = client.get(
            "/api/v1/validation/overview", headers=_auth(worker)
        ).json()
        assert overview["datasets"][0]["dataset_key"] == "fixture-api"
        assert len(overview["datasets"]) == 1
        assert "EMPIRICAL_OBSERVATIONAL" in overview["evidence_kinds"]
        assert any("not verified hazard" in text for text in overview["limitations"])
        listed = client.get(
            "/api/v1/validation/datasets", headers=_auth(worker)
        )
        assert listed.status_code == 200
        detail = client.get(
            f"/api/v1/validation/datasets/{dataset['id']}", headers=_auth(worker)
        )
        assert detail.status_code == 200
        assert client.get(
            f"/api/v1/validation/datasets/{uuid.uuid4()}", headers=_auth(worker)
        ).status_code == 404
        # A registered metadata-only dataset cannot silently invent records.
        missing = client.post(
            f"/api/v1/validation/experiments/risk/{dataset['id']}",
            headers=_auth(worker),
        )
        assert missing.status_code == 422
        assert missing.json()["error"]["code"] == "dataset_records_unavailable"


def test_synthetic_experiment_endpoints_and_reports(db_session: Session) -> None:
    admin = _profile(db_session, Role.ADMIN, "Admin")
    with _client(db_session) as client:
        correlation = client.post(
            "/api/v1/validation/experiments/correlation", headers=_auth(admin)
        )
        assert correlation.status_code == 200, correlation.text
        payload = correlation.json()
        assert payload["evidence_kind"] == "SYNTHETIC_FIXTURE"
        assert payload["status"] == "COMPLETED"
        assert payload["metrics"]["case_count"] == 8
        assert payload["metrics"]["precision"] is not None
        report = client.get(
            f"/api/v1/validation/experiments/{payload['id']}/report",
            headers=_auth(admin),
        )
        assert report.status_code == 200, report.text
        assert report.json()["experiment_key"] == payload["experiment_key"]
        assert report.json()["dataset"] is None
        assert report.json()["methodology"]["model_name"] == "intelligence"

        decision = client.post(
            "/api/v1/validation/experiments/decision", headers=_auth(admin)
        )
        assert decision.status_code == 200, decision.text
        assert decision.json()["evidence_kind"] == "SIMULATED_PLANNING"
        assert decision.json()["metrics"]["deterministic_schedule"] is True
        assert any(
            "No dispatch" in item for item in decision.json()["limitations"]
        )
        second = client.post(
            "/api/v1/validation/experiments/decision", headers=_auth(admin)
        )
        assert second.status_code == 200
        assert second.json()["id"] != decision.json()["id"]
        listed = client.get(
            "/api/v1/validation/experiments", headers=_auth(admin)
        )
        assert listed.status_code == 200
        assert len(listed.json()) == 3
        detailed = client.get(
            f"/api/v1/validation/experiments/{decision.json()['id']}",
            headers=_auth(admin),
        )
        assert detailed.status_code == 200
        assert detailed.json()["metrics"]
        assert client.get(
            f"/api/v1/validation/experiments/{uuid.uuid4()}",
            headers=_auth(admin),
        ).status_code == 404
