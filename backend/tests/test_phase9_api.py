"""Phase 9 research API RBAC, honesty, and bounded-input tests."""

from __future__ import annotations

import json
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


def test_research_endpoints_require_staff_authentication(db_session: Session) -> None:
    worker = _profile(db_session, Role.WORKER, "Worker")
    citizen = _profile(db_session, Role.CITIZEN, "Citizen")
    with _client(db_session) as client:
        for path in (
            "/api/v1/validation/research",
            "/api/v1/validation/research/report",
        ):
            assert client.get(path).status_code == 401
            assert client.get(path, headers=_auth(citizen)).status_code == 403
            assert client.get(path, headers=_auth(worker)).status_code == 200


def test_empty_research_state_is_reported_as_no_evidence(db_session: Session) -> None:
    worker = _profile(db_session, Role.WORKER, "Worker")
    with _client(db_session) as client:
        summary = client.get(
            "/api/v1/validation/research", headers=_auth(worker)
        ).json()
        assert summary["dataset_count"] == 0
        assert summary["datasets"] == []
        assert summary["selection"]["candidate_key"] is None
        assert summary["selection"]["selection_statistics"] is None
        assert summary["protocol_key"] == "phase9-risk-diagnosis-v1"
        assert summary["evidence_policy"]

        report = client.get(
            "/api/v1/validation/research/report", headers=_auth(worker)
        ).json()
        assert report["dataset_count"] == 0
        assert report["comparison"] == []
        assert report["model_changes"]["activated"] is False
        assert report["model_changes"]["activation_state"] == "NOT_ACTIVATED"
        assert report["executive_summary"] == [
            "No Phase 9 experiment records are persisted, so no finding is reported."
        ]
        # The empty report must not fabricate a metric or a dataset.
        assert report["datasets"] == []
        assert report["phase8_findings"] is None


def test_research_report_never_exposes_connection_material(
    db_session: Session,
) -> None:
    worker = _profile(db_session, Role.WORKER, "Worker")
    with _client(db_session) as client:
        response = client.get(
            "/api/v1/validation/research/report", headers=_auth(worker)
        )
    body = response.text.lower()
    assert response.status_code == 200
    for secret in ("postgres", "password", "secret_key", "supabase_service"):
        assert secret not in body


def test_research_run_is_admin_only_and_bounded(db_session: Session) -> None:
    admin = _profile(db_session, Role.ADMIN, "Admin")
    worker = _profile(db_session, Role.WORKER, "Worker")
    with _client(db_session) as client:
        assert client.post(
            "/api/v1/validation/research", headers=_auth(worker)
        ).status_code == 403
        missing = client.post(
            "/api/v1/validation/research?datasets=does-not-exist",
            headers=_auth(admin),
        )
        assert missing.status_code == 422
        assert missing.json()["error"]["code"] == "dataset_not_found"
        empty = client.post(
            "/api/v1/validation/research", headers=_auth(admin)
        )
        assert empty.status_code == 422
        assert empty.json()["error"]["code"] == "dataset_not_found"


def test_dataset_list_input_is_validated_before_any_run(db_session: Session) -> None:
    admin = _profile(db_session, Role.ADMIN, "Admin")
    with _client(db_session) as client:
        response = client.post(
            "/api/v1/validation/research?datasets=" + "a" * 200,
            headers=_auth(admin),
        )
        oversized = client.post(
            "/api/v1/validation/research?datasets=" + "a" * 201,
            headers=_auth(admin),
        )
        too_many = client.post(
            "/api/v1/validation/research?"
            + "&".join(f"datasets=key-{index}" for index in range(9)),
            headers=_auth(admin),
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "dataset_not_found"
    assert oversized.status_code == 422
    assert oversized.json()["error"]["code"] == "invalid_dataset_key"
    assert too_many.status_code == 422
    assert too_many.json()["error"]["code"] == "too_many_datasets"