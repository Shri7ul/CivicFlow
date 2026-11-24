"""Acquisition boundary tests. All source payloads are synthetic fixtures."""

from __future__ import annotations

import json
import uuid
from dataclasses import replace
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.evidence.acquisition import (
    AcquisitionError,
    _assert_allowed,
    acquire_infrastructure_source,
    normalize_bridge_rows,
)
from app.core.config import Settings
from app.evidence.external import ExternalAcquisitionError, acquire_external_dataset
from app.auth.dependencies import AuthenticatedUser
from app.evidence.snapshots import serialize_snapshot, verify_snapshot
from app.models import (
    EvidenceSnapshot,
    EvidenceSnapshotStatus,
    InfrastructureAsset,
    InfrastructureSource,
    Profile,
    Role,
    ValidationDataset,
    ValidationDatasetStatus,
)
from app.models.enums import InfrastructureValidationStatus, ProvenanceKind
from app.validation.phase11 import PHASE11_BROOKLYN_Q3


def _row(bin_value: str, day: int = 1, **overrides) -> dict:
    row = {
        "bin": bin_value,
        "boro": "Brooklyn",
        "feature_carried": "Synthetic Avenue",
        "feature_crossed": "Synthetic Creek",
        "inspection_date": f"2024-01-{day:02d}T00:00:00.000",
        "x_coord_lat": "40.7000",
        "y_coord_lon": "-73.9000",
        "current_rating": "5.0",
        "rating_source": "synthetic",
        "bridge_type": "Synthetic",
        "spans": "2",
        "other_owner": "TEST",
        "general_recommendation": "4",
        "deck_area_sq_ft": "1000",
        "replacement_cost": "100000",
        "verbal_rating": "Good",
    }
    row.update(overrides)
    return row


def test_allowlist_rejects_arbitrary_urls() -> None:
    _assert_allowed(
        "https://data.cityofnewyork.us/resource/4yue-vjfc.json?$limit=5000&$order=bin"
    )
    for url in (
        "http://data.cityofnewyork.us/resource/4yue-vjfc.json",
        "https://169.254.169.254/latest/meta-data",
        "https://data.cityofnewyork.us/resource/4yue-vjfc.json?$limit=999999",
        "https://user:pass@data.cityofnewyork.us/resource/4yue-vjfc.json",
    ):
        with pytest.raises(AcquisitionError):
            _assert_allowed(url)


def test_bridge_normalization_is_deterministic_and_bounded() -> None:
    rows = [
        _row("000001", 1),
        _row("000001", 3, x_coord_lat="", y_coord_lon=""),
        _row("000002", 2, bin="000002"),
        _row("000003", 4, x_coord_lat="", y_coord_lon=""),
        {"bin": "", "inspection_date": "2024-01-01"},
        "not-a-row",
    ]
    result = normalize_bridge_rows(rows)
    assert result["record_count"] == 2
    assert [item["external_id"] for item in result["records"]] == ["000001", "000002"]
    first = result["records"][0]
    assert first["coordinate_source"] == "PRIOR_INSPECTION"
    assert first["inspection_date"].startswith("2024-01-03")
    assert first["source_row_count"] == 2
    assert result["record_count"] != result["raw_record_count"]
    assert result["bbox"] == [-73.9, 40.7, -73.9, 40.7]
    assert result["quality_status"].value == "FAIL"


def _bridge_payload(count: int = 110) -> bytes:
    rows = [
        _row(f"{index:06d}", (index % 20) + 1) for index in range(count)
    ]
    return json.dumps(rows).encode("utf-8")


def test_failed_fetch_never_replaces_current_assets(db_session: Session) -> None:
    good, created = acquire_infrastructure_source(
        db_session,
        "nyc-dot-bridge-ratings",
        None,
        fetcher=lambda _url: _bridge_payload(),
    )
    assert created is True
    assert good.status == EvidenceSnapshotStatus.VALIDATED
    assert good.provenance_kind == ProvenanceKind.OPERATIONAL
    assert good.record_count == 110
    assert good.is_current is True
    assets = db_session.scalars(
        select(InfrastructureAsset).where(InfrastructureAsset.snapshot_id == good.id)
    ).all()
    assert len(assets) == 110

    with pytest.raises(AcquisitionError):
        acquire_infrastructure_source(
            db_session,
            "nyc-dot-bridge-ratings",
            None,
            fetcher=lambda _url: b"not-json",
        )
    db_session.expire_all()
    current = db_session.scalar(
        select(EvidenceSnapshot).where(
            EvidenceSnapshot.source_key == "nyc-dot-bridge-ratings",
            EvidenceSnapshot.is_current.is_(True),
        )
    )
    assert current is not None
    assert current.id == good.id
    failed = db_session.scalars(
        select(EvidenceSnapshot).where(
            EvidenceSnapshot.source_key == "nyc-dot-bridge-ratings",
            EvidenceSnapshot.status == EvidenceSnapshotStatus.FAILED,
        )
    ).all()
    assert len(failed) == 1
    assert failed[0].is_current is False
    assert db_session.scalars(
        select(InfrastructureAsset).where(InfrastructureAsset.is_active.is_(True))
    ).all()

    repeated, created_again = acquire_infrastructure_source(
        db_session,
        "nyc-dot-bridge-ratings",
        None,
        fetcher=lambda _url: _bridge_payload(),
    )
    assert created_again is False
    assert repeated.id == good.id
    assert repeated.is_current is True


def test_valid_replacement_retires_assets_absent_from_new_snapshot(
    db_session: Session,
) -> None:
    first, _ = acquire_infrastructure_source(
        db_session,
        "nyc-dot-bridge-ratings",
        None,
        fetcher=lambda _url: _bridge_payload(),
    )
    replacement, created = acquire_infrastructure_source(
        db_session,
        "nyc-dot-bridge-ratings",
        None,
        fetcher=lambda _url: _bridge_payload(109),
    )
    assert created is True
    assert replacement.id != first.id
    db_session.expire_all()
    retired = db_session.scalar(
        select(InfrastructureAsset).where(
            InfrastructureAsset.source_id == replacement.infrastructure_source_id,
            InfrastructureAsset.external_id == "000109",
        )
    )
    assert retired is not None
    assert retired.is_active is False
    active = db_session.scalars(
        select(InfrastructureAsset).where(
            InfrastructureAsset.source_id == replacement.infrastructure_source_id,
            InfrastructureAsset.is_active.is_(True),
        )
    ).all()
    assert len(active) == 109


def test_recomputed_snapshot_validates_source_metadata_only(
    db_session: Session,
) -> None:
    snapshot, _ = acquire_infrastructure_source(
        db_session,
        "nyc-dot-bridge-ratings",
        None,
        fetcher=lambda _url: _bridge_payload(),
    )
    profile = Profile(
        id=uuid.uuid4(),
        full_name="Synthetic verifier fixture",
        role=Role.ADMIN,
        is_active=True,
    )
    db_session.add(profile)
    db_session.commit()
    actor = AuthenticatedUser(subject=profile.id, email=None, profile=profile)
    verify_snapshot(db_session, snapshot, actor)
    source = db_session.scalar(
        select(InfrastructureSource).where(
            InfrastructureSource.source_key == "nyc-dot-bridge-ratings"
        )
    )
    assert source is not None
    assert source.validation_status == InfrastructureValidationStatus.VERIFIED
    assert source.details["metadata_validation"]["status"] == "COMPLETE"
    assert "physical condition is not field-verified" in (
        source.details["metadata_validation"]["limitation"]
    )


def test_snapshot_serialization_labels_synthetic_and_hides_bytes(
    db_session: Session,
) -> None:
    snapshot, _ = acquire_infrastructure_source(
        db_session,
        "nyc-dot-bridge-ratings",
        None,
        fetcher=lambda _url: _bridge_payload(),
    )
    payload = serialize_snapshot(snapshot, detail=True)
    assert "raw_content" not in payload
    assert payload["provenance"] == "REAL"
    assert payload["provenance_kind"] == "OPERATIONAL"
    assert payload["record_count"] == 110
    assert payload["readiness"] == "REAL_ACQUIRED"


def test_external_acquisition_rejects_modified_pinned_spec(
    db_session: Session,
) -> None:
    modified = replace(
        PHASE11_BROOKLYN_Q3,
        bbox=(40.68, -73.99, 40.70, -73.95),
        snapshot_filename="../escape.json.gz",
    )
    with pytest.raises(ExternalAcquisitionError, match="pinned"):
        acquire_external_dataset(
            db_session,
            modified,
            settings=Settings(),
        )
    assert db_session.scalars(select(EvidenceSnapshot)).all() == []


def test_existing_external_dataset_is_never_overwritten(
    db_session: Session,
) -> None:
    dataset = ValidationDataset(
        dataset_key=PHASE11_BROOKLYN_Q3.dataset_key,
        name="Synthetic pinned dataset fixture",
        source_url=PHASE11_BROOKLYN_Q3.source_url,
        license_note="Synthetic fixture; no license claim.",
        region=PHASE11_BROOKLYN_Q3.region,
        period_start=PHASE11_BROOKLYN_Q3.period_start,
        period_end=PHASE11_BROOKLYN_Q3.period_end,
        snapshot_sha256="a" * 64,
        record_count=7,
        schema_version="fixture-v1",
        status=ValidationDatasetStatus.VALIDATED,
        dataset_metadata={"fixture": True},
        created_by=None,
    )
    db_session.add(dataset)
    db_session.commit()

    result = acquire_external_dataset(
        db_session,
        PHASE11_BROOKLYN_Q3,
        settings=Settings(),
    )
    assert result["created"] is False
    assert result["dataset"].id == dataset.id
    assert result["dataset"].record_count == 7
    assert "not overwritten" in result["reason"]
    assert db_session.scalars(select(EvidenceSnapshot)).all() == []
