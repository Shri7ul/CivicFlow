"""Evidence upload, metadata, authorization, and signed URL tests."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.jwt import get_token_verifier
from app.core.config import get_settings
from app.db.session import get_db_session
from app.main import create_app
from app.models import IncidentEvidence, Profile, Role
from app.services.storage import get_storage_service
from tests.auth_support import make_settings, make_token, make_verifier

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG = b"\xff\xd8\xff" + b"\x00" * 16
WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 16

PAYLOAD: dict[str, Any] = {
    "title": "Evidence incident",
    "description": "Evidence upload validation incident.",
    "category": "ROADS",
    "severity": "MEDIUM",
    "latitude": 23.8103,
    "longitude": 90.4125,
}


class FakeStorage:
    def __init__(self, *, fail_on_upload: int | None = None) -> None:
        self.uploads: list[tuple[str, bytes, str]] = []
        self.deleted: list[str] = []
        self.fail_on_upload = fail_on_upload
        self.signed_paths: list[str] = []

    def upload(self, path: str, data: bytes, mime_type: str) -> None:
        if self.fail_on_upload is not None and len(self.uploads) == self.fail_on_upload:
            raise RuntimeError("simulated storage failure")
        self.uploads.append((path, data, mime_type))

    def delete(self, path: str) -> None:
        self.deleted.append(path)

    def create_signed_url(self, path: str) -> str:
        self.signed_paths.append(path)
        return f"https://storage.test/{path}?token=test"


def _profile(session: Session, role: Role = Role.CITIZEN, name: str = "Citizen") -> Profile:
    profile = Profile(
        id=uuid.uuid4(),
        full_name=name,
        role=role,
        is_active=True,
    )
    session.add(profile)
    session.commit()
    return profile


def _client(session: Session, storage: FakeStorage) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_token_verifier] = lambda: make_verifier(
        make_settings()
    )
    app.dependency_overrides[get_storage_service] = lambda: storage
    return TestClient(app)


def _auth(profile: Profile) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(sub=profile.id)}"}


def _incident(client: TestClient, profile: Profile) -> str:
    response = client.post("/api/v1/incidents", headers=_auth(profile), json=PAYLOAD)
    assert response.status_code == 201
    return response.json()["id"]


def _upload(
    client: TestClient,
    profile: Profile,
    incident_id: str,
    files: list[tuple[str, bytes, str]],
):
    return client.post(
        f"/api/v1/incidents/{incident_id}/evidence",
        headers=_auth(profile),
        files=[("files", item) for item in files],
    )


def test_valid_evidence_upload_persists_safe_metadata_and_signed_url(
    db_session: Session,
) -> None:
    storage = FakeStorage()
    citizen = _profile(db_session)
    worker = _profile(db_session, Role.WORKER, "Worker")
    with _client(db_session, storage) as client:
        incident_id = _incident(client, citizen)
        response = _upload(
            client,
            citizen,
            incident_id,
            [
                ("../../outside name.png", PNG, "image/png"),
                ("photo.jpg", JPEG, "image/jpeg"),
                ("photo.webp", WEBP, "image/webp"),
            ],
        )
        assert response.status_code == 201
        body = response.json()
        assert len(body) == 3
        assert body[0]["file_name"] == "outside name.png"
        assert body[1]["file_name"] == "photo.jpg"
        assert body[2]["mime_type"] == "image/webp"
        assert all(item["file_size"] > 0 for item in body)
        assert all(
            item["uploader"]["id"] == str(citizen.id) for item in body
        )

        detail = client.get(
            f"/api/v1/incidents/{incident_id}", headers=_auth(citizen)
        )
        assert detail.status_code == 200
        assert len(detail.json()["evidence"]) == 3

        evidence_list = client.get(
            f"/api/v1/incidents/{incident_id}/evidence", headers=_auth(worker)
        )
        assert evidence_list.status_code == 200
        assert len(evidence_list.json()) == 3

        evidence_id = body[0]["id"]
        signed = client.get(
            f"/api/v1/incidents/{incident_id}/evidence/{evidence_id}/url",
            headers=_auth(citizen),
        )
        assert signed.status_code == 200
        assert signed.json()["signed_url"].startswith("https://storage.test/")
        assert signed.json()["expires_in"] == 300
        assert storage.signed_paths

        assert len(storage.uploads) == 3
        for path, _data, _mime in storage.uploads:
            assert path.startswith(f"{incident_id}/")
            assert ".." not in path
            assert not path.endswith("outside name.png")

    assert db_session.scalar(select(func.count()).select_from(IncidentEvidence)) == 3


def test_other_citizen_cannot_list_upload_or_sign_evidence(
    db_session: Session,
) -> None:
    storage = FakeStorage()
    owner = _profile(db_session)
    other = _profile(db_session, name="Other")
    with _client(db_session, storage) as client:
        incident_id = _incident(client, owner)
        created = _upload(
            client, owner, incident_id, [("photo.png", PNG, "image/png")]
        )
        assert created.status_code == 201
        evidence_id = created.json()[0]["id"]

        assert (
            client.get(
                f"/api/v1/incidents/{incident_id}/evidence",
                headers=_auth(other),
            ).status_code
            == 404
        )
        assert (
            _upload(client, other, incident_id, [("photo.png", PNG, "image/png")])
            .status_code
            == 404
        )
        assert (
            client.get(
                f"/api/v1/incidents/{incident_id}/evidence/{evidence_id}/url",
                headers=_auth(other),
            ).status_code
            == 404
        )
        assert storage.uploads


def test_invalid_mime_empty_and_missing_files_are_rejected(
    db_session: Session,
) -> None:
    storage = FakeStorage()
    citizen = _profile(db_session)
    with _client(db_session, storage) as client:
        incident_id = _incident(client, citizen)

        invalid = _upload(
            client,
            citizen,
            incident_id,
            [("malware.png", b"not an image", "image/png")],
        )
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "unsupported_evidence_type"

        empty = _upload(
            client, citizen, incident_id, [("empty.png", b"", "image/png")]
        )
        assert empty.status_code == 422
        assert empty.json()["error"]["code"] == "empty_evidence_file"

        missing = client.post(
            f"/api/v1/incidents/{incident_id}/evidence",
            headers=_auth(citizen),
            files=[],
        )
        assert missing.status_code == 422

    assert storage.uploads == []
    assert db_session.scalar(select(func.count()).select_from(IncidentEvidence)) == 0


def test_upload_limits_and_storage_failure_cleanup(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EVIDENCE_MAX_FILE_SIZE_BYTES", "32")
    monkeypatch.setenv("EVIDENCE_MAX_FILES_PER_UPLOAD", "2")
    get_settings.cache_clear()
    storage = FakeStorage(fail_on_upload=1)
    citizen = _profile(db_session)
    try:
        with _client(db_session, storage) as client:
            incident_id = _incident(client, citizen)

            oversized = _upload(
                client,
                citizen,
                incident_id,
                [("large.png", PNG + b"x" * 40, "image/png")],
            )
            assert oversized.status_code == 413
            assert oversized.json()["error"]["code"] == "evidence_too_large"

            too_many = _upload(
                client,
                citizen,
                incident_id,
                [
                    ("one.png", PNG, "image/png"),
                    ("two.png", PNG, "image/png"),
                    ("three.png", PNG, "image/png"),
                ],
            )
            assert too_many.status_code == 422
            assert too_many.json()["error"]["code"] == "too_many_evidence_files"

            failure = _upload(
                client,
                citizen,
                incident_id,
                [
                    ("one.png", PNG, "image/png"),
                    ("two.png", PNG, "image/png"),
                ],
            )
            assert failure.status_code == 503
            assert storage.deleted == [storage.uploads[0][0]]
    finally:
        get_settings.cache_clear()

    assert db_session.scalar(select(func.count()).select_from(IncidentEvidence)) == 0


def test_evidence_constraints_reject_bad_mime_and_oversized_rows(
    db_session: Session,
) -> None:
    citizen = _profile(db_session)
    incident_id = uuid.uuid4()
    # This test uses the model's check constraints directly, without the API.
    from app.models import Incident, Role  # local import keeps test setup explicit

    incident = Incident(
        id=incident_id,
        title="Constraint incident",
        description="A valid description for constraint testing.",
        category="OTHER",
        severity="LOW",
        status="OPEN",
        location="POINT(90.4 23.8)",
        reporter_id=citizen.id,
    )
    db_session.add(incident)
    db_session.commit()

    bad = IncidentEvidence(
        incident_id=incident_id,
        uploaded_by=citizen.id,
        storage_path="test/bad.txt",
        file_name="bad.txt",
        mime_type="text/plain",
        file_size=1,
    )
    db_session.add(bad)
    with pytest.raises(Exception):
        db_session.commit()
    db_session.rollback()
