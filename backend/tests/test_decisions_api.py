"""Decision scenario API, authorization, and persistence tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import h3
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.jwt import get_token_verifier
from app.db.session import get_db_session
from app.main import create_app
from app.models import DecisionSimulation, Profile, Role
from tests.auth_support import make_settings, make_token, make_verifier

CELL = h3.latlng_to_cell(23.8103, 90.4125, 8)


def _profile(session: Session, *, role: Role, name: str) -> Profile:
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


def _scenario(client: TestClient, worker: Profile) -> dict:
    response = client.post(
        "/api/v1/decisions/scenarios",
        headers=_auth(worker),
        json={
            "name": "Monsoon drain failure",
            "description": "Planning exercise only.",
            "hazard_type": "FLOOD",
            "horizon_minutes": 240,
            "budget_limit": 500,
            "resolution": 8,
            "risk_window_hours": 168,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _resource(
    client: TestClient,
    worker: Profile,
    *,
    name: str = "Drain crew",
    status: str = "PLANNING_ASSUMPTION",
    quantity: float = 2,
) -> dict:
    response = client.post(
        "/api/v1/decisions/resources",
        headers=_auth(worker),
        json={
            "name": name,
            "resource_type": "PERSONNEL",
            "unit": "crew",
            "quantity_available": quantity,
            "availability_status": status,
            "availability_source": "unit-test planning assumption",
            "available_as_of": datetime.now(timezone.utc).isoformat(),
            "allocation_mode": "SHARED_CAPACITY",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_decision_apis_are_staff_only(db_session: Session) -> None:
    citizen = _profile(db_session, role=Role.CITIZEN, name="Citizen")
    worker = _profile(db_session, role=Role.WORKER, name="Worker")
    with _client(db_session) as client:
        assert (
            client.get(
                "/api/v1/decisions/scenarios", headers=_auth(citizen)
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/v1/decisions/scenarios",
                headers=_auth(citizen),
                json={"name": "No", "hazard_type": "FLOOD"},
            ).status_code
            == 403
        )
        assert (
            client.get(
                "/api/v1/decisions/resources", headers=_auth(worker)
            ).status_code
            == 200
        )
        assert (
            client.get(
                "/api/v1/decisions/config", headers=_auth(worker)
            ).status_code
            == 200
        )


def test_resource_availability_requires_explicit_provenance(
    db_session: Session,
) -> None:
    worker = _profile(db_session, role=Role.WORKER, name="Worker")
    with _client(db_session) as client:
        missing = client.post(
            "/api/v1/decisions/resources",
            headers=_auth(worker),
            json={
                "name": "Unverified truck",
                "resource_type": "VEHICLE",
                "unit": "vehicle",
                "quantity_available": 3,
                "availability_status": "AVAILABLE",
            },
        )
        assert missing.status_code == 422, missing.text
        unknown = client.post(
            "/api/v1/decisions/resources",
            headers=_auth(worker),
            json={
                "name": "Unknown crew",
                "resource_type": "PERSONNEL",
                "unit": "crew",
                "quantity_available": 0,
                "availability_status": "UNKNOWN",
            },
        )
        assert unknown.status_code == 201, unknown.text
        assumption = _resource(client, worker)
        assert assumption["availability_status"] == "PLANNING_ASSUMPTION"
        assert assumption["availability_source"]


def test_simulation_is_planning_only_and_blocks_unknown_resources(
    db_session: Session,
) -> None:
    worker = _profile(db_session, role=Role.WORKER, name="Worker")
    with _client(db_session) as client:
        scenario = _scenario(client, worker)
        unknown = client.post(
            "/api/v1/decisions/resources",
            headers=_auth(worker),
            json={
                "name": "Unverified crew",
                "resource_type": "PERSONNEL",
                "unit": "crew",
                "quantity_available": 0,
                "availability_status": "UNKNOWN",
            },
        ).json()
        action = client.post(
            f"/api/v1/decisions/scenarios/{scenario['id']}/actions",
            headers=_auth(worker),
            json={
                "title": "Clear blocked drain",
                "action_type": "CLEAN",
                "target_h3_cell_id": CELL,
                "priority": 5,
                "duration_minutes": 60,
                "expected_risk_reduction": 25,
                "estimated_cost": 100,
                "resource_requirements": [
                    {"resource_id": unknown["id"], "quantity_required": 1}
                ],
            },
        )
        assert action.status_code == 201, action.text
        simulation = client.post(
            f"/api/v1/decisions/scenarios/{scenario['id']}/simulate",
            headers=_auth(worker),
            json={"strategy": "PRIORITY", "persist": True},
        )
        assert simulation.status_code == 200, simulation.text
        body = simulation.json()
        assert body["status"] == "COMPLETED"
        assert body["plan"]["execution_authorized"] is False
        assert body["plan"]["dispatch_performed"] is False
        assert body["plan"]["reservations_created"] is False
        assert body["plan"]["actions"][0]["status"] == "BLOCKED"
        assert body["plan"]["actions"][0]["reasons"] == [
            "resource_availability_unknown"
        ]
        assert body["simulation_id"] is not None
        stored = db_session.scalars(
            select(DecisionSimulation).where(
                DecisionSimulation.id == uuid.UUID(body["simulation_id"])
            )
        ).one()
        assert stored.result["plan"]["dispatch_performed"] is False
        assert stored.requested_by == worker.id
        listed = client.get(
            f"/api/v1/decisions/scenarios/{scenario['id']}/simulations",
            headers=_auth(worker),
        )
        assert listed.status_code == 200
        assert len(listed.json()) == 1
        detail = client.get(
            f"/api/v1/decisions/scenarios/{scenario['id']}/simulations/{body['simulation_id']}",
            headers=_auth(worker),
        )
        assert detail.status_code == 200
        assert detail.json()["reservations_created"] is False


def test_known_assumption_resources_schedule_and_compare(
    db_session: Session,
) -> None:
    worker = _profile(db_session, role=Role.WORKER, name="Worker")
    with _client(db_session) as client:
        scenario = _scenario(client, worker)
        resource = _resource(client, worker, quantity=1)
        for title, priority, reduction, cost in (
            ("Inspect", 5, 20, 100),
            ("Repair", 3, 30, 200),
        ):
            response = client.post(
                f"/api/v1/decisions/scenarios/{scenario['id']}/actions",
                headers=_auth(worker),
                json={
                    "title": title,
                    "action_type": "INSPECT" if title == "Inspect" else "REPAIR",
                    "target_h3_cell_id": CELL,
                    "priority": priority,
                    "duration_minutes": 60,
                    "expected_risk_reduction": reduction,
                    "estimated_cost": cost,
                    "resource_requirements": [
                        {
                            "resource_id": resource["id"],
                            "quantity_required": 1,
                        }
                    ],
                },
            )
            assert response.status_code == 201, response.text
        simulation = client.post(
            f"/api/v1/decisions/scenarios/{scenario['id']}/simulate",
            headers=_auth(worker),
            json={"strategy": "BALANCED"},
        )
        assert simulation.status_code == 200, simulation.text
        body = simulation.json()
        assert body["plan"]["metrics"]["scheduled_actions"] >= 1
        assert any(
            "planning assumption" in assumption.lower()
            for assumption in body["assumptions"]
        )
        compare = client.post(
            f"/api/v1/decisions/scenarios/{scenario['id']}/compare",
            headers=_auth(worker),
            json={
                "strategies": [
                    "PRIORITY",
                    "RISK_REDUCTION",
                    "COST_EFFICIENT",
                    "BALANCED",
                ]
            },
        )
        assert compare.status_code == 200, compare.text
        comparison = compare.json()["comparison"]
        assert comparison["execution_authorized"] is False
        assert len(comparison["results"]) == 4
        assert comparison["winner"] in {
            "PRIORITY",
            "RISK_REDUCTION",
            "COST_EFFICIENT",
            "BALANCED",
        }
        detail = client.get(
            f"/api/v1/decisions/scenarios/{scenario['id']}",
            headers=_auth(worker),
        )
        assert detail.status_code == 200
        assert len(detail.json()["actions"]) == 2


def test_action_validation_rejects_bad_targets_and_dependencies(
    db_session: Session,
) -> None:
    worker = _profile(db_session, role=Role.WORKER, name="Worker")
    with _client(db_session) as client:
        scenario = _scenario(client, worker)
        bad_cell = client.post(
            f"/api/v1/decisions/scenarios/{scenario['id']}/actions",
            headers=_auth(worker),
            json={
                "title": "Bad target",
                "action_type": "REPAIR",
                "target_h3_cell_id": "not-h3",
            },
        )
        assert bad_cell.status_code == 422
        first = client.post(
            f"/api/v1/decisions/scenarios/{scenario['id']}/actions",
            headers=_auth(worker),
            json={"title": "First", "action_type": "INSPECT"},
        ).json()
        self_dependency = client.patch(
            f"/api/v1/decisions/scenarios/{scenario['id']}/actions/{first['id']}",
            headers=_auth(worker),
            json={"depends_on_action_id": first["id"]},
        )
        assert self_dependency.status_code == 422
