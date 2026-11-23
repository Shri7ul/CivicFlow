"""Phase 4 incident intelligence, duplicate, and infrastructure API tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.jwt import get_token_verifier
from app.db.session import get_db_session
from app.main import create_app
from app.models import (
    AssetType,
    DependencyEdge,
    DependencyType,
    Incident,
    IncidentRelationship,
    InfrastructureAsset,
    Profile,
    RelationshipStatus,
    RelationshipType,
    Role,
)
from app.services.intelligence import geometry_distance_m, text_similarity
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
    name: str = "Citizen",
) -> Profile:
    profile = Profile(
        id=uuid.uuid4(),
        full_name=name,
        role=role,
        is_active=True,
    )
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


def _report(
    client: TestClient,
    profile: Profile,
    **overrides: Any,
) -> dict[str, Any]:
    payload = {**PAYLOAD, **overrides}
    response = client.post("/api/v1/incidents", headers=_auth(profile), json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_helpers_are_explainable_and_geometrically_sane() -> None:
    assert text_similarity("blocked storm drain overflowing", "storm drain blocked") > 0.3
    assert text_similarity("blocked storm drain", "street light outage") < 0.2
    # The line runs through the origin; the point is about 111 m north.
    assert geometry_distance_m(23.811, 90.4125, "POINT(90.4125 23.811)") < 1
    line_distance = geometry_distance_m(
        23.8100, 90.4125, "LINESTRING(90.4100 23.8100, 90.4150 23.8100)"
    )
    assert line_distance < 1


def test_duplicate_and_related_suggestions_are_explained(
    db_session: Session,
) -> None:
    citizen = _profile(db_session)
    with _client(db_session) as client:
        primary = _report(client, citizen)
        duplicate = _report(
            client,
            citizen,
            title="Storm drain blocked",
            description="Water pooling across the road from the blocked drain.",
        )
        _report(
            client,
            citizen,
            title="Street light outage",
            description="The street light at the corner is not working.",
            category="UTILITIES",
            severity="LOW",
            latitude=23.9000,
            longitude=90.5000,
        )

        response = client.get(
            f"/api/v1/incidents/{primary['id']}/intelligence",
            headers=_auth(citizen),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        duplicate_ids = {
            item["incident"]["id"] for item in body["duplicate_candidates"]
        }
        assert duplicate["id"] in duplicate_ids
        assert body["duplicate_candidates"][0]["confidence"] >= 0.55
        assert body["duplicate_candidates"][0]["reasons"]
        signal_keys = {
            signal["key"]
            for signal in body["duplicate_candidates"][0]["signals"]
        }
        assert {"distance", "time", "text", "category", "severity", "status"} <= signal_keys
        assert body["thresholds"]["duplicate_radius_m"] == 250
        assert "not confirmed facts" in body["limitations"][0]


def test_same_location_but_different_text_is_not_a_duplicate(
    db_session: Session,
) -> None:
    citizen = _profile(db_session)
    with _client(db_session) as client:
        primary = _report(client, citizen)
        _report(
            client,
            citizen,
            title="Street light outage",
            description="The street light at the corner is not working.",
            category="DRAINAGE",
        )
        response = client.get(
            f"/api/v1/incidents/{primary['id']}/intelligence",
            headers=_auth(citizen),
        )
        body = response.json()
        assert body["duplicate_candidates"] == []


def test_citizen_cannot_infer_another_citizens_incident(
    db_session: Session,
) -> None:
    owner = _profile(db_session, name="Owner")
    other = _profile(db_session, name="Other")
    worker = _profile(db_session, role=Role.WORKER, name="Worker")
    with _client(db_session) as client:
        owner_incident = _report(client, owner)
        other_incident = _report(
            client,
            other,
            title="Blocked storm drain",
            description="Water is pooling across the road after every rain shower.",
        )

        owner_view = client.get(
            f"/api/v1/incidents/{owner_incident['id']}/intelligence",
            headers=_auth(owner),
        )
        assert owner_view.status_code == 200
        owner_candidates = {
            item["incident"]["id"]
            for item in owner_view.json()["duplicate_candidates"]
        }
        assert other_incident["id"] not in owner_candidates

        staff_view = client.get(
            f"/api/v1/incidents/{owner_incident['id']}/intelligence",
            headers=_auth(worker),
        )
        assert staff_view.status_code == 200
        staff_candidates = {
            item["incident"]["id"]
            for item in staff_view.json()["duplicate_candidates"]
        }
        assert other_incident["id"] in staff_candidates

        hidden = client.get(
            f"/api/v1/incidents/{other_incident['id']}/intelligence",
            headers=_auth(owner),
        )
        assert hidden.status_code == 404


def test_relationship_review_is_unique_persistent_and_staff_only(
    db_session: Session,
) -> None:
    owner = _profile(db_session, name="Owner")
    other = _profile(db_session, name="Other")
    worker = _profile(db_session, role=Role.WORKER, name="Worker")
    with _client(db_session) as client:
        first = _report(client, owner)
        second = _report(
            client,
            other,
            title="Blocked storm drain",
            description="Water is pooling across the road after every rain shower.",
        )
        payload = {
            "other_incident_id": second["id"],
            "relationship_type": "DUPLICATE",
            "status": "CONFIRMED",
            "confidence": 0.88,
            "signals": {"source": "staff_review"},
            "note": "Same drain and time window.",
        }

        forbidden = client.post(
            f"/api/v1/incidents/{first['id']}/relationships",
            headers=_auth(owner),
            json=payload,
        )
        assert forbidden.status_code == 403

        self_review = client.post(
            f"/api/v1/incidents/{first['id']}/relationships",
            headers=_auth(worker),
            json={**payload, "other_incident_id": first["id"]},
        )
        assert self_review.status_code == 422
        assert self_review.json()["error"]["code"] == "self_relationship"

        created = client.post(
            f"/api/v1/incidents/{first['id']}/relationships",
            headers=_auth(worker),
            json=payload,
        )
        assert created.status_code == 200, created.text
        relationship = created.json()
        assert relationship["status"] == "CONFIRMED"
        assert relationship["other_incident"]["id"] == second["id"]

        # Re-review updates the same relationship rather than duplicating it.
        updated = client.post(
            f"/api/v1/incidents/{first['id']}/relationships",
            headers=_auth(worker),
            json={**payload, "status": "DISMISSED", "note": "Different drain."},
        )
        assert updated.status_code == 200
        assert updated.json()["id"] == relationship["id"]
        assert updated.json()["status"] == "DISMISSED"

        stored = client.get(
            f"/api/v1/incidents/{first['id']}/relationships",
            headers=_auth(worker),
        )
        assert stored.status_code == 200
        assert len(stored.json()) == 1

        citizen_relationships = client.get(
            f"/api/v1/incidents/{first['id']}/relationships",
            headers=_auth(owner),
        )
        assert citizen_relationships.status_code == 200
        assert citizen_relationships.json() == []

    assert db_session.scalar(
        select(func.count()).select_from(IncidentRelationship)
    ) == 1


def test_infrastructure_proximity_and_dependency_impact_foundation(
    db_session: Session,
) -> None:
    citizen = _profile(db_session)
    with _client(db_session) as client:
        incident = _report(client, citizen)
        source = InfrastructureAsset(
            name="Test Drain",
            asset_type=AssetType.DRAIN,
            location="LINESTRING(90.4124 23.8102, 90.4126 23.8104)",
            criticality_score=Decimal("8.0"),
            is_active=True,
            metadata_json={"source": "test"},
        )
        target = InfrastructureAsset(
            name="Test Hospital",
            asset_type=AssetType.HOSPITAL,
            location="POINT(90.4130 23.8110)",
            criticality_score=Decimal("9.0"),
            is_active=True,
            metadata_json={"source": "test"},
        )
        db_session.add_all([source, target])
        db_session.flush()
        db_session.add(
            DependencyEdge(
                source_asset_id=source.id,
                target_asset_id=target.id,
                dependency_type=DependencyType.SERVES,
                strength=Decimal("0.800"),
            )
        )
        db_session.commit()

        response = client.get(
            f"/api/v1/incidents/{incident['id']}/intelligence",
            headers=_auth(citizen),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assets = {item["asset"]["name"]: item for item in body["infrastructure"]}
        assert "Test Drain" in assets
        assert assets["Test Drain"]["dependency_count"] == 1
        assert body["potential_impacts"]
        assert body["potential_impacts"][0]["impact_type"] == (
            "GEOSPATIAL_ASSOCIATION"
        )
        assert any(
            item["impact_type"] == "INFERRED_POTENTIAL"
            for item in body["potential_impacts"]
        )
        assert "not an observed impact" in body["potential_impacts"][-1]["rationale"]

        reference = client.get(
            "/api/v1/infrastructure/assets",
            headers=_auth(citizen),
        )
        assert reference.status_code == 200
        assert any(item["name"] == "Test Drain" for item in reference.json())
        filtered = client.get(
            "/api/v1/infrastructure/assets?asset_type=HOSPITAL",
            headers=_auth(citizen),
        )
        assert filtered.status_code == 200
        assert [item["name"] for item in filtered.json()] == ["Test Hospital"]


def test_old_candidates_are_outside_duplicate_window(db_session: Session) -> None:
    citizen = _profile(db_session)
    with _client(db_session) as client:
        primary = _report(client, citizen)
        old = db_session.get(Incident, uuid.UUID(_report(client, citizen)["id"]))
        assert old is not None
        old.created_at = datetime.now(timezone.utc) - timedelta(days=3)
        db_session.commit()

        response = client.get(
            f"/api/v1/incidents/{primary['id']}/intelligence",
            headers=_auth(citizen),
        )
        assert response.status_code == 200
        assert response.json()["duplicate_candidates"] == []
