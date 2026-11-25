"""Phase 10 governance contracts, lifecycle and honest-readiness tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.governance.pilots as pilot_service
from app.auth.dependencies import get_token_verifier
from app.db.session import get_db_session
from app.main import create_app
from app.models import (
    CorrelationDecision,
    CorrelationUniverse,
    Incident,
    IncidentCategory,
    IncidentSeverity,
    ProvenanceKind,
    InfrastructureValidationStatus,
    ModelVersion,
    Pilot,
    PilotStatus,
    Profile,
    ReadinessStatus,
    RiskCategory,
    RiskCellSnapshot,
    RiskModelRun,
    RiskReviewCase,
    RiskReviewEvent,
    Role,
)
from app.models.decision import DecisionScenario, DecisionSimulation
from app.models.enums import (
    DecisionStrategy,
    ScenarioHazard,
    SimulationStatus,
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
    app.dependency_overrides[get_token_verifier] = lambda: make_verifier(
        make_settings()
    )
    return TestClient(app)


def _auth(profile: Profile, email: str | None = None) -> dict[str, str]:
    return {
        "Authorization": "Bearer "
        + make_token(sub=profile.id, email=email or f"{profile.id}@example.com")
    }


def _when(days: int = 1) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _pilot_payload(owner_id: uuid.UUID | None = None) -> dict:
    return {
        "pilot_key": f"pilot-{uuid.uuid4().hex[:10]}",
        "name": "Brooklyn drainage controlled pilot",
        "description": "Read-only evaluation of drainage risk review workflows.",
        "mode": "SIMULATION",
        "region": "Brooklyn, New York",
        "bbox": [40.55, -74.05, 40.74, -73.83],
        "start_date": _when(-1),
        "end_date": _when(30),
        "eligible_categories": ["DRAINAGE"],
        "evaluation_protocol": (
            "Compare reviewed risk scores with the active baseline and record "
            "every reviewer decision without changing model outputs."
        ),
        "operational_restrictions": ["No dispatch", "No public alerts"],
        "data_sources": ["NYC 311 sample"],
        "evaluation_criteria": ["Coverage >= 90%", "Two independent reviewers"],
        "owner_id": str(owner_id) if owner_id else None,
    }


def _run(session: Session, admin: Profile, *, version: str = "risk-v1") -> RiskModelRun:
    now = datetime.now(timezone.utc)
    run = RiskModelRun(
        model_version=version,
        config_hash="a" * 64,
        resolution=8,
        window_hours=168,
        window_start=now - timedelta(days=7),
        window_end=now,
        incident_count=4,
        cell_count=1,
        duration_ms=12,
        query_parameters={"dataset_key": "nyc311-test"},
        requested_by=admin.id,
    )
    session.add(run)
    session.commit()
    return run


def _cell(session: Session, run: RiskModelRun, h3: str = "882a100d2dfffff") -> RiskCellSnapshot:
    cell = RiskCellSnapshot(
        run_id=run.id,
        h3_cell_id=h3,
        resolution=8,
        boundary="POLYGON((0 0,0 1,1 1,1 0,0 0))",
        risk_score=Decimal("72.50"),
        incident_activity_score=Decimal("65.00"),
        risk_category=RiskCategory.HIGH,
        confidence=Decimal("0.800"),
        incident_count=3,
        active_count=1,
        adjusted_incident_count=3,
        factor_contributions=[
            {
                "key": "incident_activity",
                "label": "Incident activity",
                "contribution": 45.0,
                "available": True,
                "explanation": "Three incidents in the window.",
            },
            {
                "key": "drainage_exposure",
                "label": "Drainage exposure",
                "contribution": 5.0,
                "available": False,
                "explanation": "No verified drainage asset data.",
            },
        ],
        model_version=run.model_version,
        config_hash=run.config_hash,
    )
    session.add(cell)
    session.commit()
    return cell


def _incident(session: Session, reporter: Profile, title: str) -> Incident:
    incident = Incident(
        title=title,
        description="Synthetic labelled fixture for correlation review tests.",
        category=IncidentCategory.DRAINAGE,
        severity=IncidentSeverity.MEDIUM,
        status="OPEN",
        location="POINT(-73.95 40.65)",
        reporter_id=reporter.id,
    )
    session.add(incident)
    session.commit()
    return incident


def _approved_pilot(session: Session, client: TestClient) -> tuple[Pilot, Profile, Profile, Profile]:
    creator = _profile(session, Role.ADMIN, "Creator Admin")
    reviewer = _profile(session, Role.ADMIN, "Approving Admin")
    activator = _profile(session, Role.ADMIN, "Activation Admin")
    created = client.post(
        "/api/v1/governance/pilots",
        json=_pilot_payload(owner_id=creator.id),
        headers=_auth(creator),
    )
    assert created.status_code == 201, created.text
    pilot_id = created.json()["id"]
    assert client.post(
        f"/api/v1/governance/pilots/{pilot_id}/reviewers",
        json={"profile_id": str(reviewer.id), "role": "REVIEWER"},
        headers=_auth(creator),
    ).status_code == 201
    assert client.post(
        f"/api/v1/governance/pilots/{pilot_id}/transition",
        json={"action": "SUBMIT"},
        headers=_auth(creator),
    ).status_code == 200
    approved = client.post(
        f"/api/v1/governance/pilots/{pilot_id}/transition",
        json={"action": "APPROVE", "note": "Protocol and restrictions reviewed."},
        headers=_auth(reviewer),
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"
    return session.get(Pilot, uuid.UUID(pilot_id)), creator, reviewer, activator


def test_pilot_lifecycle_enforces_separation_and_readiness(db_session: Session) -> None:
    with _client(db_session) as client:
        creator = _profile(db_session, Role.ADMIN, "Creator Admin")
        reviewer = _profile(db_session, Role.ADMIN, "Approving Admin")
        activator = _profile(db_session, Role.ADMIN, "Activation Admin")
        response = client.post(
            "/api/v1/governance/pilots",
            json=_pilot_payload(owner_id=creator.id),
            headers=_auth(creator),
        )
        assert response.status_code == 201, response.text
        pilot_id = response.json()["id"]
        assert response.json()["status"] == "DRAFT"
        assert client.post(
            f"/api/v1/governance/pilots/{pilot_id}/reviewers",
            json={"profile_id": str(reviewer.id), "role": "REVIEWER"},
            headers=_auth(creator),
        ).status_code == 201
        assert client.post(
            f"/api/v1/governance/pilots/{pilot_id}/transition",
            json={"action": "SUBMIT"},
            headers=_auth(creator),
        ).status_code == 200
        missing_reason = client.post(
            f"/api/v1/governance/pilots/{pilot_id}/transition",
            json={"action": "REJECT"},
            headers=_auth(reviewer),
        )
        assert missing_reason.status_code == 400
        assert missing_reason.json()["error"]["code"] == "note_required"
        self_approval = client.post(
            f"/api/v1/governance/pilots/{pilot_id}/transition",
            json={"action": "APPROVE"},
            headers=_auth(creator),
        )
        assert self_approval.status_code == 403
        assert self_approval.json()["error"]["code"] == "separation_of_duties"
        approved = client.post(
            f"/api/v1/governance/pilots/{pilot_id}/transition",
            json={"action": "APPROVE"},
            headers=_auth(reviewer),
        )
        assert approved.status_code == 200
        same_approver = client.post(
            f"/api/v1/governance/pilots/{pilot_id}/transition",
            json={"action": "ACTIVATE"},
            headers=_auth(reviewer),
        )
        assert same_approver.status_code == 403
        assert same_approver.json()["error"]["code"] == "separation_of_duties"
        blocked = client.post(
            f"/api/v1/governance/pilots/{pilot_id}/transition",
            json={"action": "ACTIVATE"},
            headers=_auth(activator),
        )
        assert blocked.status_code == 409
        assert blocked.json()["error"]["code"] == "readiness_not_met"
        assert db_session.get(Pilot, uuid.UUID(pilot_id)).status == PilotStatus.APPROVED


def test_activation_uses_independent_readiness_when_gates_pass(
    db_session: Session, monkeypatch
) -> None:
    with _client(db_session) as client:
        pilot, _, reviewer, activator = _approved_pilot(db_session, client)
        monkeypatch.setattr(
            pilot_service,
            "assess_readiness",
            lambda session, pilot=None: {
                "overall": "READY_FOR_CONTROLLED_PILOT",
                "ready_for_activation": True,
                "categories": [],
                "activation_blockers": [],
            },
        )
        # Phase 14 adds a second, independent server-side gate. This test
        # exercises Phase 10 transition mechanics; the real Phase 14 gate is
        # covered by its own adversarial tests in test_phase14_pilot.py.
        monkeypatch.setattr(
            "app.phase14.readiness.assess_phase14_readiness",
            lambda session, pilot=None: {
                "protocol": "phase14-final-gate-v1",
                "overall": "READY_FOR_CONTROLLED_PILOT",
                "ready_for_activation": True,
                "blockers": [],
            },
        )
        response = client.post(
            f"/api/v1/governance/pilots/{pilot.id}/transition",
            json={"action": "ACTIVATE"},
            headers=_auth(activator),
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "ACTIVE"
        assert response.json()["activated_by"] == str(activator.id)
        again = client.post(
            f"/api/v1/governance/pilots/{pilot.id}/transition",
            json={"action": "RESUME"},
            headers=_auth(activator),
        )
        assert again.status_code == 409


def test_risk_review_never_changes_assessment_and_is_audited(
    db_session: Session,
) -> None:
    admin = _profile(db_session, Role.ADMIN, "Admin")
    worker = _profile(db_session, Role.WORKER, "Reviewer")
    other = _profile(db_session, Role.WORKER, "Other Reviewer")
    run = _run(db_session, admin)
    cell = _cell(db_session, run)
    before = (cell.risk_score, cell.confidence, dict(cell.factor_contributions[0]))
    with _client(db_session) as client:
        created = client.post(
            "/api/v1/governance/reviews",
            json={
                "run_id": str(run.id),
                "cell_id": str(cell.id),
                "assigned_reviewer_id": str(worker.id),
            },
            headers=_auth(worker),
        )
        assert created.status_code == 201, created.text
        case_id = created.json()["id"]
        assert created.json()["status"] == "UNREVIEWED"
        assert created.json()["review_disclaimer"]
        unauthorized = client.post(
            f"/api/v1/governance/reviews/{case_id}/decisions",
            json={"status": "ACCEPTED", "note": "Looks plausible."},
            headers=_auth(other),
        )
        assert unauthorized.status_code == 403
        accepted = client.post(
            f"/api/v1/governance/reviews/{case_id}/decisions",
            json={"status": "ACCEPTED", "note": "Evidence and factors checked."},
            headers=_auth(worker, "reviewer@example.com"),
        )
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["status"] == "ACCEPTED"
        assert accepted.json()["events"][-1]["actor_email"] == "reviewer@example.com"
        db_session.expire_all()
        persisted = db_session.get(RiskCellSnapshot, cell.id)
        assert persisted is not None
        assert (persisted.risk_score, persisted.confidence) == before[:2]
        assert persisted.factor_contributions[0] == before[2]
        assert len(accepted.json()["events"]) == 2
        # Final states may only reopen through IN_REVIEW.
        invalid = client.post(
            f"/api/v1/governance/reviews/{case_id}/decisions",
            json={"status": "ACCEPTED", "note": "Second final vote."},
            headers=_auth(worker),
        )
        assert invalid.status_code == 409
        reopened = client.post(
            f"/api/v1/governance/reviews/{case_id}/decisions",
            json={"status": "IN_REVIEW", "note": "Reopening for a second look."},
            headers=_auth(worker),
        )
        assert reopened.status_code == 200
        events = client.get(
            f"/api/v1/governance/reviews/{case_id}/events", headers=_auth(admin)
        )
        assert events.status_code == 200
        assert len(events.json()["items"]) == 3
        assert db_session.scalar(
            select(RiskReviewEvent).where(RiskReviewEvent.case_id == uuid.UUID(case_id))
        ) is not None
        assert db_session.scalar(
            select(RiskReviewCase).where(RiskReviewCase.id == uuid.UUID(case_id))
        ).status.value == "IN_REVIEW"


def test_correlation_metrics_are_honest_about_missing_labels(
    db_session: Session,
) -> None:
    admin = _profile(db_session, Role.ADMIN, "Admin")
    reviewer = _profile(db_session, Role.WORKER, "Reviewer")
    incidents = [
        _incident(db_session, admin, f"Synthetic {name}") for name in "ABCD"
    ]
    universe = CorrelationUniverse(
        universe_key="synthetic-test",
        name="Synthetic correlation fixture",
        version="fixture-v1",
        provenance_kind=ProvenanceKind.SYNTHETIC,
        reference_complete=True,
        reference_size=2,
        reference_note="Labelled synthetic fixture universe.",
        candidate_method="token-cosine",
        candidate_method_version="corr-v1",
        created_by=admin.id,
    )
    db_session.add(universe)
    db_session.commit()
    with _client(db_session) as client:
        missing_provenance = client.post(
            "/api/v1/governance/correlation/candidates",
            json={
                "source_incident_id": str(incidents[0].id),
                "target_incident_id": str(incidents[1].id),
                "similarity_score": 0.91,
                "method": "token-cosine",
                "method_version": "corr-v1",
                "universe_key": "synthetic-test",
            },
            headers=_auth(admin),
        )
        assert missing_provenance.status_code == 422
        created = []
        for source, target in ((incidents[0], incidents[1]), (incidents[2], incidents[3])):
            response = client.post(
                "/api/v1/governance/correlation/candidates",
                json={
                    "source_incident_id": str(source.id),
                    "target_incident_id": str(target.id),
                    "similarity_score": 0.91,
                    "method": "token-cosine",
                    "method_version": "corr-v1",
                    "universe_key": "synthetic-test",
                    "universe_reference_complete": True,
                    "reference_universe_size": 2,
                    "reference_note": "Labelled synthetic fixture universe.",
                    "synthetic_fixture": True,
                },
                headers=_auth(admin),
            )
            assert response.status_code == 201, response.text
            assert response.json()["synthetic_fixture"] is True
            created.append(response.json()["id"])
        first = client.post(
            f"/api/v1/governance/correlation/candidates/{created[0]}/reviews",
            json={"decision": "DUPLICATE", "explanation": "Same location and issue."},
            headers=_auth(reviewer, "reviewer@example.com"),
        )
        assert first.status_code == 201, first.text
        duplicate_vote = client.post(
            f"/api/v1/governance/correlation/candidates/{created[0]}/reviews",
            json={"decision": "NOT_DUPLICATE"},
            headers=_auth(reviewer),
        )
        assert duplicate_vote.status_code == 409
        partial = client.get(
            "/api/v1/governance/correlation/metrics?universe_key=synthetic-test",
            headers=_auth(admin),
        ).json()
        assert partial["metrics"]["recall"] is None
        assert partial["confusion_matrix"]["true_negative"] is None
        assert partial["confusion_matrix"]["false_negative"] is None
        assert partial["reference"]["recall_reason"]
        second = client.post(
            f"/api/v1/governance/correlation/candidates/{created[1]}/reviews",
            json={"decision": "NOT_DUPLICATE", "explanation": "Different culvert."},
            headers=_auth(reviewer),
        )
        assert second.status_code == 201
        complete = client.get(
            "/api/v1/governance/correlation/metrics?universe_key=synthetic-test",
            headers=_auth(admin),
        ).json()
        assert complete["metrics"] == {"precision": 0.5, "recall": 0.5, "f1": 0.5}
        assert complete["confusion_matrix"] == {
            "true_positive": 1,
            "false_positive": 1,
            "false_negative": 1,
            "true_negative": None,
        }
        assert complete["is_validated_ground_truth"] is False
        assert complete["is_simulated"] is True
        assert complete["synthetic_provenance"] == "SYNTHETIC"
        assert complete["reference"]["complete"] is True
        db_session.delete(universe)
        db_session.commit()
        unattested = client.get(
            "/api/v1/governance/correlation/metrics?universe_key=synthetic-test",
            headers=_auth(admin),
        ).json()
        assert unattested["metrics"]["recall"] is None
        assert "no registered reference universe" in unattested["reference"]["recall_reason"]


def test_infrastructure_registry_requires_metadata_before_verification(
    db_session: Session,
) -> None:
    admin = _profile(db_session, Role.ADMIN, "Admin")
    worker = _profile(db_session, Role.WORKER, "Worker")
    payload = {
        "source_key": "nyc-dot-roads",
        "name": "NYC DOT road centreline",
        "category": "ROADS",
        "source_url": "https://example.gov/roads",
        "provider": "NYC DOT",
        "license_note": "Public domain, metadata review only.",
        "retrieved_at": _when(-2),
        "dataset_version": "2025-01",
        "geographic_coverage": "New York City",
        "crs": "EPSG:4326",
        "schema_version": "1.0",
        "snapshot_sha256": "b" * 64,
        "update_frequency": "Quarterly",
        "metadata": {"rows": 100, "note": "sample metadata only"},
    }
    with _client(db_session) as client:
        assert client.post(
            "/api/v1/governance/infrastructure/sources",
            json=payload,
            headers=_auth(worker),
        ).status_code == 403
        created = client.post(
            "/api/v1/governance/infrastructure/sources",
            json=payload,
            headers=_auth(admin),
        )
        assert created.status_code == 201, created.text
        assert created.json()["validation_status"] == "PENDING"
        assert created.json()["asset_data"] is None
        source_id = created.json()["id"]
        verified = client.post(
            f"/api/v1/governance/infrastructure/sources/{source_id}/validation",
            json={"status": "VERIFIED", "note": "License and coverage checked."},
            headers=_auth(admin),
        )
        assert verified.status_code == 200, verified.text
        assert verified.json()["validation_status"] == "VERIFIED"
        assert len(verified.json()["events"]) == 2
        coverage = client.get(
            "/api/v1/governance/infrastructure/coverage", headers=_auth(worker)
        ).json()
        assert coverage["verified_domains"] == 1
        assert coverage["asset_data_available"] is False
        incomplete_payload = {
            **payload,
            "source_key": "nyc-bridges",
            "category": "BRIDGES",
            "snapshot_sha256": None,
        }
        incomplete = client.post(
            "/api/v1/governance/infrastructure/sources",
            json=incomplete_payload,
            headers=_auth(admin),
        )
        assert incomplete.status_code == 201
        blocked = client.post(
            f"/api/v1/governance/infrastructure/sources/{incomplete.json()['id']}/validation",
            json={"status": "VERIFIED", "note": "Attempt without a checksum."},
            headers=_auth(admin),
        )
        assert blocked.status_code == 409
        assert blocked.json()["error"]["code"] == "source_metadata_incomplete"


def test_readiness_is_not_ready_without_evidence(db_session: Session) -> None:
    admin = _profile(db_session, Role.ADMIN, "Admin")
    worker = _profile(db_session, Role.WORKER, "Worker")
    with _client(db_session) as client:
        scorecard = client.get(
            "/api/v1/governance/readiness", headers=_auth(worker)
        )
        assert scorecard.status_code == 200
        body = scorecard.json()
        assert body["overall"] == "NOT_READY"
        assert body["ready_for_activation"] is False
        assert len(body["categories"]) == 16
        assert body["counts"]["mandatory_total"] == 12
        assert body["counts"]["advisory_total"] == 4
        assert body["activation_blockers"]
        derived = client.post(
            "/api/v1/governance/readiness/evidence",
            json={
                "category": "data_quality",
                "criterion_key": "data_quality.manual",
                "status": "PASS",
                "evidence": "A manually asserted pass that must be refused.",
                "evidence_refs": ["doc-1"],
            },
            headers=_auth(admin),
        )
        assert derived.status_code == 422
        manual = client.post(
            "/api/v1/governance/readiness/evidence",
            json={
                "category": "security",
                "criterion_key": "security.access_review",
                "status": "PASS",
                "evidence": "Quarterly access review completed and signed off.",
                "evidence_refs": ["security-review-2025-q1"],
            },
            headers=_auth(admin),
        )
        assert manual.status_code == 201, manual.text
        still = client.get(
            "/api/v1/governance/readiness", headers=_auth(worker)
        ).json()
        assert still["overall"] == "NOT_READY"
        security = next(
            item for item in still["categories"] if item["key"] == "security"
        )
        assert security["status"] == "PASS"
        assert security["mandatory"] is False


def test_traceability_links_configuration_inputs_factors_reviews_and_export(
    db_session: Session,
) -> None:
    admin = _profile(db_session, Role.ADMIN, "Admin")
    worker = _profile(db_session, Role.WORKER, "Reviewer")
    run = _run(db_session, admin)
    cell = _cell(db_session, run)
    db_session.add(
        ModelVersion(
            model_name="risk",
            version=run.model_version,
            config={"weights": {"incident_activity": 0.6}},
            config_hash=run.config_hash,
            description="Fixture risk configuration.",
            is_active=True,
        )
    )
    db_session.commit()
    with _client(db_session) as client:
        case = client.post(
            "/api/v1/governance/reviews",
            json={"run_id": str(run.id), "cell_id": str(cell.id)},
            headers=_auth(worker),
        )
        assert case.status_code == 201
        trace = client.get(
            f"/api/v1/governance/traceability/runs/{run.id}", headers=_auth(worker)
        )
        assert trace.status_code == 200, trace.text
        body = trace.json()
        assert body["assessment"]["id"] == str(run.id)
        assert body["model_configuration"]["found"] is True
        assert body["model_configuration"]["config_hash_matches"] is True
        assert body["model_configuration"]["active_matches_run"] is True
        assert body["inputs"]["source_datasets"] == ["nyc311-test"]
        assert body["provenance"]["complete"] is True
        assert body["reviews"]["case_count"] == 1
        assert len(body["spatial_units"]["cells"]) == 1
        factors = {item["key"]: item for item in body["factor_contributions"]}
        assert factors["incident_activity"]["mean_contribution"] == 45.0
        assert factors["drainage_exposure"]["available_share"] == 0.0
        listed = client.get(
            "/api/v1/governance/traceability/runs", headers=_auth(worker)
        ).json()
        assert listed["items"][0]["review_cases"] == 1
        export = client.get(
            f"/api/v1/governance/traceability/runs/{run.id}/export",
            headers=_auth(worker),
        )
        assert export.status_code == 200
        assert "attachment" in export.headers["content-disposition"]
        assert export.headers["x-content-type-options"] == "nosniff"
        assert body["reviews"]["review_decision_distinct_from_prediction"] is True


def test_simulation_audit_labels_results_and_refuses_execution_claims(
    db_session: Session,
) -> None:
    admin = _profile(db_session, Role.ADMIN, "Admin")
    scenario = DecisionScenario(
        name="Synthetic flood planning scenario",
        description="Synthetic fixture, not an emergency instruction.",
        hazard_type=ScenarioHazard.FLOOD,
        parameters={"rainfall_mm": 30},
        horizon_minutes=1440,
        resolution=8,
        risk_window_hours=168,
        status="DRAFT",
        created_by=admin.id,
    )
    db_session.add(scenario)
    db_session.flush()
    simulation = DecisionSimulation(
        scenario_id=scenario.id,
        strategy=DecisionStrategy.BALANCED,
        status=SimulationStatus.COMPLETED,
        model_version="decision-v1",
        config_hash="c" * 64,
        assumptions={"risk_context": {"available": True, "cell_count": 1}},
        solver={"algorithm": "greedy", "time_limit_ms": 5000},
        result={
            "objective_score": 0.5,
            "objective_components": {"risk_reduction": 0.4},
            "metrics": {"budget_limit": 1000},
            "actions": [],
            "resources": [],
            "assumptions": ["Planner-supplied expected reductions."],
            "solver": {"algorithm": "greedy", "time_limit_ms": 5000},
            "warnings": [],
            "limitations": [],
            "execution_authorized": False,
            "dispatch_performed": False,
            "reservations_created": False,
        },
        duration_ms=3,
        requested_by=admin.id,
    )
    db_session.add(simulation)
    db_session.commit()
    with _client(db_session) as client:
        response = client.get(
            "/api/v1/governance/simulation/audit", headers=_auth(admin)
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["execution_authorized"] is False
        assert body["summary"]["simulations"] == 1
        item = body["simulations"][0]
        assert item["simulation_label"] == "SIMULATED"
        assert item["dispatch_permitted"] is False
        checks = {check["key"]: check["status"] for check in item["checks"]}
        assert checks["no_execution_side_effects"] == "PASS"
        assert checks["unknown_resources_preserved"] == "NOT_APPLICABLE"
        assert checks["human_review"] == "FAIL"
        assert item["validation_status"] == "FAIL"


def test_phase10_routes_require_staff_and_bounded_pagination(
    db_session: Session,
) -> None:
    citizen = _profile(db_session, Role.CITIZEN, "Citizen")
    worker = _profile(db_session, Role.WORKER, "Worker")
    with _client(db_session) as client:
        assert client.get("/api/v1/governance/pilots").status_code == 401
        assert client.get(
            "/api/v1/governance/readiness", headers=_auth(citizen)
        ).status_code == 403
        assert client.get(
            "/api/v1/governance/reviews?limit=101", headers=_auth(worker)
        ).status_code == 422
        assert client.get(
            "/api/v1/governance/reviews?offset=-1", headers=_auth(worker)
        ).status_code == 422
        assert client.post(
            "/api/v1/governance/pilots",
            json=_pilot_payload(),
            headers=_auth(worker),
        ).status_code == 403
        assert client.get(
            "/api/v1/governance/pilots", headers=_auth(worker)
        ).status_code == 200

def test_phase10_rejects_identity_spoofing_and_enforces_review_ownership(
    db_session: Session,
) -> None:
    creator = _profile(db_session, Role.ADMIN, "Creator Admin")
    other_worker = _profile(db_session, Role.WORKER, "Other Reviewer")
    assigned = _profile(db_session, Role.WORKER, "Assigned Reviewer")
    run = _run(db_session, creator)
    cell = _cell(db_session, run)

    with _client(db_session) as client:
        spoofed = _pilot_payload(owner_id=creator.id)
        spoofed.update(
            {
                "status": "ACTIVE",
                "created_by": str(creator.id),
                "approved_by": str(creator.id),
            }
        )
        rejected = client.post(
            "/api/v1/governance/pilots",
            json=spoofed,
            headers=_auth(creator),
        )
        assert rejected.status_code == 422
        assert rejected.json()["error"]["code"] == "validation_error"

        case = client.post(
            "/api/v1/governance/reviews",
            json={
                "run_id": str(run.id),
                "cell_id": str(cell.id),
                "assigned_reviewer_id": str(assigned.id),
            },
            headers=_auth(creator),
        )
        assert case.status_code == 201, case.text
        case_id = case.json()["id"]

        impersonated = client.post(
            f"/api/v1/governance/reviews/{case_id}/decisions",
            json={
                "status": "ACCEPTED",
                "note": "Checked the cell score.",
                "reviewer_id": str(assigned.id),
            },
            headers=_auth(assigned),
        )
        assert impersonated.status_code == 422

        not_owner = client.post(
            f"/api/v1/governance/reviews/{case_id}/decisions",
            json={"status": "ACCEPTED", "note": "Trying another reviewer case."},
            headers=_auth(other_worker),
        )
        assert not_owner.status_code == 403
        assert not_owner.json()["error"]["code"] == "reviewer_not_assigned"

        missing_note = client.post(
            f"/api/v1/governance/reviews/{case_id}/decisions",
            json={"status": "REJECTED"},
            headers=_auth(assigned),
        )
        assert missing_note.status_code == 422

        allowed = client.post(
            f"/api/v1/governance/reviews/{case_id}/decisions",
            json={
                "status": "ACCEPTED",
                "note": "The score is a prediction, not a verified hazard.",
            },
            headers=_auth(assigned),
        )
        assert allowed.status_code == 200, allowed.text
        assert allowed.json()["status"] == "ACCEPTED"
        assert allowed.json()["assigned_reviewer_id"] == str(assigned.id)

        assert client.post(
            "/api/v1/governance/readiness/evidence",
            json={
                "category": "security",
                "status": "PASS",
                "evidence": "Worker cannot self-attest.",
            },
            headers=_auth(other_worker),
        ).status_code == 403
