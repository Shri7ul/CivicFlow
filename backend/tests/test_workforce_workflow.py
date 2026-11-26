"""Worker application, assignment and verification lifecycle API tests."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.jwt import get_token_verifier
from app.db.session import get_db_session
from app.main import create_app
from app.models import (
    Incident,
    IncidentStatus,
    Profile,
    Role,
    WorkerApplication,
    WorkerProfile,
    WorkerStatus,
    WorkforceEvent,
    WorkforceNotification,
)
from tests.auth_support import make_settings, make_token, make_verifier

APPLICATION: dict[str, Any] = {
    "full_name": "Amina Rahman",
    "phone": "+8801711000000",
    "email": "amina@example.com",
    "specialization": "Drainage",
    "service_area": "Dhanmondi",
    "address": "Road 12, Dhanmondi",
    "experience": "Five years of municipal drainage response.",
    "credentials_note": "Municipal certificate available on request",
}

INCIDENT: dict[str, Any] = {
    "title": "Blocked storm drain",
    "description": "Water is pooling across the road after every rain shower.",
    "category": "DRAINAGE",
    "severity": "HIGH",
    "latitude": 23.8103,
    "longitude": 90.4125,
    "address": "Road 12, Dhanmondi",
}


def _profile(
    session: Session,
    *,
    role: Role = Role.CITIZEN,
    name: str | None = None,
    is_active: bool = True,
) -> Profile:
    profile = Profile(
        id=uuid.uuid4(),
        full_name=name or f"{role.value.title()} User",
        role=role,
        is_active=is_active,
    )
    session.add(profile)
    session.commit()
    return profile


def _client(session: Session) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_token_verifier] = lambda: make_verifier(make_settings())
    return TestClient(app)


def _auth(profile: Profile) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(sub=profile.id)}"}


def _apply(client: TestClient, citizen: Profile, **overrides: Any):
    payload = {**APPLICATION, **overrides}
    return client.post("/api/v1/workforce/applications", json=payload, headers=_auth(citizen))


def _approve(client: TestClient, admin: Profile, application_id: str):
    return client.post(
        f"/api/v1/workforce/applications/{application_id}/review",
        json={"decision": "APPROVE", "note": "Credentials verified"},
        headers=_auth(admin),
    )


def _report(client: TestClient, citizen: Profile) -> str:
    response = client.post("/api/v1/incidents", json=INCIDENT, headers=_auth(citizen))
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _verify_incident(client: TestClient, admin: Profile, incident_id: str) -> None:
    response = client.post(
        f"/api/v1/incidents/{incident_id}/status",
        json={"status": "VERIFIED"},
        headers=_auth(admin),
    )
    assert response.status_code == 200, response.text


def _approved_worker(
    client: TestClient, session: Session, admin: Profile, citizen: Profile
) -> tuple[str, str]:
    created = _apply(client, citizen)
    assert created.status_code == 201, created.text
    application_id = created.json()["id"]
    approved = _approve(client, admin, application_id)
    assert approved.status_code == 200, approved.text
    worker = session.scalar(
        select(WorkerProfile).where(WorkerProfile.profile_id == citizen.id)
    )
    assert worker is not None
    return application_id, str(worker.id)


def test_application_submission_duplicate_and_role_guards(db_session: Session) -> None:
    citizen = _profile(db_session)
    admin = _profile(db_session, role=Role.ADMIN)
    with _client(db_session) as client:
        first = _apply(client, citizen)
        assert first.status_code == 201
        assert first.json()["status"] == "PENDING"
        assert first.json()["applicant_id"] == str(citizen.id)

        duplicate = _apply(client, citizen)
        assert duplicate.status_code == 409
        assert duplicate.json()["error"]["code"] == "duplicate_application"

        mine = client.get("/api/v1/workforce/applications/mine", headers=_auth(citizen))
        assert mine.status_code == 200
        assert mine.json()["id"] == first.json()["id"]

        as_admin = _apply(client, admin)
        assert as_admin.status_code == 409
        assert as_admin.json()["error"]["code"] == "application_not_allowed"

        listing = client.get("/api/v1/workforce/applications", headers=_auth(citizen))
        assert listing.status_code == 403
        assert listing.json()["error"]["code"] == "insufficient_role"


def test_pending_applicant_cannot_use_worker_workspace(db_session: Session) -> None:
    citizen = _profile(db_session)
    with _client(db_session) as client:
        assert _apply(client, citizen).status_code == 201
        response = client.get("/api/v1/workforce/workers/me", headers=_auth(citizen))
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "insufficient_role"
        assignments = client.get("/api/v1/workforce/assignments", headers=_auth(citizen))
        assert assignments.status_code == 403
        assert assignments.json()["error"]["code"] == "insufficient_role"


def test_admin_approval_grants_worker_role_and_audits(db_session: Session) -> None:
    citizen = _profile(db_session)
    admin = _profile(db_session, role=Role.ADMIN)
    with _client(db_session) as client:
        application_id, worker_id = _approved_worker(client, db_session, admin, citizen)

        db_session.expire_all()
        assert db_session.get(Profile, citizen.id).role is Role.WORKER
        worker = db_session.get(WorkerProfile, uuid.UUID(worker_id))
        assert worker is not None
        assert worker.status is WorkerStatus.ACTIVE
        assert worker.approved_by == admin.id
        assert worker.specialization == "Drainage"

        me = client.get("/api/v1/workforce/workers/me", headers=_auth(citizen))
        assert me.status_code == 200
        assert me.json()["status"] == "ACTIVE"

        notices = client.get("/api/v1/workforce/notifications", headers=_auth(citizen))
        assert notices.status_code == 200
        assert notices.json()["unread"] >= 1
        assert any(
            item["kind"] == "worker_application_approved"
            for item in notices.json()["items"]
        )

        events = client.get("/api/v1/workforce/events", headers=_auth(admin))
        assert events.status_code == 200
        actions = {item["action"] for item in events.json()["items"]}
        assert {
            "worker_application_submitted",
            "worker_application_approved",
        }.issubset(actions)
        assert application_id in [
            item["entity_id"] for item in events.json()["items"]
        ]

        # No ordinary API can mutate an audit event.
        assert (
            client.put(f"/api/v1/workforce/events/{uuid.uuid4()}", headers=_auth(admin)).status_code
            in {404, 405}
        )


def test_rejection_and_additional_information_require_note(db_session: Session) -> None:
    citizen_a = _profile(db_session, name="Applicant A")
    citizen_b = _profile(db_session, name="Applicant B")
    admin = _profile(db_session, role=Role.ADMIN)
    with _client(db_session) as client:
        first = _apply(client, citizen_a).json()["id"]
        second = _apply(client, citizen_b).json()["id"]

        missing = client.post(
            f"/api/v1/workforce/applications/{first}/review",
            json={"decision": "REJECT"},
            headers=_auth(admin),
        )
        assert missing.status_code == 422
        assert missing.json()["error"]["code"] == "review_note_required"

        rejected = client.post(
            f"/api/v1/workforce/applications/{first}/review",
            json={"decision": "REJECT", "note": "Insufficient experience"},
            headers=_auth(admin),
        )
        assert rejected.status_code == 200
        assert rejected.json()["status"] == "REJECTED"

        info = client.post(
            f"/api/v1/workforce/applications/{second}/review",
            json={"decision": "REQUEST_INFO", "note": "Provide a contact number"},
            headers=_auth(admin),
        )
        assert info.status_code == 200
        assert info.json()["status"] == "ADDITIONAL_INFORMATION_REQUIRED"

        decided = client.post(
            f"/api/v1/workforce/applications/{first}/review",
            json={"decision": "APPROVE"},
            headers=_auth(admin),
        )
        assert decided.status_code == 409
        assert decided.json()["error"]["code"] == "application_already_decided"

        notices = client.get("/api/v1/workforce/notifications", headers=_auth(citizen_b))
        assert any(
            item["kind"] == "worker_application_additional_information"
            for item in notices.json()["items"]
        )


def test_citizen_cannot_approve_and_worker_cannot_approve_self(db_session: Session) -> None:
    citizen = _profile(db_session)
    admin = _profile(db_session, role=Role.ADMIN)
    with _client(db_session) as client:
        application_id = _apply(client, citizen).json()["id"]
        citizen_attempt = client.post(
            f"/api/v1/workforce/applications/{application_id}/review",
            json={"decision": "APPROVE"},
            headers=_auth(citizen),
        )
        assert citizen_attempt.status_code == 403

        _approve(client, admin, application_id)
        db_session.expire_all()
        assert db_session.get(Profile, citizen.id).role is Role.WORKER
        self_attempt = client.post(
            f"/api/v1/workforce/applications/{application_id}/review",
            json={"decision": "APPROVE"},
            headers=_auth(citizen),
        )
        assert self_attempt.status_code == 403


def test_full_lifecycle_from_report_to_resolution(db_session: Session) -> None:
    citizen = _profile(db_session)
    admin = _profile(db_session, role=Role.ADMIN)
    with _client(db_session) as client:
        _, worker_id = _approved_worker(client, db_session, admin, citizen)
        incident_id = _report(client, citizen)
        _verify_incident(client, admin, incident_id)

        candidates = client.get(
            "/api/v1/workforce/assignments/candidates",
            params={"incident_id": incident_id},
            headers=_auth(admin),
        )
        assert candidates.status_code == 200
        assert candidates.json()["items"]
        assert any(
            item["worker_profile_id"] == worker_id and item["eligible"]
            for item in candidates.json()["items"]
        )

        assigned = client.post(
            "/api/v1/workforce/assignments",
            json={
                "incident_id": incident_id,
                "worker_profile_id": worker_id,
                "note": "Area and specialization match",
            },
            headers=_auth(admin),
        )
        assert assigned.status_code == 201, assigned.text
        assignment_id = assigned.json()["id"]
        assert assigned.json()["status"] == "OFFERED"
        assert "service area" in assigned.json()["rationale"]

        detail = client.get(
            f"/api/v1/incidents/{incident_id}", headers=_auth(citizen)
        )
        assert detail.json()["status"] == "ASSIGNED"

        accepted = client.post(
            f"/api/v1/workforce/assignments/{assignment_id}/accept",
            json={"note": "Accepted"},
            headers=_auth(citizen),
        )
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["status"] == "ACCEPTED"

        started = client.post(
            f"/api/v1/workforce/assignments/{assignment_id}/start",
            json={"note": "On site"},
            headers=_auth(citizen),
        )
        assert started.status_code == 200, started.text
        assert started.json()["status"] == "IN_PROGRESS"

        progressed = client.post(
            f"/api/v1/workforce/assignments/{assignment_id}/progress",
            json={"note": "Clearing in progress", "progress_percent": 60},
            headers=_auth(citizen),
        )
        assert progressed.status_code == 200

        completed = client.post(
            f"/api/v1/workforce/assignments/{assignment_id}/complete",
            json={"note": "Drain cleared and flow restored"},
            headers=_auth(citizen),
        )
        assert completed.status_code == 200, completed.text
        assert completed.json()["status"] == "COMPLETION_SUBMITTED"

        pending_detail = client.get(
            f"/api/v1/incidents/{incident_id}", headers=_auth(citizen)
        )
        assert pending_detail.json()["status"] == "COMPLETION_SUBMITTED"

        rework = client.post(
            f"/api/v1/workforce/assignments/{assignment_id}/verify",
            json={"approve": False, "note": "Photo evidence required"},
            headers=_auth(admin),
        )
        assert rework.status_code == 200
        assert rework.json()["status"] == "IN_PROGRESS"

        resubmitted = client.post(
            f"/api/v1/workforce/assignments/{assignment_id}/complete",
            json={"note": "Cleared again with site notes"},
            headers=_auth(citizen),
        )
        assert resubmitted.status_code == 200

        verified = client.post(
            f"/api/v1/workforce/assignments/{assignment_id}/verify",
            json={"approve": True, "note": "Verified on site criteria"},
            headers=_auth(admin),
        )
        assert verified.status_code == 200, verified.text
        assert verified.json()["status"] == "VERIFIED_COMPLETED"
        assert verified.json()["verified_at"] is not None

        final = client.get(f"/api/v1/incidents/{incident_id}", headers=_auth(citizen))
        assert final.json()["status"] == "RESOLVED"
        statuses = [event["to_status"] for event in final.json()["history"]]
        assert statuses == [
            "OPEN",
            "VERIFIED",
            "ASSIGNED",
            "ACCEPTED",
            "IN_PROGRESS",
            "COMPLETION_SUBMITTED",
            "IN_PROGRESS",
            "COMPLETION_SUBMITTED",
            "VERIFIED_COMPLETED",
            "RESOLVED",
        ]

        citizen_notices = client.get(
            "/api/v1/workforce/notifications", headers=_auth(citizen)
        )
        assert any(
            item["kind"] == "incident_resolved"
            for item in citizen_notices.json()["items"]
        )


def test_assignment_guards_and_ownership(db_session: Session) -> None:
    admin = _profile(db_session, role=Role.ADMIN)
    worker_a = _profile(db_session, name="Worker A")
    worker_b = _profile(db_session, name="Worker B")
    with _client(db_session) as client:
        _, worker_a_id = _approved_worker(client, db_session, admin, worker_a)
        _, worker_b_id = _approved_worker(client, db_session, admin, worker_b)
        incident_id = _report(client, worker_a)
        _verify_incident(client, admin, incident_id)

        assigned = client.post(
            "/api/v1/workforce/assignments",
            json={"incident_id": incident_id, "worker_profile_id": worker_a_id},
            headers=_auth(admin),
        )
        assert assigned.status_code == 201
        assignment_id = assigned.json()["id"]

        double = client.post(
            "/api/v1/workforce/assignments",
            json={"incident_id": incident_id, "worker_profile_id": worker_b_id},
            headers=_auth(admin),
        )
        assert double.status_code == 409
        assert double.json()["error"]["code"] == "incident_already_assigned"

        foreign = client.post(
            f"/api/v1/workforce/assignments/{assignment_id}/accept",
            json={"note": "Not mine"},
            headers=_auth(worker_b),
        )
        assert foreign.status_code == 404
        assert foreign.json()["error"]["code"] == "assignment_not_found"

        invalid = client.post(
            f"/api/v1/incidents/{incident_id}/status",
            json={"status": "RESOLVED"},
            headers=_auth(admin),
        )
        assert invalid.status_code == 409
        assert invalid.json()["error"]["code"] == "invalid_status_transition"

        cancel = client.post(
            f"/api/v1/workforce/assignments/{assignment_id}/cancel",
            json={"note": "Replanning"},
            headers=_auth(admin),
        )
        assert cancel.status_code == 200
        assert cancel.json()["status"] == "CANCELLED"
        incident = client.get(f"/api/v1/incidents/{incident_id}", headers=_auth(admin))
        assert incident.json()["status"] == "VERIFIED"


def test_suspended_worker_is_ineligible_and_loses_access(db_session: Session) -> None:
    admin = _profile(db_session, role=Role.ADMIN)
    worker_user = _profile(db_session, name="Suspendable Worker")
    with _client(db_session) as client:
        _, worker_id = _approved_worker(client, db_session, admin, worker_user)
        incident_id = _report(client, worker_user)
        _verify_incident(client, admin, incident_id)

        missing_reason = client.post(
            f"/api/v1/workforce/workers/{worker_id}/suspend",
            json={},
            headers=_auth(admin),
        )
        assert missing_reason.status_code == 422
        assert missing_reason.json()["error"]["code"] == "suspension_reason_required"

        suspended = client.post(
            f"/api/v1/workforce/workers/{worker_id}/suspend",
            json={"note": "Under investigation"},
            headers=_auth(admin),
        )
        assert suspended.status_code == 200
        assert suspended.json()["status"] == "SUSPENDED"

        denied = client.get("/api/v1/workforce/workers/me", headers=_auth(worker_user))
        assert denied.status_code == 403
        assert denied.json()["error"]["code"] == "worker_suspended"

        candidates = client.get(
            "/api/v1/workforce/assignments/candidates",
            params={"incident_id": incident_id},
            headers=_auth(admin),
        )
        assert all(
            item["worker_profile_id"] != worker_id for item in candidates.json()["items"]
        )

        bad_assign = client.post(
            "/api/v1/workforce/assignments",
            json={"incident_id": incident_id, "worker_profile_id": worker_id},
            headers=_auth(admin),
        )
        assert bad_assign.status_code == 409
        assert bad_assign.json()["error"]["code"] == "worker_not_active"

        reactivated = client.post(
            f"/api/v1/workforce/workers/{worker_id}/reactivate",
            headers=_auth(admin),
        )
        assert reactivated.status_code == 200
        assert reactivated.json()["status"] == "ACTIVE"


def test_admin_overview_uses_real_counts(db_session: Session) -> None:
    admin = _profile(db_session, role=Role.ADMIN)
    citizen = _profile(db_session)
    with _client(db_session) as client:
        before = client.get("/api/v1/workforce/admin/overview", headers=_auth(admin))
        assert before.status_code == 200
        assert before.json()["total_incidents"] == 0

        _apply(client, citizen)
        _report(client, citizen)

        after = client.get("/api/v1/workforce/admin/overview", headers=_auth(admin))
        assert after.json()["total_incidents"] == 1
        assert after.json()["unreviewed_incidents"] == 1
        assert after.json()["pending_applications"] == 1

        unauthorized = client.get("/api/v1/workforce/admin/overview", headers=_auth(citizen))
        assert unauthorized.status_code == 403

        count = db_session.scalar(
            select(func.count()).select_from(WorkforceEvent)
        )
        assert count and count >= 1
        notification_count = db_session.scalar(
            select(func.count()).select_from(WorkforceNotification)
        )
        assert notification_count and notification_count >= 1


def test_audit_metadata_is_persisted_and_scrubbed(db_session: Session) -> None:
    """Audit detail must round-trip and never retain sensitive keys."""
    from app.workforce.audit import emit

    event = emit(
        db_session,
        actor_id=None,
        action="test_action",
        entity_type="worker_application",
        entity_id=uuid.uuid4(),
        previous_state="PENDING",
        new_state="APPROVED",
        metadata={
            "worker_profile_id": "worker-1",
            "count": 2,
            "password": "must-not-be-stored",
            "signed_url": "https://example.invalid/private",
            "access_key": "must-not-be-stored",
            "nested": {"secret": "must-not-be-stored"},
        },
    )
    db_session.commit()
    db_session.expire_all()

    stored = db_session.get(WorkforceEvent, event.id)
    assert stored is not None
    assert stored.detail == {"worker_profile_id": "worker-1", "count": 2}
    assert stored.previous_state == "PENDING"
    assert stored.new_state == "APPROVED"
