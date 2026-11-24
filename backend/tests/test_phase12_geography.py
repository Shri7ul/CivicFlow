"""Phase 12 geographic localization, isolation and Dhaka readiness tests.

Every row created here is a deterministic SYNTHETIC test fixture. Synthetic
fixtures are never counted as operational evidence, field observations,
human-verified records or pilot approval.
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
from app.evidence.acquisition import (
    AcquisitionError,
    DHAKA_OSM_SOURCE,
    SOURCES,
    acquire_infrastructure_source,
    fetch_source_bytes,
)
from app.evidence.dhaka_osm import normalize_osm_context_rows
from app.evidence.workspace import build_workspace
from app.geo.contexts import (
    BD_DHAKA,
    US_NYC,
    UNKNOWN_CONTEXT_KEY,
    BoundingBox,
    all_contexts,
    pilot_area_selection_status,
    require_context,
    resolve_context_from_bbox,
    resolve_context_from_point,
)
from app.governance.dhaka_readiness import assess_dhaka_readiness
from app.main import create_app
from app.models import (
    EvidenceQualityStatus,
    EvidenceSnapshot,
    EvidenceSnapshotKind,
    EvidenceSnapshotStatus,
    Profile,
    ProvenanceKind,
    Role,
    SnapshotVerificationStatus,
    ValidationDataset,
)
from app.models.validation import ValidationDatasetStatus
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
    context_key: str,
    source_key: str,
    bbox: list[float],
    key: str,
    provenance_kind: ProvenanceKind = ProvenanceKind.SYNTHETIC,
) -> EvidenceSnapshot:
    raw = json.dumps({"fixture": True, "context": context_key}).encode("utf-8")
    normalized = json.dumps([{"fixture": True}], sort_keys=True).encode("utf-8")
    snapshot = EvidenceSnapshot(
        snapshot_key=key,
        kind=EvidenceSnapshotKind.RESEARCH_DATASET,
        provenance_kind=provenance_kind,
        status=EvidenceSnapshotStatus.VALIDATED,
        source_key=source_key,
        source_url="https://example.invalid/synthetic-fixture",
        provider="SYNTHETIC TEST FIXTURE",
        license_note="Synthetic fixture; no operational license claim.",
        dataset_version="fixture-v1",
        retrieved_at=datetime.now(timezone.utc),
        snapshot_sha256=hashlib.sha256(normalized).hexdigest(),
        raw_sha256=hashlib.sha256(raw).hexdigest(),
        schema_version="fixture-v1",
        record_count=1,
        raw_record_count=1,
        byte_size=len(normalized),
        crs="EPSG:4326",
        bbox=bbox,
        geographic_coverage="Synthetic fixture bbox",
        geographic_context_key=context_key,
        quality_status=EvidenceQualityStatus.PASS,
        quality_checks=[],
        lineage={"fixture": True},
        verification_status=SnapshotVerificationStatus.PENDING,
        is_current=True,
        raw_content=raw,
        normalized_content=normalized,
    )
    session.add(snapshot)
    session.commit()
    return snapshot


def _osm_payload(count: int = 24) -> dict:
    """Deterministic synthetic Overpass payload inside the Dhaka research cell."""
    elements = []
    for index in range(count):
        latitude = 23.781 + (index % 6) * 0.002
        longitude = 90.391 + (index // 6) * 0.002
        elements.append(
            {
                "type": "way",
                "id": 1000 + index,
                "tags": {"highway": "residential", "name": f"Synthetic Road {index}"},
                "geometry": [
                    {"lat": latitude, "lon": longitude},
                    {"lat": latitude + 0.0001, "lon": longitude + 0.0001},
                ],
            }
        )
    return {"version": 0.6, "elements": elements}


# --- central registry -------------------------------------------------------


def test_registry_defines_exactly_two_non_arbitrary_contexts() -> None:
    assert {context.key for context in all_contexts()} == {US_NYC.key, BD_DHAKA.key}
    assert BD_DHAKA.key == "BD-DHAKA"
    assert BD_DHAKA.country_code == "BD"
    assert BD_DHAKA.boundary_status.value == "BLOCKED"
    assert BD_DHAKA.is_pilot_eligible is False
    assert US_NYC.is_pilot_eligible is False
    with pytest.raises(ValueError):
        require_context("DHaka")
    with pytest.raises(ValueError):
        require_context("BD-DHAKA-NYC")


def test_bbox_conventions_convert_explicitly_without_mixing() -> None:
    box = BoundingBox.from_latlon(23.78, 90.39, 23.80, 90.41)
    assert box.as_geojson() == [90.39, 23.78, 90.41, 23.80]
    assert box.as_latlon() == (23.78, 90.39, 23.80, 90.41)
    assert box.contains(23.79, 90.40)
    assert not box.contains(40.7, -73.9)


def test_nyc_and_dhaka_points_never_cross_classify() -> None:
    assert resolve_context_from_point(23.8103, 90.4125) == BD_DHAKA.key
    assert resolve_context_from_point(40.690, -73.980) == US_NYC.key
    assert resolve_context_from_point(0.0, 0.0) == UNKNOWN_CONTEXT_KEY
    assert (
        resolve_context_from_bbox(BoundingBox.from_geojson([90.39, 23.78, 90.41, 23.80]))
        == BD_DHAKA.key
    )
    assert (
        resolve_context_from_bbox(BoundingBox.from_geojson([-74.0, 40.6, -73.9, 40.7]))
        == US_NYC.key
    )
    assert (
        resolve_context_from_bbox(BoundingBox.from_geojson([0.0, 0.0, 1.0, 1.0]))
        == UNKNOWN_CONTEXT_KEY
    )


def test_pilot_area_selection_remains_blocked() -> None:
    status = pilot_area_selection_status()
    assert status["status"] == "BLOCKED"
    assert status["selected_area"] is None
    assert len(status["candidates"]) >= 2
    assert all(item["status"] == "NOT_ASSESSED" for item in status["candidates"])


# --- Dhaka OSM integration --------------------------------------------------


def test_osm_source_is_pinned_allowlisted_and_context_tagged() -> None:
    definition = SOURCES[DHAKA_OSM_SOURCE]
    assert definition.geographic_context_key == BD_DHAKA.key
    assert definition.normalization_kind == "osm_context"
    assert definition.url.startswith("https://overpass-api.de/api/interpreter?data=")
    assert "23.78" in definition.url and "90.39" in definition.url
    allowed = {item.url for item in SOURCES.values()}
    assert definition.url in allowed
    with pytest.raises(AcquisitionError, match="not allowlisted"):
        fetch_source_bytes("https://example.invalid/arbitrary?data=x")


def test_osm_normalizer_is_deterministic_and_scoped() -> None:
    payload = _osm_payload()
    first = normalize_osm_context_rows(payload)
    second = normalize_osm_context_rows(payload)
    assert first["record_count"] == 24
    assert first["normalized_bytes"] == second["normalized_bytes"]
    assert first["bbox"] == [90.39105, 23.78105, 90.39705, 23.79105]
    assert all(item["external_id"].startswith("osm-way-") for item in first["records"])
    assert all(item["asset_type"] == "ROAD" for item in first["records"])


def test_osm_normalizer_rejects_out_of_cell_and_invalid_geometry() -> None:
    payload = _osm_payload(1)
    payload["elements"].append(
        {
            "type": "way",
            "id": 9999,
            "tags": {"highway": "residential"},
            "geometry": [{"lat": 40.7, "lon": -73.9}],
        }
    )
    payload["elements"].append({"type": "way", "id": 9998, "tags": {}})
    result = normalize_osm_context_rows(payload)
    assert result["record_count"] == 1
    assert result["rejected"] == 2
    assert result["bbox"] == [90.39105, 23.78105, 90.39105, 23.78105]
    assert all(item["external_id"] != "osm-way-9999" for item in result["records"])


def test_osm_acquisition_persists_bd_dhaka_tag(db_session: Session) -> None:
    raw = json.dumps(_osm_payload(24)).encode("utf-8")
    snapshot, created = acquire_infrastructure_source(
        db_session,
        DHAKA_OSM_SOURCE,
        None,
        fetcher=lambda _url: raw,
    )
    assert created is True
    assert snapshot.geographic_context_key == BD_DHAKA.key
    assert snapshot.record_count == 24
    assert snapshot.status == EvidenceSnapshotStatus.VALIDATED
    assert snapshot.raw_sha256 == hashlib.sha256(raw).hexdigest()
    assert snapshot.lineage["geographic_context_key"] == BD_DHAKA.key
    assert "ODbL" in snapshot.license_note
    again, created_again = acquire_infrastructure_source(
        db_session,
        DHAKA_OSM_SOURCE,
        None,
        fetcher=lambda _url: raw,
    )
    assert created_again is False
    assert again.id == snapshot.id


def test_failed_osm_acquisition_does_not_replace_valid_snapshot(
    db_session: Session,
) -> None:
    current = _snapshot(
        db_session,
        context_key=BD_DHAKA.key,
        source_key=DHAKA_OSM_SOURCE,
        bbox=[90.39, 23.78, 90.41, 23.80],
        key="dhaka-current-fixture",
    )

    def _fail(_url: str) -> bytes:
        raise AcquisitionError("fixture source unavailable", code="source_unavailable")

    with pytest.raises(AcquisitionError):
        acquire_infrastructure_source(
            db_session, DHAKA_OSM_SOURCE, None, fetcher=_fail
        )
    db_session.refresh(current)
    assert current.is_current is True
    assert current.snapshot_key == "dhaka-current-fixture"
    failures = db_session.scalars(
        select(EvidenceSnapshot).where(
            EvidenceSnapshot.source_key == DHAKA_OSM_SOURCE,
            EvidenceSnapshot.status == EvidenceSnapshotStatus.FAILED,
        )
    ).all()
    assert len(failures) == 1
    assert failures[0].geographic_context_key == BD_DHAKA.key


# --- workspace isolation ----------------------------------------------------


def test_workspace_dhaka_context_excludes_nyc_research_data(
    db_session: Session,
) -> None:
    _snapshot(
        db_session,
        context_key=US_NYC.key,
        source_key="nyc311-brooklyn-2025q1",
        bbox=[-73.99, 40.68, -73.95, 40.71],
        key="nyc-fixture",
    )
    _snapshot(
        db_session,
        context_key=BD_DHAKA.key,
        source_key=DHAKA_OSM_SOURCE,
        bbox=[90.39, 23.78, 90.41, 23.80],
        key="dhaka-fixture",
    )
    dhaka = build_workspace(db_session, geographic_context_key=BD_DHAKA.key)
    assert dhaka["geographic_context_key"] == BD_DHAKA.key
    assert all(
        row["geographic_context_key"] == BD_DHAKA.key
        for row in dhaka["dataset_registry"]
    )
    assert all(
        row["geographic_context_key"] == BD_DHAKA.key for row in dhaka["snapshots"]
    )
    assert dhaka["infrastructure"]["coverage_context"] is None
    assert dhaka["external_validation"]["results"] == []
    nyc = build_workspace(db_session, geographic_context_key=US_NYC.key)
    assert all(
        row["geographic_context_key"] == US_NYC.key for row in nyc["snapshots"]
    )


# --- readiness --------------------------------------------------------------


def test_dhaka_readiness_with_no_evidence_is_not_ready(db_session: Session) -> None:
    report = assess_dhaka_readiness(db_session)
    assert report["overall"] == "NOT_READY"
    assert report["pilot_activation_authorized"] is False
    assert report["ready_for_activation"] is False
    assert report["geographic_context_key"] == BD_DHAKA.key
    assert "dhaka_ground_truth_readiness" in report["mandatory_unmet"]
    assert "dhaka_pilot_area_selection" in report["mandatory_unmet"]
    assert all(
        item["status"] != "PASS" for item in report["categories"]
    ), "Missing evidence must never become PASS"


def test_nyc_evidence_does_not_satisfy_dhaka_readiness(db_session: Session) -> None:
    _snapshot(
        db_session,
        context_key=US_NYC.key,
        source_key="nyc-dot-bridge-ratings",
        bbox=[-74.3, 40.4, -73.6, 41.0],
        key="nyc-only-fixture",
    )
    report = assess_dhaka_readiness(db_session)
    assert report["overall"] == "NOT_READY"
    assert "dhaka_source_availability" in report["mandatory_unmet"]
    assert report["pilot_area_selection"]["status"] == "BLOCKED"


def test_dhaka_readiness_with_osm_context_still_blocks_pilot(
    db_session: Session,
) -> None:
    _snapshot(
        db_session,
        context_key=BD_DHAKA.key,
        source_key=DHAKA_OSM_SOURCE,
        bbox=[90.39, 23.78, 90.41, 23.80],
        key="dhaka-osm-fixture",
        provenance_kind=ProvenanceKind.OPERATIONAL,
    )
    report = assess_dhaka_readiness(db_session)
    assert report["overall"] == "NOT_READY"
    assert report["ready_for_activation"] is False
    categories = {item["key"]: item for item in report["categories"]}
    assert categories["dhaka_source_availability"]["status"] == "BLOCKED"
    assert categories["dhaka_geographic_isolation"]["status"] == "PASS"


# --- API --------------------------------------------------------------------


def test_api_contexts_and_unknown_context_rejection(db_session: Session) -> None:
    client = _client(db_session)
    worker = _profile(db_session, Role.WORKER, "Worker")
    headers = _auth(worker)
    response = client.get(
        "/api/v1/governance/geography/contexts", headers=headers
    )
    assert response.status_code == 200
    keys = {item["key"] for item in response.json()["items"]}
    assert keys == {US_NYC.key, BD_DHAKA.key}
    detail = client.get(
        "/api/v1/governance/geography/contexts/BD-DHAKA", headers=headers
    )
    assert detail.status_code == 200
    assert detail.json()["boundary_status"] == "BLOCKED"
    bad = client.get(
        "/api/v1/governance/geography/contexts/NYC-DHAKA", headers=headers
    )
    assert bad.status_code == 422


def test_api_dhaka_readiness_never_authorizes_activation(
    db_session: Session,
) -> None:
    client = _client(db_session)
    worker = _profile(db_session, Role.WORKER, "Worker")
    headers = _auth(worker)
    response = client.get(
        "/api/v1/governance/geography/readiness/dhaka", headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["overall"] == "NOT_READY"
    assert body["ready_for_activation"] is False
    assert body["pilot_activation_authorized"] is False
    citizen = _profile(db_session, Role.CITIZEN, "Citizen")
    denied = client.get(
        "/api/v1/governance/geography/readiness/dhaka",
        headers=_auth(citizen),
    )
    assert denied.status_code in {401, 403}


def test_api_workspace_geographic_scope_is_server_side(
    db_session: Session,
) -> None:
    _snapshot(
        db_session,
        context_key=US_NYC.key,
        source_key="nyc311-fixture",
        bbox=[-73.99, 40.68, -73.95, 40.71],
        key="nyc-api-fixture",
    )
    _snapshot(
        db_session,
        context_key=BD_DHAKA.key,
        source_key=DHAKA_OSM_SOURCE,
        bbox=[90.39, 23.78, 90.41, 23.80],
        key="dhaka-api-fixture",
    )
    client = _client(db_session)
    worker = _profile(db_session, Role.WORKER, "Worker")
    headers = _auth(worker)
    response = client.get(
        "/api/v1/governance/evidence/workspace",
        params={"geographic_context": BD_DHAKA.key},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["geographic_context_key"] == BD_DHAKA.key
    assert all(
        item["geographic_context_key"] == BD_DHAKA.key
        for item in body["snapshots"]
    )
    rejected = client.get(
        "/api/v1/governance/evidence/workspace",
        params={"geographic_context": "NOT-REGISTERED"},
        headers=headers,
    )
    assert rejected.status_code == 422


def test_synthetic_dhaka_snapshot_cannot_pass_isolation(db_session: Session) -> None:
    _snapshot(
        db_session,
        context_key=BD_DHAKA.key,
        source_key=DHAKA_OSM_SOURCE,
        bbox=[90.39, 23.78, 90.41, 23.80],
        key="synthetic-dhaka-fixture",
        provenance_kind=ProvenanceKind.SYNTHETIC,
    )
    report = assess_dhaka_readiness(db_session)
    categories = {item["key"]: item for item in report["categories"]}
    assert categories["dhaka_geographic_isolation"]["status"] == "FAIL"
    assert categories["dhaka_source_availability"]["status"] == "BLOCKED"


def test_osm_snapshot_never_serializes_as_operational_evidence(
    db_session: Session,
) -> None:
    snapshot, _ = acquire_infrastructure_source(
        db_session,
        DHAKA_OSM_SOURCE,
        None,
        fetcher=lambda _url: json.dumps(_osm_payload(24)).encode("utf-8"),
    )
    from app.evidence.snapshots import serialize_snapshot

    payload = serialize_snapshot(snapshot, detail=True)
    assert payload["geographic_context_key"] == BD_DHAKA.key
    assert payload["provenance"] == "PUBLIC_OSM_RESEARCH"
    assert payload["readiness"] == "RESEARCH_CONTEXT_ONLY"
    assert "not authoritative" in payload["disclaimer"]


def test_workspace_aggregate_counts_are_geography_scoped(db_session: Session) -> None:
    _snapshot(
        db_session,
        context_key=US_NYC.key,
        source_key="nyc-dot-bridge-ratings",
        bbox=[-74.3, 40.4, -73.6, 41.0],
        key="nyc-count-fixture",
        provenance_kind=ProvenanceKind.OPERATIONAL,
    )
    _snapshot(
        db_session,
        context_key=BD_DHAKA.key,
        source_key=DHAKA_OSM_SOURCE,
        bbox=[90.39, 23.78, 90.41, 23.80],
        key="dhaka-count-fixture",
        provenance_kind=ProvenanceKind.OPERATIONAL,
    )
    dhaka = build_workspace(db_session, geographic_context_key=BD_DHAKA.key)
    assert dhaka["evidence_integrity"]["snapshots"] == 1
    assert dhaka["evidence_integrity"]["current_snapshots"] == 1
    nyc = build_workspace(db_session, geographic_context_key=US_NYC.key)
    assert nyc["evidence_integrity"]["snapshots"] == 1
