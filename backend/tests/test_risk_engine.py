"""Phase 5 urban risk engine unit, API, privacy, and persistence tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import h3
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.auth.jwt import get_token_verifier
from app.db.session import get_db_session
from app.main import create_app
from app.models import (
    AssetType,
    DependencyEdge,
    DependencyType,
    Incident,
    IncidentCategory,
    IncidentRelationship,
    IncidentSeverity,
    IncidentStatus,
    InfrastructureAsset,
    Profile,
    RiskCellSnapshot,
    RiskModelRun,
    RelationshipStatus,
    RelationshipType,
    Role,
)
from app.risk.config import RiskConfig, RiskConfigError
from app.risk.engine import RiskEngine, RiskQuery
from app.risk.geo import geometry_distance_m
from app.risk.scoring import (
    IncidentRecord,
    InfrastructureFactor,
    aggregate_incidents,
    calculate_trend,
    score_aggregate,
)
from app.core.config import Settings
from tests.auth_support import make_settings, make_token, make_verifier

PAYLOAD: dict[str, Any] = {
    "title": "Flooded drain hazard",
    "description": "Water is pooling across the road after heavy rain.",
    "category": "DRAINAGE",
    "severity": "HIGH",
    "latitude": 23.8103,
    "longitude": 90.4125,
    "address": "Phase 5 risk test",
}


def _profile(session: Session, *, role: Role = Role.CITIZEN, name: str = "Citizen") -> Profile:
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


def _report(
    client: TestClient, profile: Profile, **overrides: Any
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/incidents",
        headers=_auth(profile),
        json={**PAYLOAD, **overrides},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _config() -> RiskConfig:
    return RiskConfig.from_settings(Settings(_env_file=None, app_env="testing"))


def test_config_is_validated_and_stable() -> None:
    config = _config()
    assert config.model_version == "risk-v1"
    assert config.default_resolution == 8
    assert config.category_for(0) .value == "MINIMAL"
    assert config.category_for(20).value == "LOW"
    assert config.category_for(40).value == "MODERATE"
    assert config.category_for(65).value == "HIGH"
    assert config.category_for(85).value == "CRITICAL"
    assert config.config_hash == _config().config_hash
    assert sum(config.weights.values()) == 1.0

    with pytest.raises(RiskConfigError):
        RiskConfig(
            **{
                **config.__dict__,
                "weights": {**config.weights, "severity": 0.9},
            }
        )
    with pytest.raises(RiskConfigError):
        RiskConfig(
            **{
                **config.__dict__,
                "severity_weights": {IncidentSeverity.HIGH: 0.7},
            }
        )
    with pytest.raises(RiskConfigError):
        RiskConfig(
            **{
                **config.__dict__,
                "weights": {**config.weights, "unexpected": 0.0},
            }
        )
    with pytest.raises(RiskConfigError):
        RiskConfig(
            **{
                **config.__dict__,
                "weights": {**config.weights, "severity": float("nan")},
            }
        )


def test_h3_boundary_and_geometry_helpers() -> None:
    cell = h3.latlng_to_cell(23.8103, 90.4125, 8)
    boundary = h3.cell_to_boundary(cell)
    assert len(boundary) == 6
    assert h3.get_resolution(cell) == 8
    assert geometry_distance_m(23.8103, 90.4125, "POINT(90.4125 23.8103)") < 1
    assert geometry_distance_m(
        23.8103, 90.4125, "LINESTRING(90.4124 23.8103, 90.4126 23.8103)"
    ) < 1
    assert geometry_distance_m(
        23.8103,
        90.4125,
        "POLYGON((90.4120 23.8100, 90.4130 23.8100, "
        "90.4130 23.8110, 90.4120 23.8110, 90.4120 23.8100))",
    ) == 0


def test_scoring_factors_and_duplicate_adjustment_are_explainable() -> None:
    config = _config()
    now = datetime.now(timezone.utc)
    reporter = uuid.uuid4()
    first = IncidentRecord(
        uuid.uuid4(), 23.8103, 90.4125, now, IncidentSeverity.HIGH,
        IncidentCategory.DRAINAGE, IncidentStatus.OPEN, reporter,
    )
    duplicate = IncidentRecord(
        uuid.uuid4(), 23.8103, 90.4125, now, IncidentSeverity.HIGH,
        IncidentCategory.DRAINAGE, IncidentStatus.OPEN, reporter,
    )
    aggregate = aggregate_incidents(
        [first, duplicate], duplicate_pairs=[(first.id, duplicate.id)]
    )
    assert len(aggregate.raw_incidents) == 2
    assert len(aggregate.adjusted_incidents) == 1
    assert aggregate.removed_duplicates == 1
    result = score_aggregate(
        aggregate,
        config=config,
        now=now,
        infrastructure=InfrastructureFactor(
            normalized=0.5,
            available=True,
            explanation="One nearby asset.",
            metadata={"nearby_asset_count": 1, "dependency_count": 1},
        ),
        spatial_value=0.8,
        trend_value=0.6,
    )
    assert 0 <= result.risk_score <= 100
    assert 0 <= result.incident_activity_score <= 100
    assert {factor.key for factor in result.factors} == {
        "severity",
        "density",
        "spatial",
        "recency",
        "active",
        "category",
        "trend",
        "infrastructure",
        "dependency",
    }
    assert all(factor.available for factor in result.factors)
    assert sum(factor.contribution for factor in result.factors) == pytest.approx(
        result.risk_score / 100, abs=1e-3
    )
    assert result.confidence_label in {"low", "moderate", "high"}


def test_trend_requires_enough_history_and_classifies_changes() -> None:
    config = _config()
    insufficient = calculate_trend(
        current_score=50,
        previous_score=10,
        current_count=1,
        previous_count=1,
        config=config,
    )
    assert insufficient.available is False
    assert insufficient.direction == "INSUFFICIENT_DATA"
    incomplete = calculate_trend(
        current_score=50,
        previous_score=10,
        current_count=3,
        previous_count=3,
        config=config,
        history_coverage=0.5,
    )
    assert incomplete.available is False
    assert "covered" in incomplete.reason
    stable = calculate_trend(
        current_score=50,
        previous_score=48,
        current_count=2,
        previous_count=2,
        config=config,
    )
    assert stable.direction == "STABLE"
    increasing = calculate_trend(
        current_score=70,
        previous_score=30,
        current_count=2,
        previous_count=2,
        config=config,
    )
    assert increasing.direction == "INCREASING"
    decreasing = calculate_trend(
        current_score=20,
        previous_score=70,
        current_count=2,
        previous_count=2,
        config=config,
    )
    assert decreasing.direction == "DECREASING"


def test_risk_cells_are_private_until_minimum_count(db_session: Session) -> None:
    citizen = _profile(db_session)
    worker = _profile(db_session, role=Role.WORKER)
    with _client(db_session) as client:
        _report(client, citizen)
        citizen_response = client.get(
            "/api/v1/risk/cells?window=7d", headers=_auth(citizen)
        )
        assert citizen_response.status_code == 200, citizen_response.text
        assert citizen_response.json()["items"] == []
        assert citizen_response.json()["privacy"]["suppressed_cells"] == 1

        worker_response = client.get(
            "/api/v1/risk/cells?window=7d", headers=_auth(worker)
        )
        assert worker_response.status_code == 200, worker_response.text
        body = worker_response.json()
        assert len(body["items"]) == 1
        cell = body["items"][0]
        assert cell["incident_count"] == 1
        assert cell["risk_category"] in {"MINIMAL", "LOW", "MODERATE", "HIGH", "CRITICAL"}
        assert len(cell["factors"]) == 9
        assert body["summary"]["current_incident_count"] == 1
        assert body["model_version"] == "risk-v1"


def test_risk_cells_detail_privacy_and_infrastructure_exposure(
    db_session: Session,
) -> None:
    owner = _profile(db_session, name="Owner")
    other = _profile(db_session, name="Other")
    worker = _profile(db_session, role=Role.WORKER)
    with _client(db_session) as client:
        owner_ids = [_report(client, owner)["id"] for _ in range(3)]
        _report(client, other)
        asset = InfrastructureAsset(
            name="Phase 5 Hospital",
            asset_type=AssetType.HOSPITAL,
            location="POINT(90.4126 23.8104)",
            criticality_score=9,
            is_active=True,
            metadata_json={"source": "test", "authoritative": False},
        )
        second_asset = InfrastructureAsset(
            name="Phase 5 Drain",
            asset_type=AssetType.DRAIN,
            location="LINESTRING(90.4124 23.8102, 90.4126 23.8104)",
            criticality_score=8,
            is_active=True,
            metadata_json={"source": "test", "authoritative": False},
        )
        db_session.add_all([asset, second_asset])
        db_session.flush()
        db_session.add(
            DependencyEdge(
                source_asset_id=second_asset.id,
                target_asset_id=asset.id,
                dependency_type=DependencyType.SERVES,
                strength=0.8,
            )
        )
        db_session.commit()

        response = client.get(
            "/api/v1/risk/cells?window=7d", headers=_auth(worker)
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["items"][0]["infrastructure"]["nearby_asset_count"] == 2
        assert body["items"][0]["infrastructure"]["dependency_count"] == 2
        assert body["summary"]["exposure_cells"] == 1
        assert body["dataset"]["development_or_unknown_asset_count"] == 2
        cell_id = body["items"][0]["h3_cell_id"]
        detail = client.get(
            f"/api/v1/risk/cells/{cell_id}?window=7d", headers=_auth(worker)
        )
        assert detail.status_code == 200, detail.text
        assert len(detail.json()["incidents"]) == 4
        assert detail.json()["limitations"]

        citizen_detail = client.get(
            f"/api/v1/risk/cells/{cell_id}?window=7d", headers=_auth(owner)
        )
        assert citizen_detail.status_code == 200
        assert {
            item["id"] for item in citizen_detail.json()["incidents"]
        } == set(owner_ids)

        geojson = client.get(
            "/api/v1/risk/cells?window=7d&format=geojson", headers=_auth(worker)
        )
        assert geojson.status_code == 200, geojson.text
        assert geojson.json()["type"] == "FeatureCollection"
        assert geojson.json()["features"][0]["geometry"]["type"] == "Polygon"
        assert geojson.json()["features"][0]["properties"]["h3_cell_id"] == cell_id


def test_citizen_trends_hide_low_count_comparison_windows(
    db_session: Session,
) -> None:
    citizen = _profile(db_session)
    worker = _profile(db_session, role=Role.WORKER)
    with _client(db_session) as client:
        ids = [_report(client, worker)["id"] for _ in range(4)]
        historical = uuid.UUID(_report(client, worker)["id"])
        for incident_id in ids[:1]:
            db_session.execute(
                update(Incident)
                .where(Incident.id == uuid.UUID(incident_id))
                .values(created_at=datetime.now(timezone.utc) - timedelta(hours=36))
            )
        db_session.execute(
            update(Incident)
            .where(Incident.id == historical)
            .values(created_at=datetime.now(timezone.utc) - timedelta(hours=60))
        )
        db_session.commit()
        cells = client.get(
            "/api/v1/risk/cells?window=24h", headers=_auth(citizen)
        )
        assert cells.status_code == 200, cells.text
        body = cells.json()
        assert len(body["items"]) == 1
        assert body["items"][0]["incident_count"] == 3
        trend = body["items"][0]["trend"]
        assert trend["available"] is False
        assert trend["current_incident_count"] == 0
        assert trend["previous_incident_count"] == 0
        trends = client.get(
            "/api/v1/risk/trends?window=24h", headers=_auth(citizen)
        )
        assert trends.status_code == 200, trends.text
        assert trends.json()["items"] == []


def test_summary_trends_and_filters(db_session: Session) -> None:
    worker = _profile(db_session, role=Role.WORKER)
    with _client(db_session) as client:
        current_ids = [
            _report(client, worker)["id"] for _ in range(3)
        ]
        # Move two incidents into the immediately preceding 24h window and
        # establish older history so the previous window is fully observable.
        prior_ids = current_ids[:2]
        for incident_id in prior_ids:
            db_session.execute(
                update(Incident)
                .where(Incident.id == uuid.UUID(incident_id))
                .values(created_at=datetime.now(timezone.utc) - timedelta(hours=36))
            )
        historical = uuid.UUID(_report(client, worker)["id"])
        db_session.execute(
            update(Incident)
            .where(Incident.id == historical)
            .values(created_at=datetime.now(timezone.utc) - timedelta(hours=60))
        )
        db_session.commit()
        response = client.get(
            "/api/v1/risk/trends?window=24h", headers=_auth(worker)
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["counts"]["total"] == 1
        assert body["items"][0]["direction"] in {
            "INCREASING", "DECREASING", "STABLE"
        }
        assert body["items"][0]["current_incident_count"] == 1
        assert body["items"][0]["previous_incident_count"] == 2

        summary = client.get(
            "/api/v1/risk/summary?window=7d", headers=_auth(worker)
        )
        assert summary.status_code == 200, summary.text
        assert summary.json()["total_cells"] == 1
        assert summary.json()["current_incident_count"] == 4

        filtered = client.get(
            "/api/v1/risk/cells?window=7d&min_score=100", headers=_auth(worker)
        )
        assert filtered.status_code == 200
        assert filtered.json()["items"] == []
        assert filtered.json()["total"] == 0

        assert client.get("/api/v1/risk/cells?window=1h&window_hours=24").status_code == 401


def test_early_trend_is_withheld_without_comparison_history(
    db_session: Session,
) -> None:
    worker = _profile(db_session, role=Role.WORKER)
    with _client(db_session) as client:
        _report(client, worker)
        response = client.get(
            "/api/v1/risk/trends?window=24h", headers=_auth(worker)
        )
        assert response.status_code == 200, response.text
        assert response.json()["items"][0]["direction"] == "INSUFFICIENT_DATA"


def test_confirmed_duplicates_do_not_double_count_across_cells(
    db_session: Session,
) -> None:
    worker = _profile(db_session, role=Role.WORKER)
    with _client(db_session) as client:
        base_cell = h3.latlng_to_cell(23.8103, 90.4125, 8)
        neighbors = sorted(h3.grid_disk(base_cell, 1))
        first_lat, first_lon = h3.cell_to_latlng(neighbors[0])
        second_lat, second_lon = h3.cell_to_latlng(neighbors[1])
        first = _report(
            client,
            worker,
            latitude=first_lat,
            longitude=first_lon,
        )
        second = _report(
            client,
            worker,
            latitude=second_lat,
            longitude=second_lon,
        )
        first_id = uuid.UUID(first["id"])
        second_id = uuid.UUID(second["id"])
        db_session.add(
            IncidentRelationship(
                incident_a_id=min(first_id, second_id),
                incident_b_id=max(first_id, second_id),
                relationship_type=RelationshipType.DUPLICATE,
                status=RelationshipStatus.CONFIRMED,
                confidence=Decimal("0.95"),
                signals={"source": "phase5 regression test"},
                reviewed_by=worker.id,
                reviewed_at=datetime.now(timezone.utc),
            )
        )
        db_session.commit()
        response = client.get(
            "/api/v1/risk/cells?window=7d&resolution=8", headers=_auth(worker)
        )
        assert response.status_code == 200, response.text
        items = response.json()["items"]
        assert sum(item["incident_count"] for item in items) == 2
        assert sum(item["adjusted_incident_count"] for item in items) == 1
        assert sum(item["removed_duplicates"] for item in items) == 1


def test_confirmed_duplicates_across_windows_are_deduplicated_once(
    db_session: Session,
) -> None:
    worker = _profile(db_session, role=Role.WORKER)
    with _client(db_session) as client:
        first = _report(client, worker)
        second = _report(client, worker)
        first_id = uuid.UUID(first["id"])
        second_id = uuid.UUID(second["id"])
        db_session.execute(
            update(Incident)
            .where(Incident.id == second_id)
            .values(created_at=datetime.now(timezone.utc) - timedelta(hours=36))
        )
        historical = uuid.UUID(_report(client, worker)["id"])
        db_session.execute(
            update(Incident)
            .where(Incident.id == historical)
            .values(created_at=datetime.now(timezone.utc) - timedelta(hours=60))
        )
        db_session.add(
            IncidentRelationship(
                incident_a_id=min(first_id, second_id),
                incident_b_id=max(first_id, second_id),
                relationship_type=RelationshipType.DUPLICATE,
                status=RelationshipStatus.CONFIRMED,
                confidence=Decimal("0.95"),
                signals={"source": "phase5 cross-window test"},
                reviewed_by=worker.id,
                reviewed_at=datetime.now(timezone.utc),
            )
        )
        db_session.commit()
        response = client.get(
            "/api/v1/risk/trends?window=24h", headers=_auth(worker)
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["counts"]["total"] == 1
        trend = body["items"][0]
        assert trend["current_incident_count"] + trend["previous_incident_count"] == 1


def test_risk_cell_detail_rejects_invalid_cell_ids(db_session: Session) -> None:
    worker = _profile(db_session, role=Role.WORKER)
    with _client(db_session) as client:
        response = client.get(
            "/api/v1/risk/cells/not-an-h3-cell", headers=_auth(worker)
        )
        assert response.status_code == 404


def test_risk_runs_persist_for_staff(db_session: Session) -> None:
    worker = _profile(db_session, role=Role.WORKER)
    citizen = _profile(db_session)
    with _client(db_session) as client:
        _report(client, worker)
        forbidden = client.post(
            "/api/v1/risk/runs", headers=_auth(citizen), json={"window_hours": 168}
        )
        assert forbidden.status_code == 403
        response = client.post(
            "/api/v1/risk/runs",
            headers=_auth(worker),
            json={"window_hours": 168, "resolution": 8},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["run_id"]
        assert body["cell_count"] == 1
        assert db_session.scalar(
            select(func.count()).select_from(RiskModelRun)
        ) == 1
        assert db_session.scalar(
            select(func.count()).select_from(RiskCellSnapshot)
        ) == 1
        listed = client.get("/api/v1/risk/runs", headers=_auth(worker))
        assert listed.status_code == 200
        assert len(listed.json()["items"]) == 1


def test_risk_endpoints_require_auth_and_bbox_validation(
    db_session: Session,
) -> None:
    worker = _profile(db_session, role=Role.WORKER)
    with _client(db_session) as client:
        assert client.get("/api/v1/risk/config").status_code == 401
        assert client.get("/api/v1/risk/cells").status_code == 401
        invalid = client.get(
            "/api/v1/risk/cells?min_latitude=23.8",
            headers=_auth(worker),
        )
        assert invalid.status_code == 422
        invalid_resolution = client.get(
            "/api/v1/risk/cells?resolution=4", headers=_auth(worker)
        )
        assert invalid_resolution.status_code == 422
