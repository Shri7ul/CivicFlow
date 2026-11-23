"""Incident reporting, visibility, lifecycle, and department API tests."""

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
    Department,
    Incident,
    IncidentStatusEvent,
    Profile,
    Role,
)
from tests.auth_support import make_settings, make_token, make_verifier

PAYLOAD: dict[str, Any] = {
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
    full_name: str | None = None,
) -> Profile:
    profile = Profile(
        id=uuid.uuid4(),
        full_name=full_name or f"{role.value.title()} User",
        role=role,
        is_active=True,
    )
    session.add(profile)
    session.commit()
    return profile


def _department(session: Session, *, active: bool = True) -> Department:
    department = Department(
        name=f"Department {uuid.uuid4().hex[:8]}",
        description="Test department",
        is_active=active,
    )
    session.add(department)
    session.commit()
    return department


def _client(session: Session) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_token_verifier] = lambda: make_verifier(
        make_settings()
    )
    return TestClient(app)


def _auth(profile: Profile) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(sub=profile.id)}"}


def _report(client: TestClient, profile: Profile, **overrides: Any):
    payload = {**PAYLOAD, **overrides}
    return client.post("/api/v1/incidents", headers=_auth(profile), json=payload)


def test_citizen_can_report_and_read_own_incident(db_session: Session) -> None:
    citizen = _profile(db_session)
    other = _profile(db_session)
    with _client(db_session) as client:
        response = _report(client, citizen)
        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "OPEN"
        assert body["reporter"]["id"] == str(citizen.id)
        assert body["latitude"] == 23.8103
        assert body["longitude"] == 90.4125
        assert body["assigned_department"] is None
        assert len(body["history"]) == 1
        assert body["history"][0]["from_status"] is None
        assert body["history"][0]["to_status"] == "OPEN"

        incident_id = body["id"]
        detail = client.get(
            f"/api/v1/incidents/{incident_id}", headers=_auth(citizen)
        )
        assert detail.status_code == 200
        assert detail.json()["title"] == PAYLOAD["title"]

        own_list = client.get("/api/v1/incidents", headers=_auth(citizen))
        assert own_list.status_code == 200
        assert own_list.json()["total"] == 1
        assert own_list.json()["items"][0]["id"] == incident_id

        other_list = client.get("/api/v1/incidents", headers=_auth(other))
        assert other_list.json()["total"] == 0
        hidden = client.get(
            f"/api/v1/incidents/{incident_id}", headers=_auth(other)
        )
        assert hidden.status_code == 404
        assert hidden.json()["error"]["code"] == "incident_not_found"


def test_report_validation_rejects_bad_coordinates_and_extra_fields(
    db_session: Session,
) -> None:
    citizen = _profile(db_session)
    with _client(db_session) as client:
        bad_latitude = _report(client, citizen, latitude=91)
        assert bad_latitude.status_code == 422
        assert bad_latitude.json()["error"]["code"] == "validation_error"

        blank_title = _report(client, citizen, title="   ")
        assert blank_title.status_code == 422

        extra = _report(client, citizen, reporter_id=str(citizen.id))
        assert extra.status_code == 422

        no_auth = client.get("/api/v1/incidents")
        assert no_auth.status_code == 401


def test_worker_lifecycle_records_history_and_guards_transitions(
    db_session: Session,
) -> None:
    citizen = _profile(db_session)
    worker = _profile(db_session, role=Role.WORKER)
    department = _department(db_session)
    with _client(db_session) as client:
        incident_id = _report(client, citizen).json()["id"]

        no_department = client.post(
            f"/api/v1/incidents/{incident_id}/status",
            headers=_auth(worker),
            json={"status": "ACKNOWLEDGED"},
        )
        assert no_department.status_code == 422
        assert no_department.json()["error"]["code"] == "department_required"

        acknowledged = client.post(
            f"/api/v1/incidents/{incident_id}/status",
            headers=_auth(worker),
            json={
                "status": "ACKNOWLEDGED",
                "department_id": str(department.id),
                "note": "Crew dispatched.",
            },
        )
        assert acknowledged.status_code == 200
        body = acknowledged.json()
        assert body["status"] == "ACKNOWLEDGED"
        assert body["assigned_department"]["id"] == str(department.id)

        citizen_transition = client.post(
            f"/api/v1/incidents/{incident_id}/status",
            headers=_auth(citizen),
            json={"status": "IN_PROGRESS"},
        )
        assert citizen_transition.status_code == 403
        assert citizen_transition.json()["error"]["code"] == "insufficient_role"

        in_progress = client.post(
            f"/api/v1/incidents/{incident_id}/status",
            headers=_auth(worker),
            json={"status": "IN_PROGRESS", "note": "Crew on site."},
        )
        assert in_progress.status_code == 200

        resolved = client.post(
            f"/api/v1/incidents/{incident_id}/status",
            headers=_auth(worker),
            json={"status": "RESOLVED", "note": "Drain cleared."},
        )
        assert resolved.status_code == 200
        assert resolved.json()["resolved_at"] is not None

        closed = client.post(
            f"/api/v1/incidents/{incident_id}/status",
            headers=_auth(worker),
            json={"status": "CLOSED"},
        )
        assert closed.status_code == 200
        history = closed.json()["history"]
        assert [event["to_status"] for event in history] == [
            "OPEN",
            "ACKNOWLEDGED",
            "IN_PROGRESS",
            "RESOLVED",
            "CLOSED",
        ]
        assert history[-1]["actor"]["id"] == str(worker.id)

        invalid = client.post(
            f"/api/v1/incidents/{incident_id}/status",
            headers=_auth(worker),
            json={"status": "IN_PROGRESS"},
        )
        assert invalid.status_code == 409
        assert invalid.json()["error"]["code"] == "invalid_status_transition"

        edit_after_close = client.patch(
            f"/api/v1/incidents/{incident_id}",
            headers=_auth(worker),
            json={"title": "Changed after close"},
        )
        assert edit_after_close.status_code == 409
        assert edit_after_close.json()["error"]["code"] == "incident_not_editable"


def test_citizen_can_edit_open_incident_but_not_after_acknowledgement(
    db_session: Session,
) -> None:
    citizen = _profile(db_session)
    other = _profile(db_session)
    worker = _profile(db_session, role=Role.WORKER)
    department = _department(db_session)
    with _client(db_session) as client:
        incident_id = _report(client, citizen).json()["id"]

        edited = client.patch(
            f"/api/v1/incidents/{incident_id}",
            headers=_auth(citizen),
            json={
                "title": "Updated blocked drain",
                "severity": "CRITICAL",
                "latitude": 23.82,
            },
        )
        assert edited.status_code == 200
        body = edited.json()
        assert body["title"] == "Updated blocked drain"
        assert body["severity"] == "CRITICAL"
        assert body["latitude"] == 23.82
        assert body["longitude"] == 90.4125

        null_coordinate = client.patch(
            f"/api/v1/incidents/{incident_id}",
            headers=_auth(citizen),
            json={"latitude": None, "longitude": 90.4},
        )
        assert null_coordinate.status_code == 422
        assert null_coordinate.json()["error"]["code"] == "invalid_incident_update"

        hidden = client.patch(
            f"/api/v1/incidents/{incident_id}",
            headers=_auth(other),
            json={"title": "Not mine"},
        )
        assert hidden.status_code == 404

        client.post(
            f"/api/v1/incidents/{incident_id}/status",
            headers=_auth(worker),
            json={
                "status": "ACKNOWLEDGED",
                "department_id": str(department.id),
            },
        )
        locked = client.patch(
            f"/api/v1/incidents/{incident_id}",
            headers=_auth(citizen),
            json={"title": "Too late"},
        )
        assert locked.status_code == 409

        empty = client.patch(
            f"/api/v1/incidents/{incident_id}",
            headers=_auth(citizen),
            json={},
        )
        assert empty.status_code == 422
        assert empty.json()["error"]["code"] == "empty_update"


def test_list_filters_and_spatial_filter_boundary(db_session: Session) -> None:
    citizen = _profile(db_session)
    with _client(db_session) as client:
        _report(client, citizen, title="Drain issue", category="DRAINAGE")
        _report(
            client,
            citizen,
            title="Street light outage",
            category="UTILITIES",
            severity="LOW",
        )

        category = client.get(
            "/api/v1/incidents?category=UTILITIES", headers=_auth(citizen)
        )
        assert category.json()["total"] == 1
        assert category.json()["items"][0]["title"] == "Street light outage"

        search = client.get(
            "/api/v1/incidents?q=Drain", headers=_auth(citizen)
        )
        assert search.json()["total"] == 1

        partial_bbox = client.get(
            "/api/v1/incidents?min_latitude=23&min_longitude=90",
            headers=_auth(citizen),
        )
        assert partial_bbox.status_code == 422
        assert partial_bbox.json()["error"]["code"] == "invalid_bbox"

        unsupported = client.get(
            "/api/v1/incidents"
            "?min_latitude=23&min_longitude=90&max_latitude=24&max_longitude=91",
            headers=_auth(citizen),
        )
        assert unsupported.status_code == 400
        assert unsupported.json()["error"]["code"] == "spatial_filter_unsupported"


def test_departments_are_authenticated_and_active_only(
    db_session: Session,
) -> None:
    citizen = _profile(db_session)
    active = _department(db_session, active=True)
    _department(db_session, active=False)
    with _client(db_session) as client:
        unauthenticated = client.get("/api/v1/departments")
        assert unauthenticated.status_code == 401

        response = client.get("/api/v1/departments", headers=_auth(citizen))
        assert response.status_code == 200
        body = response.json()
        assert [item["id"] for item in body] == [str(active.id)]
        assert body[0]["name"] == active.name


def test_incident_history_and_cascade_constraints(db_session: Session) -> None:
    citizen = _profile(db_session)
    with _client(db_session) as client:
        incident_id = _report(client, citizen).json()["id"]

    incident_count = db_session.scalar(
        select(func.count()).select_from(Incident)
    )
    event_count = db_session.scalar(
        select(func.count()).select_from(IncidentStatusEvent)
    )
    assert incident_count == 1
    assert event_count == 1
    event = db_session.scalar(select(IncidentStatusEvent))
    assert event is not None
    assert event.from_status is None
    assert event.to_status.value == "OPEN"
    assert str(event.incident_id) == incident_id
