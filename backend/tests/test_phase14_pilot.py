"""Phase 14 controlled-pilot controls, gates and adversarial tests.

All fixtures below are structural test data, never operational Dhaka evidence.
No test in this module claims a pilot, model or civic action was activated.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.governance.pilots as pilot_service
from app.auth.dependencies import get_token_verifier
from app.db.session import get_db_session
from app.main import create_app
from app.models import (
    GroundTruthRecord,
    GroundTruthStatus,
    GroundTruthSourceType,
    Pilot,
    PilotStatus,
    Profile,
    ProvenanceKind,
    Role,
)
from app.models.phase14 import (
    FieldObservation,
    Phase14Attestation,
    PilotBoundary,
    PilotIncident,
    PilotShutdown,
)
from app.phase14.readiness import assess_phase14_readiness
from tests.auth_support import make_settings, make_token, make_verifier

BASE = "/api/v1/governance/phase14"
BBOX = [90.390, 23.780, 90.410, 23.800]
RING = [
    [90.390, 23.780],
    [90.410, 23.780],
    [90.410, 23.800],
    [90.390, 23.800],
    [90.390, 23.780],
]


def _profile(session: Session, role: Role, name: str) -> Profile:
    profile = Profile(id=uuid.uuid4(), full_name=name, role=role, is_active=True)
    session.add(profile)
    session.commit()
    return profile


def _client(session: Session) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_token_verifier] = lambda: make_verifier(make_settings())
    return TestClient(app)


def _auth(profile: Profile) -> dict[str, str]:
    return {"Authorization": "Bearer " + make_token(sub=profile.id, email=f"{profile.id}@example.com")}


def _when(days: int = 1) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _pilot(session: Session, region: str = "Central Dhaka, Bangladesh") -> Pilot:
    pilot = Pilot(
        pilot_key=f"p14-{uuid.uuid4().hex[:10]}",
        name="Phase 14 bounded evaluation",
        description="Structural test pilot; no operational authorization.",
        status=PilotStatus.DRAFT,
        mode="SIMULATION",
        region=region,
        geographic_context_key="BD-DHAKA" if "Dhaka" in region else "UNKNOWN",
        bbox=BBOX,
        start_date=datetime.now(timezone.utc) + timedelta(days=-1),
        end_date=datetime.now(timezone.utc) + timedelta(days=30),
        eligible_categories=["DRAINAGE"],
        evaluation_protocol="Human-reviewed decision-support evaluation only.",
        operational_restrictions=["No dispatch", "No public alerts"],
        data_sources=["none"],
        evaluation_criteria=["Two reviewers"],
    )
    session.add(pilot)
    session.commit()
    return pilot


def _boundary_payload(key: str | None = None, **overrides) -> dict:
    payload = {
        "boundary_key": key or f"boundary-{uuid.uuid4().hex[:10]}",
        "name": "Candidate ward boundary",
        "description": "Structural test geometry.",
        "geographic_context_key": "BD-DHAKA",
        "source_type": "OFFICIAL_ADMINISTRATIVE",
        "source_owner": "Municipal authority",
        "source_name": "Ward register extract",
        "source_url": "https://example.org/boundary.geojson",
        "source_date": _when(-5),
        "boundary_version": "v1",
        "crs": "EPSG:4326",
        "geometry_geojson": {"type": "Polygon", "coordinates": [RING]},
        "bbox_geojson": BBOX,
        "provenance_note": "Registered for boundary verification workflow testing only.",
        "license_note": "Test licence reference.",
    }
    payload.update(overrides)
    return payload


def _observation_payload(**overrides) -> dict:
    payload = {
        "observed_at": _when(0),
        "latitude": 23.790,
        "longitude": 90.400,
        "category": "DRAINAGE",
        "description": "Standing water observed beside a drain inlet near the test cell.",
        "source_reference": f"ref-{uuid.uuid4().hex[:12]}",
        "evidence_refs": ["evidence:test-observation"],
        "evidence_sha256": "a" * 64,
        "confidence": 0.7,
    }
    payload.update(overrides)
    return payload


def _source_payload(key: str | None = None, **overrides) -> dict:
    payload = {
        "source_key": key or f"source-{uuid.uuid4().hex[:10]}",
        "geographic_context_key": "BD-DHAKA",
        "source_identity": "Municipal register",
        "source_owner": "Municipal authority",
        "dataset_name": "Test civic register",
        "dataset_description": "Structural test description of a hypothetical register.",
        "geographic_scope": "Central Dhaka test cell",
        "acquisition_method": "Authorized download",
        "endpoint": "https://example.org/dataset",
        "classification": "UNAUTHORIZED",
        "license_note": "Licence reference for testing.",
        "license_ref": "licence-test-001",
        "timestamp_note": "Snapshot timestamp recorded by the authority.",
        "update_frequency": "monthly",
        "data_quality_note": "Quality is documented but not asserted as complete.",
        "schema_version": "v1",
        "provenance_note": "Provenance documented for workflow testing.",
        "raw_sha256": "b" * 64,
        "normalized_sha256": "c" * 64,
        "coverage_note": "Coverage limited to the test cell.",
        "missing_data_note": "Missing categories are recorded as unknown.",
        "confidence_note": "Confidence is not asserted beyond source documentation.",
        "limitations": "No operational claim is made by this registration.",
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Final gate
# ---------------------------------------------------------------------------


def test_final_gate_defaults_to_not_ready_with_no_hardcoded_pass(db_session: Session) -> None:
    report = assess_phase14_readiness(db_session)
    assert report["protocol"] == "phase14-final-gate-v1"
    assert report["overall"] == "NOT_READY"
    assert report["ready_for_activation"] is False
    assert report["pilot_activation_authorized"] is False
    assert len(report["mandatory_unmet"]) >= 15
    assert all("PASS" not in item for item in report["mandatory_unmet"])
    assert any("Production infrastructure" in item for item in report["blockers"])


def test_final_gate_reflects_recorded_attestation_without_activation(db_session: Session) -> None:
    admin = _profile(db_session, Role.ADMIN, "Gate Admin")
    session = db_session
    attestation = Phase14Attestation(
        category="production_infrastructure",
        criterion_key="infrastructure.verified",
        status="PASS",
        evidence="Production infrastructure observed during an authorized review.",
        evidence_refs=["review:record-1"],
        blocking=True,
        assessed_by=admin.id,
        assessed_at=datetime.now(timezone.utc),
    )
    session.add(attestation)
    session.commit()
    report = assess_phase14_readiness(session)
    category = next(item for item in report["categories"] if item["key"] == "phase14_production_infrastructure")
    assert category["status"] == "PASS"
    assert report["ready_for_activation"] is False
    assert report["pilot_activation_authorized"] is False


def test_activation_is_blocked_by_phase14_gate_even_when_phase10_gate_passes(
    db_session: Session, monkeypatch
) -> None:
    creator = _profile(db_session, Role.ADMIN, "Creator")
    reviewer = _profile(db_session, Role.ADMIN, "Reviewer")
    activator = _profile(db_session, Role.ADMIN, "Activator")
    pilot = _pilot(db_session)
    with _client(db_session) as client:
        assert client.post(
            f"/api/v1/governance/pilots/{pilot.id}/reviewers",
            json={"profile_id": str(reviewer.id), "role": "REVIEWER"},
            headers=_auth(creator),
        ).status_code == 201
        assert client.post(
            f"/api/v1/governance/pilots/{pilot.id}/transition",
            json={"action": "SUBMIT"},
            headers=_auth(creator),
        ).status_code == 200
        assert client.post(
            f"/api/v1/governance/pilots/{pilot.id}/transition",
            json={"action": "APPROVE", "note": "Protocol reviewed by an independent admin."},
            headers=_auth(reviewer),
        ).status_code == 200
        monkeypatch.setattr(
            pilot_service,
            "assess_readiness",
            lambda session, pilot=None: {
                "overall": "READY_FOR_CONTROLLED_PILOT",
                "ready_for_activation": True,
                "activation_blockers": [],
            },
        )
        response = client.post(
            f"/api/v1/governance/pilots/{pilot.id}/transition",
            json={"action": "ACTIVATE", "ready": True},
            headers=_auth(activator),
        )
        assert response.status_code == 422  # client-supplied readiness cannot bypass
        response = client.post(
            f"/api/v1/governance/pilots/{pilot.id}/transition",
            json={"action": "ACTIVATE"},
            headers=_auth(activator),
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "phase14_readiness_not_met"
        assert db_session.get(Pilot, pilot.id).status == PilotStatus.APPROVED


def test_model_status_is_descriptive_and_not_operational(db_session: Session) -> None:
    worker = _profile(db_session, Role.WORKER, "Worker")
    with _client(db_session) as client:
        response = client.get(f"{BASE}/model-status", headers=_auth(worker))
        assert response.status_code == 200
        assert response.json()["readiness_level"] == "RESEARCH_ONLY"
        assert response.json()["operationally_available"] is False


# ---------------------------------------------------------------------------
# Boundary workflow
# ---------------------------------------------------------------------------


def test_boundary_registration_is_unverified_hashed_and_validated(db_session: Session) -> None:
    admin = _profile(db_session, Role.ADMIN, "Boundary Admin")
    with _client(db_session) as client:
        response = client.post(f"{BASE}/boundaries", json=_boundary_payload(), headers=_auth(admin))
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["status"] == "UNVERIFIED"
        assert len(data["integrity_sha256"]) == 64
        assert data["geometry_validation"]["valid"] is True
        assert data["coordinate_validation"]["valid"] is True
        assert "does not approve" in data["activation_note"]


def test_boundary_registration_rejects_invalid_geometry_and_context_mismatch(db_session: Session) -> None:
    admin = _profile(db_session, Role.ADMIN, "Boundary Admin")
    with _client(db_session) as client:
        bad_geometry = _boundary_payload(
            geometry_geojson={"type": "Polygon", "coordinates": [[[90.39, 23.78], [90.41, 23.78]]]},
        )
        bad = client.post(f"{BASE}/boundaries", json=bad_geometry, headers=_auth(admin))
        assert bad.status_code == 422
        assert bad.json()["error"]["code"] == "boundary_geometry_invalid"
        mismatch = client.post(
            f"{BASE}/boundaries",
            json=_boundary_payload(geographic_context_key="US-NYC"),
            headers=_auth(admin),
        )
        assert mismatch.status_code == 422
        assert mismatch.json()["error"]["code"] == "context_mismatch"


def test_boundary_requires_distinct_humans_for_verification_and_approval(db_session: Session) -> None:
    submitter = _profile(db_session, Role.ADMIN, "Submitter")
    verifier = _profile(db_session, Role.ADMIN, "Verifier")
    approver = _profile(db_session, Role.ADMIN, "Approver")
    with _client(db_session) as client:
        created = client.post(f"{BASE}/boundaries", json=_boundary_payload(), headers=_auth(submitter))
        boundary_id = created.json()["id"]
        assert client.post(
            f"{BASE}/boundaries/{boundary_id}/transition",
            json={"action": "APPROVE"},
            headers=_auth(approver),
        ).status_code == 409
        assert client.post(
            f"{BASE}/boundaries/{boundary_id}/transition",
            json={"action": "SUBMIT"},
            headers=_auth(submitter),
        ).status_code == 200
        self_verify = client.post(
            f"{BASE}/boundaries/{boundary_id}/transition",
            json={"action": "VERIFY", "note": "Verified the official ward register extract."},
            headers=_auth(submitter),
        )
        assert self_verify.status_code == 403
        assert self_verify.json()["error"]["code"] == "separation_of_duties"
        assert client.post(
            f"{BASE}/boundaries/{boundary_id}/transition",
            json={"action": "VERIFY", "note": "Verified the official ward register extract."},
            headers=_auth(verifier),
        ).status_code == 200
        approved = client.post(
            f"{BASE}/boundaries/{boundary_id}/transition",
            json={
                "action": "APPROVE",
                "note": "Approved for pilot preparation only.",
                "approval_reference": "approval-ref-001",
            },
            headers=_auth(approver),
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "APPROVED"
        events = approved.json()["events"]
        assert [event["action"] for event in events] == [
            "REGISTERED", "SUBMIT", "VERIFY", "APPROVE"
        ]


def test_research_boundary_cannot_be_approved(db_session: Session) -> None:
    submitter = _profile(db_session, Role.ADMIN, "Submitter")
    verifier = _profile(db_session, Role.ADMIN, "Verifier")
    approver = _profile(db_session, Role.ADMIN, "Approver")
    with _client(db_session) as client:
        created = client.post(
            f"{BASE}/boundaries",
            json=_boundary_payload(source_type="OSM_RESEARCH"),
            headers=_auth(submitter),
        )
        boundary_id = created.json()["id"]
        client.post(f"{BASE}/boundaries/{boundary_id}/transition", json={"action": "SUBMIT"}, headers=_auth(submitter))
        client.post(
            f"{BASE}/boundaries/{boundary_id}/transition",
            json={"action": "VERIFY", "note": "Research geometry checked for structure."},
            headers=_auth(verifier),
        )
        blocked = client.post(
            f"{BASE}/boundaries/{boundary_id}/transition",
            json={"action": "APPROVE", "note": "Attempted approval of research source.", "approval_reference": "ref"},
            headers=_auth(approver),
        )
        assert blocked.status_code == 422
        assert blocked.json()["error"]["code"] == "boundary_source_not_authoritative"


def test_worker_cannot_register_or_approve_boundary(db_session: Session) -> None:
    worker = _profile(db_session, Role.WORKER, "Worker")
    with _client(db_session) as client:
        assert client.post(f"{BASE}/boundaries", json=_boundary_payload(), headers=_auth(worker)).status_code == 403
        assert client.get(f"{BASE}/boundaries", headers=_auth(worker)).status_code == 200


# ---------------------------------------------------------------------------
# Field observations and ground truth
# ---------------------------------------------------------------------------


def test_observation_is_server_scoped_and_starts_draft(db_session: Session) -> None:
    observer = _profile(db_session, Role.WORKER, "Observer")
    pilot = _pilot(db_session)
    with _client(db_session) as client:
        response = client.post(
            f"{BASE}/observations",
            json=_observation_payload(pilot_id=str(pilot.id)),
            headers=_auth(observer),
        )
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["status"] == "DRAFT"
        assert data["geographic_context_key"] == "BD-DHAKA"
        assert data["observer_id"] == str(observer.id)
        assert data["ground_truth_record_id"] is None
        assert "A VERIFIED observation is a reviewed assertion" in data["ground_truth_note"]


def test_observation_rejects_unknown_context_and_duplicate_reference(db_session: Session) -> None:
    observer = _profile(db_session, Role.WORKER, "Observer")
    with _client(db_session) as client:
        outside = client.post(
            f"{BASE}/observations",
            json=_observation_payload(latitude=0.0, longitude=0.0, source_reference="outside-ref"),
            headers=_auth(observer),
        )
        assert outside.status_code == 422
        assert outside.json()["error"]["code"] == "unknown_geographic_context"
        nyc = client.post(
            f"{BASE}/observations",
            json=_observation_payload(latitude=40.72, longitude=-73.98, source_reference="nyc-ref"),
            headers=_auth(observer),
        )
        assert nyc.status_code == 201
        assert nyc.json()["geographic_context_key"] == "US-NYC"
        payload = _observation_payload()
        assert client.post(f"{BASE}/observations", json=payload, headers=_auth(observer)).status_code == 201
        duplicate = client.post(f"{BASE}/observations", json=payload, headers=_auth(observer))
        assert duplicate.status_code == 409
        assert duplicate.json()["error"]["code"] == "duplicate_observation"


def test_observation_review_requires_independence_and_evidence(db_session: Session) -> None:
    observer = _profile(db_session, Role.WORKER, "Observer")
    reviewer = _profile(db_session, Role.WORKER, "Reviewer")
    admin = _profile(db_session, Role.ADMIN, "Admin")
    with _client(db_session) as client:
        created = client.post(f"{BASE}/observations", json=_observation_payload(), headers=_auth(observer))
        oid = created.json()["id"]
        assert client.post(f"{BASE}/observations/{oid}/submit", json={}, headers=_auth(observer)).status_code == 200
        self_assign = client.post(
            f"{BASE}/observations/{oid}/assign-reviewer",
            json={"reviewer_id": str(observer.id)},
            headers=_auth(admin),
        )
        assert self_assign.status_code == 403
        assigned = client.post(
            f"{BASE}/observations/{oid}/assign-reviewer",
            json={"reviewer_id": str(reviewer.id)},
            headers=_auth(admin),
        )
        assert assigned.status_code == 200
        assert assigned.json()["status"] == "PENDING_REVIEW"
        bad_review = client.post(
            f"{BASE}/observations/{oid}/review",
            json={"decision": "REJECTED"},
            headers=_auth(reviewer),
        )
        assert bad_review.status_code == 422
        verified = client.post(
            f"{BASE}/observations/{oid}/review",
            json={"decision": "VERIFIED", "note": "Evidence checked against source record."},
            headers=_auth(reviewer),
        )
        assert verified.status_code == 200, verified.text
        assert verified.json()["status"] == "VERIFIED"
        assert verified.json()["ground_truth_record_id"] is None


def test_observation_revision_and_rejection_require_reasons(db_session: Session) -> None:
    observer = _profile(db_session, Role.WORKER, "Observer")
    reviewer = _profile(db_session, Role.WORKER, "Reviewer")
    admin = _profile(db_session, Role.ADMIN, "Admin")
    with _client(db_session) as client:
        first = client.post(f"{BASE}/observations", json=_observation_payload(), headers=_auth(observer)).json()
        oid = first["id"]
        client.post(f"{BASE}/observations/{oid}/submit", json={}, headers=_auth(observer))
        client.post(
            f"{BASE}/observations/{oid}/assign-reviewer",
            json={"reviewer_id": str(reviewer.id)},
            headers=_auth(admin),
        )
        revised = client.post(
            f"{BASE}/observations/{oid}/review",
            json={"decision": "REQUIRES_REVISION", "revision_notes": "Add the exact drain identifier."},
            headers=_auth(reviewer),
        )
        assert revised.status_code == 200
        assert revised.json()["revision"] == 2
        assert revised.json()["status"] == "REQUIRES_REVISION"


def test_ground_truth_promotion_is_explicit_and_distinct(db_session: Session) -> None:
    observer = _profile(db_session, Role.WORKER, "Observer")
    reviewer = _profile(db_session, Role.WORKER, "Reviewer")
    promoter = _profile(db_session, Role.ADMIN, "Promoter")
    with _client(db_session) as client:
        created = client.post(f"{BASE}/observations", json=_observation_payload(), headers=_auth(observer))
        oid = created.json()["id"]
        blocked = client.post(f"{BASE}/observations/{oid}/promote-ground-truth", headers=_auth(promoter))
        assert blocked.status_code == 409
        client.post(f"{BASE}/observations/{oid}/submit", json={}, headers=_auth(observer))
        client.post(
            f"{BASE}/observations/{oid}/assign-reviewer",
            json={"reviewer_id": str(reviewer.id)},
            headers=_auth(promoter),
        )
        client.post(
            f"{BASE}/observations/{oid}/review",
            json={"decision": "VERIFIED", "note": "Evidence independently checked."},
            headers=_auth(reviewer),
        )
        self_promote = client.post(f"{BASE}/observations/{oid}/promote-ground-truth", headers=_auth(reviewer))
        assert self_promote.status_code == 403
        promoted = client.post(f"{BASE}/observations/{oid}/promote-ground-truth", headers=_auth(promoter))
        assert promoted.status_code == 200, promoted.text
        assert promoted.json()["ground_truth_record_key"].startswith("gt-")
        gt = db_session.scalars(select(GroundTruthRecord)).first()
        assert gt.status == GroundTruthStatus.UNVERIFIED  # GT itself still needs its own review
        assert gt.provenance_kind == ProvenanceKind.OPERATIONAL
        assert gt.source_type == GroundTruthSourceType.FIELD_OBSERVATION
        assert db_session.get(FieldObservation, uuid.UUID(oid)).ground_truth_record_id == gt.id
        assert client.post(f"{BASE}/observations/{oid}/promote-ground-truth", headers=_auth(promoter)).status_code == 409


def test_duplicate_observation_is_rejected_not_promoted(db_session: Session) -> None:
    observer = _profile(db_session, Role.WORKER, "Observer")
    admin = _profile(db_session, Role.ADMIN, "Admin")
    with _client(db_session) as client:
        first = client.post(f"{BASE}/observations", json=_observation_payload(), headers=_auth(observer)).json()
        second = client.post(
            f"{BASE}/observations",
            json=_observation_payload(source_reference=f"ref-{uuid.uuid4().hex[:12]}"),
            headers=_auth(observer),
        ).json()
        response = client.post(
            f"{BASE}/observations/{second['id']}/duplicate",
            json={"duplicate_of_id": first["id"]},
            headers=_auth(admin),
        )
        assert response.status_code == 200
        assert response.json()["status"] == "REJECTED"
        assert response.json()["decision"] == "DUPLICATE"


# ---------------------------------------------------------------------------
# Data sources
# ---------------------------------------------------------------------------


def test_source_registration_never_authorizes_and_research_cannot_be_promoted(db_session: Session) -> None:
    creator = _profile(db_session, Role.ADMIN, "Creator")
    approver = _profile(db_session, Role.ADMIN, "Approver")
    with _client(db_session) as client:
        created = client.post(f"{BASE}/data-sources", json=_source_payload(), headers=_auth(creator))
        assert created.status_code == 201
        assert created.json()["access_authorization"] == "UNAUTHORIZED"
        research = client.post(
            f"{BASE}/data-sources",
            json=_source_payload(classification="RESEARCH_ONLY"),
            headers=_auth(creator),
        ).json()
        blocked = client.post(
            f"{BASE}/data-sources/{research['id']}/authorize",
            json={"license_ref": "licence-2", "authorization_reference": "authorization-ref-002"},
            headers=_auth(approver),
        )
        assert blocked.status_code == 422
        assert blocked.json()["error"]["code"] == "research_only_source"


def test_source_authorization_requires_distinct_admin_and_evidence(db_session: Session) -> None:
    creator = _profile(db_session, Role.ADMIN, "Creator")
    approver = _profile(db_session, Role.ADMIN, "Approver")
    with _client(db_session) as client:
        created = client.post(f"{BASE}/data-sources", json=_source_payload(), headers=_auth(creator)).json()
        self_auth = client.post(
            f"{BASE}/data-sources/{created['id']}/authorize",
            json={"license_ref": "licence-3", "authorization_reference": "authorization-ref-003"},
            headers=_auth(creator),
        )
        assert self_auth.status_code == 403
        missing_hash = client.post(
            f"{BASE}/data-sources/{created['id']}/authorize",
            json={"license_ref": "licence-3", "authorization_reference": "short"},
            headers=_auth(approver),
        )
        assert missing_hash.status_code == 422
        authorized = client.post(
            f"{BASE}/data-sources/{created['id']}/authorize",
            json={"license_ref": "licence-3", "authorization_reference": "authorization-ref-003"},
            headers=_auth(approver),
        )
        assert authorized.status_code == 200
        assert authorized.json()["access_authorization"] == "AUTHORIZED"
        revoked = client.post(
            f"{BASE}/data-sources/{created['id']}/revoke",
            json={"reason": "Access permission was withdrawn by the owner."},
            headers=_auth(approver),
        )
        assert revoked.status_code == 200
        assert revoked.json()["access_authorization"] == "REVOKED"


def test_source_endpoint_rejects_private_hosts(db_session: Session) -> None:
    admin = _profile(db_session, Role.ADMIN, "Admin")
    with _client(db_session) as client:
        response = client.post(
            f"{BASE}/data-sources",
            json=_source_payload(endpoint="http://127.0.0.1:5432/admin"),
            headers=_auth(admin),
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Incidents and processing interlock
# ---------------------------------------------------------------------------


def test_critical_incident_stops_pilot_processing_without_real_world_action(db_session: Session) -> None:
    worker = _profile(db_session, Role.WORKER, "Worker")
    admin = _profile(db_session, Role.ADMIN, "Admin")
    pilot = _pilot(db_session)
    pilot.status = PilotStatus.ACTIVE
    db_session.commit()
    with _client(db_session) as client:
        created = client.post(
            f"{BASE}/incidents",
            json={
                "pilot_id": str(pilot.id),
                "title": "Critical pilot data incident",
                "description": "A structural test incident for the processing interlock.",
                "severity": "CRITICAL",
                "source": "MANUAL_TEST",
            },
            headers=_auth(worker),
        )
        assert created.status_code == 201, created.text
        data = created.json()
        assert data["processing_stopped"] is True
        assert "dispatch_performed" not in data
        processing = client.get(f"{BASE}/incidents/pilot/{pilot.id}/processing", headers=_auth(worker))
        assert processing.json()["allowed"] is False
        assert "critical_incident_processing_stop" in processing.json()["reasons"]
        iid = data["id"]
        assert client.post(
            f"{BASE}/incidents/{iid}/resume-processing",
            json={"note": "Attempted early resume before investigation."},
            headers=_auth(admin),
        ).status_code == 409
        for status in ("INVESTIGATING", "MITIGATED", "RESOLVED"):
            transition = client.post(
                f"{BASE}/incidents/{iid}/transition",
                json={"status": status, "note": f"Structural incident movement to {status}."},
                headers=_auth(admin),
            )
            assert transition.status_code == 200, transition.text
        resumed = client.post(
            f"{BASE}/incidents/{iid}/resume-processing",
            json={"note": "Processing interlock lifted after documented resolution."},
            headers=_auth(admin),
        )
        assert resumed.status_code == 200
        assert resumed.json()["processing_stopped"] is False
        assert client.get(
            f"{BASE}/incidents/pilot/{pilot.id}/processing", headers=_auth(worker)
        ).json()["allowed"] is True


def test_worker_cannot_transition_incidents(db_session: Session) -> None:
    worker = _profile(db_session, Role.WORKER, "Worker")
    admin = _profile(db_session, Role.ADMIN, "Admin")
    pilot = _pilot(db_session)
    pilot.status = PilotStatus.ACTIVE
    db_session.commit()
    with _client(db_session) as client:
        created = client.post(
            f"{BASE}/incidents",
            json={
                "pilot_id": str(pilot.id),
                "title": "Low severity pilot note",
                "description": "Structural test incident for role checks.",
                "severity": "LOW",
                "source": "MANUAL_TEST",
            },
            headers=_auth(worker),
        ).json()
        blocked = client.post(
            f"{BASE}/incidents/{created['id']}/transition",
            json={"status": "INVESTIGATING", "note": "Worker attempted an admin transition."},
            headers=_auth(worker),
        )
        assert blocked.status_code == 403
        assert client.get(f"{BASE}/incidents/{created['id']}", headers=_auth(admin)).status_code == 200


# ---------------------------------------------------------------------------
# Baselines, attestations and shutdown
# ---------------------------------------------------------------------------


def test_baseline_metrics_remain_null_without_labels(db_session: Session) -> None:
    admin = _profile(db_session, Role.ADMIN, "Admin")
    with _client(db_session) as client:
        forged = client.post(
            f"{BASE}/baselines",
            json={
                "comparison_key": "baseline-forged",
                "geographic_context_key": "BD-DHAKA",
                "comparison_type": "RULE_BASED",
                "method": "A documented method statement for testing.",
                "baseline_name": "Density",
                "candidate_name": "Experimental",
                "label_source": "No labels collected yet for this test.",
                "label_count": 0,
                "sample_count": 10,
                "candidate_metrics": {"pr_auc": 0.99},
                "baseline_metrics": {},
                "notes": "No labels are available in this fixture.",
                "limitations": "Metrics must stay null when labels are missing.",
            },
            headers=_auth(admin),
        )
        assert forged.status_code == 422
        assert forged.json()["error"]["code"] == "fabricated_metric"
        honest = client.post(
            f"{BASE}/baselines",
            json={
                "comparison_key": "baseline-honest",
                "geographic_context_key": "BD-DHAKA",
                "comparison_type": "RULE_BASED",
                "method": "A documented method statement for testing.",
                "baseline_name": "Density",
                "candidate_name": "Experimental",
                "label_source": "No labels collected yet for this test.",
                "label_count": 0,
                "sample_count": 10,
                "candidate_metrics": {"pr_auc": None},
                "baseline_metrics": {"recall": None},
                "notes": "No labels are available in this fixture.",
                "limitations": "Metrics must stay null when labels are missing.",
            },
            headers=_auth(admin),
        )
        assert honest.status_code == 201, honest.text
        assert honest.json()["candidate_metrics"]["pr_auc"] is None


def test_attestation_requires_admin_and_valid_category(db_session: Session) -> None:
    admin = _profile(db_session, Role.ADMIN, "Admin")
    worker = _profile(db_session, Role.WORKER, "Worker")
    payload = {
        "category": "backup_restore",
        "criterion_key": "backup.restore.drill",
        "status": "PASS",
        "evidence": "A documented restore drill was observed on an isolated database.",
        "evidence_refs": ["drill:record-1"],
        "blocking": True,
    }
    with _client(db_session) as client:
        assert client.post(f"{BASE}/attestations", json=payload, headers=_auth(worker)).status_code == 403
        created = client.post(f"{BASE}/attestations", json=payload, headers=_auth(admin))
        assert created.status_code == 201
        duplicate = client.post(f"{BASE}/attestations", json=payload, headers=_auth(admin))
        assert duplicate.status_code == 409
        invalid = client.post(
            f"{BASE}/attestations",
            json={**payload, "category": "fake_derived_category", "criterion_key": "fake.criterion"},
            headers=_auth(admin),
        )
        assert invalid.status_code == 422


def test_shutdown_terminates_pilot_and_preserves_records(db_session: Session) -> None:
    admin = _profile(db_session, Role.ADMIN, "Admin")
    pilot = _pilot(db_session)
    pilot.status = PilotStatus.ACTIVE
    db_session.commit()
    with _client(db_session) as client:
        response = client.post(
            f"{BASE}/pilots/{pilot.id}/shutdown",
            json={"reason": "Documented shutdown of the bounded evaluation for safety reasons."},
            headers=_auth(admin),
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["action"] == "TERMINATE"
        assert data["evidence_preserved"] is True
        assert data["audit_preserved"] is True
        assert data["reauthorization_required"] is True
        updated = db_session.get(Pilot, pilot.id)
        assert updated.status == PilotStatus.TERMINATED
        assert updated.terminated_by == admin.id
        assert "never deletes" in data["preservation_note"].lower()
        second = client.post(
            f"{BASE}/pilots/{pilot.id}/shutdown",
            json={"reason": "A second shutdown attempt after termination."},
            headers=_auth(admin),
        )
        assert second.status_code == 409
        assert db_session.scalar(select(PilotShutdown).where(PilotShutdown.pilot_id == pilot.id)) is not None


def test_pilot_terminate_action_requires_reason_and_valid_state(db_session: Session) -> None:
    admin = _profile(db_session, Role.ADMIN, "Admin")
    pilot = _pilot(db_session)
    pilot.status = PilotStatus.APPROVED
    db_session.commit()
    with _client(db_session) as client:
        missing_reason = client.post(
            f"/api/v1/governance/pilots/{pilot.id}/transition",
            json={"action": "TERMINATE"},
            headers=_auth(admin),
        )
        assert missing_reason.status_code == 400
        assert missing_reason.json()["error"]["code"] == "note_required"
        pilot.status = PilotStatus.DRAFT
        db_session.commit()
        from_draft = client.post(
            f"/api/v1/governance/pilots/{pilot.id}/transition",
            json={"action": "TERMINATE", "note": "Attempt to terminate before approval."},
            headers=_auth(admin),
        )
        assert from_draft.status_code == 409
        assert from_draft.json()["error"]["code"] == "invalid_pilot_transition"


def test_manual_attestations_alone_cannot_satisfy_final_gate(db_session: Session) -> None:
    from app.phase14.attestations import CATEGORIES

    admin = _profile(db_session, Role.ADMIN, "Attestor")
    for category in sorted(CATEGORIES):
        db_session.add(
            Phase14Attestation(
                category=category,
                criterion_key=f"{category}.recorded",
                status="PASS",
                evidence=f"Attestation recorded for {category} in a structural test.",
                evidence_refs=[f"test:{category}"],
                blocking=True,
                assessed_by=admin.id,
                assessed_at=datetime.now(timezone.utc),
            )
        )
    db_session.commit()
    report = assess_phase14_readiness(db_session)
    assert report["overall"] == "NOT_READY"
    assert report["ready_for_activation"] is False
    assert "phase14_pilot_boundary" in report["mandatory_unmet"]
    assert "phase14_ground_truth" in report["mandatory_unmet"]
    assert "phase14_model_validation" in report["mandatory_unmet"]
    del admin


def test_observation_audit_keeps_original_evidence_hash_after_db_tampering(db_session: Session) -> None:
    observer = _profile(db_session, Role.WORKER, "Observer")
    with _client(db_session) as client:
        created = client.post(f"{BASE}/observations", json=_observation_payload(), headers=_auth(observer))
        oid = uuid.UUID(created.json()["id"])
        row = db_session.get(FieldObservation, oid)
        row.evidence_sha256 = "f" * 64
        db_session.commit()
        events = client.get(f"{BASE}/observations/{oid}", headers=_auth(observer)).json()["events"]
        assert events[0]["evidence_sha256"] == "a" * 64
        assert events[0]["action"] == "CREATED"


def test_no_client_endpoint_can_edit_or_delete_phase14_audit_records(db_session: Session) -> None:
    admin = _profile(db_session, Role.ADMIN, "Admin")
    with _client(db_session) as client:
        boundary = client.post(f"{BASE}/boundaries", json=_boundary_payload(), headers=_auth(admin)).json()
        observation = client.post(f"{BASE}/observations", json=_observation_payload(), headers=_auth(admin)).json()
        for path in (
            f"{BASE}/boundaries/{boundary['id']}/events",
            f"{BASE}/observations/{observation['id']}/events",
        ):
            assert client.patch(path, json={"note": "edited"}, headers=_auth(admin)).status_code in {404, 405}
            assert client.delete(path, headers=_auth(admin)).status_code in {404, 405}
