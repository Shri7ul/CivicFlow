"""Phase 7 ingestion, alerting, dashboard, and approval tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.jwt import get_token_verifier
from app.ingestion.service import latest_quality
from app.db.session import get_db_session
from app.main import create_app
from app.models import (
    DataQualitySnapshot,
    DataSource,
    IngestedRecord,
    IngestionRun,
    IngestionStatus,
    Profile,
    Role,
)
from tests.auth_support import make_settings, make_token, make_verifier


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
    return {"Authorization": f"Bearer {make_token(sub=profile.id)}"}


def _source(client: TestClient, admin: Profile) -> dict:
    response = client.post(
        "/api/v1/operations/sources",
        headers=_auth(admin),
        json={
            "source_key": "manual-test-feed",
            "name": "Manual test feed",
            "category": "test",
            "access_method": "authorized manual batch",
            "license_note": "Synthetic unit-test fixture only",
            "reliability": "UNVERIFIED",
            "adapter": "manual",
            "freshness_target_minutes": 60,
            "required_fields": ["name"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_ingestion_is_idempotent_and_quality_is_visible(db_session: Session) -> None:
    admin = _profile(db_session, Role.ADMIN, "Admin")
    worker = _profile(db_session, Role.WORKER, "Worker")
    with _client(db_session) as client:
        assert (
            client.post(
                "/api/v1/operations/sources",
                headers=_auth(worker),
                json={
                    "source_key": "forbidden",
                    "name": "Forbidden",
                    "category": "test",
                    "access_method": "manual",
                    "reliability": "UNVERIFIED",
                },
            ).status_code
            == 403
        )
        source = _source(client, admin)
        payload = {
            "idempotency_key": "batch-001",
            "records": [
                {
                    "external_id": "a",
                    "payload": {"name": "Alpha"},
                    "observed_at": "2026-11-24T10:00:00Z",
                    "provenance": {"batch": "unit-fixture"},
                },
                {"external_id": "b", "payload": {}},
                {"external_id": "a", "payload": {"name": "Alpha duplicate"}},
            ],
        }
        first = client.post(
            f"/api/v1/operations/sources/{source['id']}/runs",
            headers=_auth(worker),
            json=payload,
        )
        assert first.status_code == 200, first.text
        body = first.json()
        assert body["run"]["records_received"] == 3
        assert body["run"]["records_valid"] == 2
        assert body["run"]["records_invalid"] == 0
        assert body["run"]["records_duplicate"] == 1
        assert body["quality"]["status"] == "DEGRADED"
        assert body["quality"]["missing_fields"] == 1
        stored = db_session.scalars(
            select(IngestedRecord).where(
                IngestedRecord.source_id == uuid.UUID(source["id"])
            )
        ).all()
        assert len(stored) == 2
        alpha = next(item for item in stored if item.external_id == "a")
        assert alpha.observed_at is not None
        assert alpha.provenance == {"batch": "unit-fixture"}
        second = client.post(
            f"/api/v1/operations/sources/{source['id']}/runs",
            headers=_auth(worker),
            json=payload,
        )
        assert second.status_code == 200, second.text
        assert second.json()["run"]["id"] == body["run"]["id"]
        runs = client.get(
            f"/api/v1/operations/sources/{source['id']}/runs", headers=_auth(worker)
        )
        assert runs.status_code == 200
        assert len(runs.json()) == 1
        quality = client.get("/api/v1/operations/quality", headers=_auth(worker))
        assert quality.status_code == 200
        assert quality.json()[0]["source"]["source_key"] == source["source_key"]
        snapshot = db_session.query(DataQualitySnapshot).one()
        snapshot.coverage = {
            **snapshot.coverage,
            "completed_at": (
                datetime.now(timezone.utc) - timedelta(hours=2)
            ).isoformat(),
        }
        db_session.commit()
        stale = client.get("/api/v1/operations/quality", headers=_auth(worker))
        assert stale.status_code == 200
        assert stale.json()[0]["status"] == "STALE"


def test_alerts_dedupe_notify_and_acknowledge(db_session: Session) -> None:
    admin = _profile(db_session, Role.ADMIN, "Admin")
    worker = _profile(db_session, Role.WORKER, "Worker")
    with _client(db_session) as client:
        rule = client.post(
            "/api/v1/operations/alerts/rules",
            headers=_auth(admin),
            json={
                "name": "Any cell risk",
                "rule_type": "RISK_THRESHOLD",
                "metric": "max_risk_score",
                "operator": ">=",
                "threshold_value": 0,
                "severity": "WARNING",
                "cooldown_minutes": 60,
                "dedupe_window_minutes": 60,
            },
        )
        assert rule.status_code == 201, rule.text
        first = client.post(
            "/api/v1/operations/alerts/evaluate", headers=_auth(worker)
        )
        assert first.status_code == 200, first.text
        assert len(first.json()) == 1
        second = client.post(
            "/api/v1/operations/alerts/evaluate", headers=_auth(worker)
        )
        assert second.status_code == 200
        assert second.json() == []
        notifications = client.get(
            "/api/v1/operations/notifications", headers=_auth(worker)
        )
        assert notifications.status_code == 200
        assert len(notifications.json()) == 1
        alert_id = first.json()[0]["id"]
        acknowledged = client.post(
            f"/api/v1/operations/alerts/{alert_id}/acknowledge",
            headers=_auth(worker),
        )
        assert acknowledged.status_code == 200
        assert acknowledged.json()["status"] == "ACKNOWLEDGED"
        first_ack_at = acknowledged.json()["acknowledged_at"]
        repeat_ack = client.post(
            f"/api/v1/operations/alerts/{alert_id}/acknowledge",
            headers=_auth(worker),
        )
        assert repeat_ack.status_code == 200
        assert repeat_ack.json()["acknowledged_at"] == first_ack_at
        resolved = client.post(
            f"/api/v1/operations/alerts/{alert_id}/resolve",
            headers=_auth(worker),
        )
        assert resolved.status_code == 200
        assert resolved.json()["status"] == "RESOLVED"
        first_resolved_at = resolved.json()["resolved_at"]
        repeat_resolve = client.post(
            f"/api/v1/operations/alerts/{alert_id}/resolve",
            headers=_auth(worker),
        )
        assert repeat_resolve.status_code == 200
        assert repeat_resolve.json()["resolved_at"] == first_resolved_at
        preference = client.put(
            "/api/v1/operations/notification-preferences",
            headers=_auth(worker),
            json={"in_app_enabled": False},
        )
        assert preference.status_code == 200
        assert preference.json()["in_app_enabled"] is False
        dashboard = client.get("/api/v1/operations/dashboard", headers=_auth(worker))
        assert dashboard.status_code == 200, dashboard.text
        data = dashboard.json()
        assert data["safety"]["execution_authorized"] is False
        assert data["health"]["database"] is True
        assert "pending_reviews" in data["planning"]


def test_plan_review_requires_second_admin_and_is_audited(db_session: Session) -> None:
    admin = _profile(db_session, Role.ADMIN, "Admin")
    worker = _profile(db_session, Role.WORKER, "Worker")
    with _client(db_session) as client:
        scenario = client.post(
            "/api/v1/decisions/scenarios",
            headers=_auth(worker),
            json={
                "name": "Reviewable plan",
                "hazard_type": "FLOOD",
                "horizon_minutes": 240,
            },
        )
        assert scenario.status_code == 201, scenario.text
        scenario_id = scenario.json()["id"]
        action = client.post(
            f"/api/v1/decisions/scenarios/{scenario_id}/actions",
            headers=_auth(worker),
            json={
                "title": "Inspect drain",
                "action_type": "INSPECT",
                "duration_minutes": 60,
                "expected_risk_reduction": 5,
            },
        )
        assert action.status_code == 201, action.text
        simulation = client.post(
            f"/api/v1/decisions/scenarios/{scenario_id}/simulate",
            headers=_auth(worker),
            json={"strategy": "BALANCED", "persist": True},
        )
        assert simulation.status_code == 200, simulation.text
        simulation_id = simulation.json()["simulation_id"]
        review = client.post(
            f"/api/v1/decisions/scenarios/{scenario_id}/reviews",
            headers=_auth(worker),
            json={
                "simulation_id": simulation_id,
                "title": "Inspect drain plan",
                "comment": "Please review the planning assumptions.",
            },
        )
        assert review.status_code == 201, review.text
        review_id = review.json()["id"]
        assert review.json()["status"] == "SUBMITTED"
        duplicate = client.post(
            f"/api/v1/decisions/scenarios/{scenario_id}/reviews",
            headers=_auth(worker),
            json={
                "simulation_id": simulation_id,
                "title": "Duplicate review",
                "comment": "Must not create a second active review.",
            },
        )
        assert duplicate.status_code == 409, duplicate.text
        pending = client.get(
            "/api/v1/decisions/reviews/pending", headers=_auth(worker)
        )
        assert pending.status_code == 200
        assert pending.json()[0]["id"] == review_id
        approved = client.post(
            f"/api/v1/decisions/reviews/{review_id}/decision",
            headers=_auth(admin),
            json={"decision": "APPROVED", "comment": "Approved for planning."},
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "APPROVED"
        assert approved.json()["execution_authorized"] is False
        repeated = client.post(
            f"/api/v1/decisions/reviews/{review_id}/decision",
            headers=_auth(admin),
            json={"decision": "REJECTED", "comment": "Must not overwrite approval."},
        )
        assert repeated.status_code == 409, repeated.text
        detail = client.get(
            f"/api/v1/decisions/reviews/{review_id}", headers=_auth(worker)
        )
        assert detail.status_code == 200
        assert len(detail.json()["events"]) == 2
        assert detail.json()["execution_authorized"] is False


def test_ingestion_rejects_oversized_record_payload(db_session: Session) -> None:
    admin = _profile(db_session, Role.ADMIN, "Admin")
    with _client(db_session) as client:
        source = _source(client, admin)
        oversized = client.post(
            f"/api/v1/operations/sources/{source['id']}/runs",
            headers=_auth(admin),
            json={
                "idempotency_key": "oversized-001",
                "records": [
                    {
                        "external_id": "huge",
                        "payload": {"blob": "x" * 40_000},
                    }
                ],
            },
        )
        assert oversized.status_code == 422, oversized.text


def test_failed_ingestion_and_recovered_freshness_are_reported(db_session: Session) -> None:
    admin = _profile(db_session, Role.ADMIN, "Admin")
    with _client(db_session) as client:
        source = _source(client, admin)
        good = client.post(
            f"/api/v1/operations/sources/{source['id']}/runs",
            headers=_auth(admin),
            json={
                "idempotency_key": "quality-good",
                "records": [{"external_id": "ok", "payload": {"name": "Fresh"}}],
            },
        )
        assert good.status_code == 200, good.text
        failed = IngestionRun(
            source_id=uuid.UUID(source["id"]),
            idempotency_key="quality-failure",
            status=IngestionStatus.FAILED,
            completed_at=datetime.now(timezone.utc) + timedelta(seconds=1),
            error_summary="upstream rejected the batch",
        )
        db_session.add(failed)
        db_session.commit()
        quality = client.get("/api/v1/operations/quality", headers=_auth(admin))
        assert quality.status_code == 200, quality.text
        item = quality.json()[0]
        assert item["status"] == "DEGRADED"
        assert any("failed" in issue.lower() for issue in item["issues"])

        # A stale snapshot must not keep reporting its old stale issue after the
        # underlying ingestion timestamp is refreshed.
        db_source = db_session.get(DataSource, uuid.UUID(source["id"]))
        db_source.freshness_target_minutes = 1
        db_session.commit()
        snapshot = latest_quality(db_session, uuid.UUID(source["id"]))
        assert snapshot is not None
        snapshot.coverage = {
            **snapshot.coverage,
            "completed_at": (
                datetime.now(timezone.utc) - timedelta(minutes=5)
            ).isoformat(),
        }
        failed.completed_at = datetime.now(timezone.utc) - timedelta(minutes=6)
        db_session.commit()
        stale = client.get("/api/v1/operations/quality", headers=_auth(admin)).json()[0]
        assert stale["status"] == "STALE"
        assert any("minutes old" in issue for issue in stale["issues"])
        snapshot.coverage = {
            **snapshot.coverage,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        db_session.commit()
        recovered = client.get("/api/v1/operations/quality", headers=_auth(admin)).json()[0]
        assert recovered["status"] == "HEALTHY"
        assert not any("minutes old" in issue for issue in recovered["issues"])
