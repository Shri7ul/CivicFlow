"""Phase 11 evidence, ground-truth, correlation and authorization tests.

All data here is deterministic synthetic test data. It is not operational
evidence and is explicitly labelled so in assertions.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone

import pytest

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_token_verifier
from app.db.session import get_db_session
from app.evidence.snapshots import verify_snapshot
from app.governance.errors import GovernanceError
from app.main import create_app
from app.models import (
    CorrelationUniverse,
    EvidenceQualityStatus,
    EvidenceSnapshot,
    EvidenceSnapshotKind,
    EvidenceSnapshotStatus,
    GroundTruthRecord,
    GroundTruthStatus,
    Profile,
    ProvenanceKind,
    Role,
    SnapshotVerificationStatus,
)
from app.models.evidence import EvidenceSnapshotEvent
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
    return {
        "Authorization": "Bearer "
        + make_token(sub=profile.id, email=f"{profile.id}@example.com")
    }


def _snapshot(
    session: Session,
    *,
    key: str | None = None,
    raw: bytes = b'[{"latitude":40.7,"longitude":-73.9,"external_id":"A1"}]',
    records: list[dict] | None = None,
    tamper_normalized: bool = False,
    tamper_raw: bool = False,
) -> EvidenceSnapshot:
    records = records or [
        {"latitude": 40.7, "longitude": -73.9, "external_id": "A1"}
    ]
    normalized = json.dumps(
        records, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    raw_hash = hashlib.sha256(raw).hexdigest()
    normalized_hash = hashlib.sha256(normalized).hexdigest()
    snapshot = EvidenceSnapshot(
        snapshot_key=key or f"test-snapshot-{uuid.uuid4().hex[:10]}",
        kind=EvidenceSnapshotKind.RESEARCH_DATASET,
        provenance_kind=ProvenanceKind.SYNTHETIC,
        status=EvidenceSnapshotStatus.VALIDATED,
        source_key=f"synthetic-test-source-{uuid.uuid4().hex[:8]}",
        source_url="https://example.invalid/synthetic-test",
        provider="SYNTHETIC TEST FIXTURE",
        license_note="Synthetic fixture; no operational license claim.",
        dataset_version="fixture-v1",
        retrieved_at=datetime.now(timezone.utc),
        snapshot_sha256=("0" * 64 if tamper_normalized else normalized_hash),
        raw_sha256=("0" * 64 if tamper_raw else raw_hash),
        schema_version="fixture-v1",
        record_count=len(records),
        raw_record_count=len(records),
        byte_size=len(normalized),
        crs="EPSG:4326",
        bbox=[-73.9, 40.7, -73.9, 40.7],
        data_period_start=datetime(2026, 7, 1, tzinfo=timezone.utc),
        data_period_end=datetime(2026, 9, 30, tzinfo=timezone.utc),
        geographic_coverage="Synthetic test bbox only",
        quality_status=EvidenceQualityStatus.PASS,
        quality_checks=[{"check": "synthetic", "status": "PASS", "detail": "fixture"}],
        lineage={"fixture": True, "provenance": "SYNTHETIC"},
        verification_status=SnapshotVerificationStatus.PENDING,
        is_current=True,
        raw_content=raw,
        normalized_content=normalized,
    )
    session.add(snapshot)
    session.commit()
    return snapshot


def _gt_payload(reference: str = "SYNTH-REF-1") -> dict:
    return {
        "source_type": "HUMAN_OBSERVATION",
        "source_name": "Synthetic test observation",
        "source_reference": reference,
        "incident_type": "DRAINAGE",
        "description": "Synthetic fixture observation for workflow tests.",
        "uncertainty": 0.2,
        "latitude": 40.7,
        "longitude": -73.9,
        "sensitive": True,
        "evidence_refs": ["fixture://photo/1"],
        "notes": "SYNTHETIC test fixture; not an operational incident.",
    }


def test_workspace_requires_staff_and_exposes_empty_metrics(db_session: Session) -> None:
    worker = _profile(db_session, Role.WORKER, "Worker")
    citizen = _profile(db_session, Role.CITIZEN, "Citizen")
    client = _client(db_session)

    assert client.get("/api/v1/governance/evidence/workspace").status_code == 401
    assert (
        client.get(
            "/api/v1/governance/evidence/workspace", headers=_auth(citizen)
        ).status_code
        == 403
    )
    response = client.get(
        "/api/v1/governance/evidence/workspace", headers=_auth(worker)
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ground_truth"]["verified_count"] == 0
    assert body["ground_truth"]["status_counts"]["VERIFIED"] == 0
    assert body["correlation"]["recall_available"] is False
    assert body["correlation"]["true_negatives_available"] is False
    assert body["external_validation"]["results"] == []
    assert any("human-verified" in item for item in body["blockers"])
    assert body["infrastructure"]["coverage_context"]["status"] == "NOT_ASSESSED"
    assert "raw_content" not in json.dumps(body)


def test_snapshot_detail_never_returns_raw_bytes(db_session: Session) -> None:
    worker = _profile(db_session, Role.WORKER, "Worker")
    snapshot = _snapshot(db_session)
    client = _client(db_session)

    response = client.get(
        f"/api/v1/governance/evidence/snapshots/{snapshot.id}",
        headers=_auth(worker),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["snapshot_sha256"] == snapshot.snapshot_sha256
    assert body["provenance"] == "SYNTHETIC"
    assert body["provenance_kind"] == "SYNTHETIC"
    assert body["readiness"] == "NOT_OPERATIONAL_EVIDENCE"
    assert "raw_content" not in body
    assert "normalized_content" not in body

    missing = client.get(
        f"/api/v1/governance/evidence/snapshots/{uuid.uuid4()}",
        headers=_auth(worker),
    )
    assert missing.status_code == 404


def test_snapshot_recomputation_and_tamper_detection(db_session: Session) -> None:
    admin = _profile(db_session, Role.ADMIN, "Admin")
    worker = _profile(db_session, Role.WORKER, "Worker")
    snapshot = _snapshot(db_session)
    client = _client(db_session)

    denied = client.post(
        f"/api/v1/governance/evidence/snapshots/{snapshot.id}/verify",
        json={"note": "synthetic check"},
        headers=_auth(worker),
    )
    assert denied.status_code == 403

    ok = client.post(
        f"/api/v1/governance/evidence/snapshots/{snapshot.id}/verify",
        json={"note": "independent synthetic recomputation"},
        headers=_auth(admin),
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["snapshot"]["verification_status"] == "AUTOMATED_RECOMPUTATION"
    events = db_session.scalars(
        select(EvidenceSnapshotEvent).where(
            EvidenceSnapshotEvent.snapshot_id == snapshot.id
        )
    ).all()
    assert [item.action for item in events] == ["AUTOMATED_RECOMPUTATION"]

    tampered = _snapshot(db_session, tamper_raw=True)
    actor = type(
        "Actor",
        (),
        {"profile": admin, "email": None, "subject": admin.id},
    )()
    with pytest.raises(GovernanceError) as error:
        verify_snapshot(db_session, tampered, actor)
    assert error.value.code == "snapshot_verification_failed"
    db_session.refresh(tampered)
    assert tampered.verification_status == SnapshotVerificationStatus.FAILED
    failed = [
        item for item in tampered.verification_checks if item["status"] == "FAIL"
    ]
    assert failed
    assert failed[0]["check"] == "raw_sha256_recomputed"


def test_ground_truth_requires_separate_reviewer_and_evidence(
    db_session: Session,
) -> None:
    creator = _profile(db_session, Role.WORKER, "Creator")
    reviewer = _profile(db_session, Role.WORKER, "Reviewer")
    client = _client(db_session)

    created = client.post(
        "/api/v1/governance/evidence/ground-truth",
        json=_gt_payload(),
        headers=_auth(creator),
    )
    assert created.status_code == 201, created.text
    record = created.json()
    assert record["status"] == "UNVERIFIED"
    assert record["provenance_kind"] == "OPERATIONAL"
    assert record["verified_by"] is None
    assert "actor_email" not in json.dumps(record)

    submitted = client.post(
        f"/api/v1/governance/evidence/ground-truth/{record['id']}/submit",
        json={"note": "Please review.", "evidence_refs": []},
        headers=_auth(creator),
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "IN_REVIEW"

    self_review = client.post(
        f"/api/v1/governance/evidence/ground-truth/{record['id']}/review",
        json={
            "decision": "VERIFIED",
            "verification_method": "field visit",
            "note": "Self verification must be rejected.",
            "evidence_refs": ["fixture://field/1"],
        },
        headers=_auth(creator),
    )
    assert self_review.status_code == 403

    no_evidence = client.post(
        f"/api/v1/governance/evidence/ground-truth/{record['id']}/review",
        json={
            "decision": "VERIFIED",
            "verification_method": "field visit",
            "note": "No evidence should fail.",
            "evidence_refs": [],
        },
        headers=_auth(reviewer),
    )
    assert no_evidence.status_code == 422

    verified = client.post(
        f"/api/v1/governance/evidence/ground-truth/{record['id']}/review",
        json={
            "decision": "VERIFIED",
            "verification_method": "independent field visit",
            "note": "Verified against an independent synthetic fixture.",
            "evidence_refs": ["fixture://field/1"],
        },
        headers=_auth(reviewer),
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["status"] == "VERIFIED"
    assert verified.json()["verified_by"] == str(reviewer.id)

    detail = client.get(
        f"/api/v1/governance/evidence/ground-truth/{record['id']}",
        headers=_auth(creator),
    )
    assert detail.status_code == 200
    body = detail.json()
    assert body["record"]["description"] == _gt_payload()["description"]
    assert [item["action"] for item in body["events"]] == [
        "CREATED",
        "SUBMITTED_FOR_REVIEW",
        "VERIFICATION_DECISION",
    ]
    assert "actor_email" not in json.dumps(body)
    assert "SYNTHETIC" not in body["record"]["provenance_kind"]

    repeat = client.post(
        f"/api/v1/governance/evidence/ground-truth/{record['id']}/review",
        json={
            "decision": "REJECTED",
            "verification_method": "field visit",
            "note": "Second decision must be rejected.",
            "evidence_refs": ["fixture://field/2"],
        },
        headers=_auth(reviewer),
    )
    assert repeat.status_code == 409


def test_rejected_ground_truth_is_reviewed_but_not_verified(
    db_session: Session,
) -> None:
    creator = _profile(db_session, Role.WORKER, "Creator")
    reviewer = _profile(db_session, Role.WORKER, "Reviewer")
    client = _client(db_session)
    created = client.post(
        "/api/v1/governance/evidence/ground-truth",
        json=_gt_payload("SYNTH-REJECTED-1"),
        headers=_auth(creator),
    )
    assert created.status_code == 201, created.text
    record = created.json()
    submitted = client.post(
        f"/api/v1/governance/evidence/ground-truth/{record['id']}/submit",
        json={"note": "Review this assertion.", "evidence_refs": []},
        headers=_auth(creator),
    )
    assert submitted.status_code == 200, submitted.text
    rejected = client.post(
        f"/api/v1/governance/evidence/ground-truth/{record['id']}/review",
        json={
            "decision": "REJECTED",
            "verification_method": "independent desk review",
            "note": "Synthetic evidence does not support verification.",
            "evidence_refs": ["fixture://review/1"],
        },
        headers=_auth(reviewer),
    )
    assert rejected.status_code == 200, rejected.text
    body = rejected.json()
    assert body["status"] == "REJECTED"
    assert body["review_status"] == "REVIEWED_NOT_VERIFIED"
    assert body["verified_by"] == str(reviewer.id)
    assert body["description"] == _gt_payload("SYNTH-REJECTED-1")["description"]


def test_ground_truth_rejects_spoofed_fields(db_session: Session) -> None:
    worker = _profile(db_session, Role.WORKER, "Worker")
    client = _client(db_session)
    payload = _gt_payload("SYNTH-REF-SPOOF")
    payload.update(
        {
            "status": "VERIFIED",
            "verified_by": str(worker.id),
            "provenance_kind": "SYNTHETIC",
        }
    )
    response = client.post(
        "/api/v1/governance/evidence/ground-truth",
        json=payload,
        headers=_auth(worker),
    )
    assert response.status_code == 422

    lon_only = _gt_payload("SYNTH-REF-LON")
    del lon_only["latitude"]
    response = client.post(
        "/api/v1/governance/evidence/ground-truth",
        json=lon_only,
        headers=_auth(worker),
    )
    assert response.status_code == 422


def test_phase11_rejects_traversal_oversize_and_keeps_sql_literal(
    db_session: Session,
) -> None:
    admin = _profile(db_session, Role.ADMIN, "Admin")
    worker = _profile(db_session, Role.WORKER, "Worker")
    client = _client(db_session)

    traversal = client.post(
        "/api/v1/governance/evidence/acquire",
        json={"source_key": "../../etc/passwd"},
        headers=_auth(admin),
    )
    assert traversal.status_code == 422
    bad_id = client.get(
        "/api/v1/governance/evidence/snapshots/..%2F..%2Fetc%2Fpasswd",
        headers=_auth(worker),
    )
    assert bad_id.status_code in {404, 422}

    oversized = _gt_payload("SYNTH-OVERSIZE")
    oversized["description"] = "x" * 4001
    response = client.post(
        "/api/v1/governance/evidence/ground-truth",
        json=oversized,
        headers=_auth(worker),
    )
    assert response.status_code == 422

    literal = _gt_payload("SYNTH-SQL-LITERAL")
    literal["description"] = "x'); DROP TABLE ground_truth_records; -- synthetic literal"
    created = client.post(
        "/api/v1/governance/evidence/ground-truth",
        json=literal,
        headers=_auth(worker),
    )
    assert created.status_code == 201, created.text
    assert created.json()["description"] == literal["description"]
    listed = client.get(
        "/api/v1/governance/evidence/ground-truth",
        headers=_auth(worker),
    )
    assert listed.status_code == 200
    assert any(
        item["description"] == literal["description"]
        for item in listed.json()["items"]
    )
    record = db_session.scalar(
        select(GroundTruthRecord).where(
            GroundTruthRecord.description == literal["description"]
        )
    )
    assert record is not None


def test_correlation_universe_immutable_and_provenance_checked(
    db_session: Session,
) -> None:
    admin = _profile(db_session, Role.ADMIN, "Admin")
    worker = _profile(db_session, Role.WORKER, "Worker")
    client = _client(db_session)

    base = {
        "universe_key": f"fixture-universe-{uuid.uuid4().hex[:8]}",
        "name": "Synthetic reference universe",
        "description": "SYNTHETIC fixture universe; not operational labels.",
        "version": "v1",
        "provenance_kind": "SYNTHETIC",
        "reference_complete": False,
        "reference_size": None,
        "candidate_method": "synthetic_pairing",
        "candidate_method_version": "v1",
    }
    denied = client.post(
        "/api/v1/governance/evidence/correlation/universes",
        json=base,
        headers=_auth(worker),
    )
    assert denied.status_code == 403

    created = client.post(
        "/api/v1/governance/evidence/correlation/universes",
        json=base,
        headers=_auth(admin),
    )
    assert created.status_code == 201, created.text
    assert created.json()["reference_complete"] is False
    assert created.json()["immutable"] is True

    duplicate = client.post(
        "/api/v1/governance/evidence/correlation/universes",
        json=base,
        headers=_auth(admin),
    )
    assert duplicate.status_code == 409

    mixed = dict(base)
    mixed["universe_key"] = f"fixture-mixed-{uuid.uuid4().hex[:8]}"
    mixed["provenance_kind"] = "MIXED"
    response = client.post(
        "/api/v1/governance/evidence/correlation/universes",
        json=mixed,
        headers=_auth(admin),
    )
    assert response.status_code == 422

    incomplete = dict(base)
    incomplete["universe_key"] = f"fixture-incomplete-{uuid.uuid4().hex[:8]}"
    incomplete["reference_complete"] = True
    response = client.post(
        "/api/v1/governance/evidence/correlation/universes",
        json=incomplete,
        headers=_auth(admin),
    )
    assert response.status_code == 422


def test_acquisition_is_allowlisted_and_admin_only(db_session: Session) -> None:
    admin = _profile(db_session, Role.ADMIN, "Admin")
    worker = _profile(db_session, Role.WORKER, "Worker")
    client = _client(db_session)

    denied = client.post(
        "/api/v1/governance/evidence/acquire",
        json={"source_key": "nyc-dot-bridge-ratings"},
        headers=_auth(worker),
    )
    assert denied.status_code == 403

    arbitrary = client.post(
        "/api/v1/governance/evidence/acquire",
        json={
            "source_key": "nyc-dot-bridge-ratings",
            "url": "http://169.254.169.254/latest/meta-data",
        },
        headers=_auth(admin),
    )
    assert arbitrary.status_code == 422

    unknown = client.post(
        "/api/v1/governance/evidence/acquire",
        json={"source_key": "not-an-allowlisted-source"},
        headers=_auth(admin),
    )
    assert unknown.status_code == 404


def test_ground_truth_synthetic_fixture_is_not_operational(
    db_session: Session,
) -> None:
    record = GroundTruthRecord(
        record_key="gt-synthetic-test",
        source_type="HUMAN_OBSERVATION",
        provenance_kind=ProvenanceKind.SYNTHETIC,
        source_name="Synthetic fixture",
        source_reference="SYNTHETIC-ONLY-1",
        incident_type="DRAINAGE",
        description="SYNTHETIC fixture; never operational evidence.",
        status=GroundTruthStatus.UNVERIFIED,
    )
    db_session.add(record)
    db_session.commit()
    stored = db_session.scalar(
        select(GroundTruthRecord).where(GroundTruthRecord.id == record.id)
    )
    assert stored is not None
    assert stored.provenance_kind.value == "SYNTHETIC"
    assert db_session.scalars(select(CorrelationUniverse)).all() == []
