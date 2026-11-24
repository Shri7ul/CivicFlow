"""Persisted validation experiment management tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Profile, Role
from app.validation import service as validation_service
from app.validation.dataset import canonical_hash, snapshot_path, write_snapshot
from app.validation.service import (
    ValidationError,
    build_report,
    dataset_records,
    register_dataset,
    run_correlation_experiment,
    run_decision_experiment,
)


def _profile(session: Session) -> Profile:
    profile = Profile(
        id=uuid.uuid4(), full_name="Validation Admin", role=Role.ADMIN, is_active=True
    )
    session.add(profile)
    session.commit()
    return profile


def _dataset(session: Session, root: Path, *, digest_suffix: str = "a") -> object:
    records = [
        {
            "external_id": "1",
            "observed_at": "2025-02-01T12:00:00+00:00",
            "complaint_type": "Street Condition",
            "descriptor": "Pothole",
            "latitude": 40.69,
            "longitude": -73.98,
            "borough": "BROOKLYN",
            "source_status": "Open",
            "status": "OPEN",
            "category": "ROADS",
            "severity": "MEDIUM",
        }
    ]
    path = root / f"snapshot-{digest_suffix}.json.gz"
    digest = write_snapshot(
        path, records=records, rejected=[], metadata={"fixture": True}
    )
    return register_dataset(
        session,
        dataset_key=f"fixture-{digest_suffix}",
        name="Fixture dataset",
        description="fixture",
        source_url="https://example.invalid/data",
        license_note="fixture only",
        region="fixture",
        period_start=datetime(2025, 1, 1, tzinfo=timezone.utc),
        period_end=datetime(2025, 3, 31, tzinfo=timezone.utc),
        source_id=None,
        ingestion_run_id=None,
        snapshot_sha256=digest,
        snapshot_path=path.name,
        record_count=1,
        schema_version="fixture-v1",
        dataset_metadata={"fixture": True},
        actor_id=None,
    )


def test_register_dataset_is_idempotent_but_not_overwritable(
    db_session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(validation_service, "DATA_ROOT", tmp_path)
    first = _dataset(db_session, tmp_path, digest_suffix="a")
    second = _dataset(db_session, tmp_path, digest_suffix="a")
    assert first.id == second.id
    with pytest.raises(ValidationError) as error:
        register_dataset(
            db_session,
            dataset_key="fixture-a",
            name="Different",
            description=None,
            source_url="https://example.invalid/other",
            license_note="fixture",
            region="fixture",
            period_start=None,
            period_end=None,
            source_id=None,
            ingestion_run_id=None,
            snapshot_sha256="b" * 64,
            snapshot_path=None,
            record_count=1,
            schema_version="fixture-v1",
            dataset_metadata={},
            actor_id=None,
        )
    assert error.value.code == "dataset_snapshot_conflict"
    records, metadata = dataset_records(db_session, first)
    assert records[0]["external_id"] == "1"
    assert metadata["fixture"] is True


def test_register_dataset_rejects_mismatched_snapshot(
    db_session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(validation_service, "DATA_ROOT", tmp_path)
    dataset = _dataset(db_session, tmp_path)
    dataset.snapshot_sha256 = "0" * 64
    db_session.commit()
    with pytest.raises(ValidationError) as error:
        dataset_records(db_session, dataset)
    assert error.value.code == "dataset_snapshot_mismatch"


def test_experiments_are_append_only_and_reports_are_derived(
    db_session: Session,
) -> None:
    settings = get_settings()
    first = run_correlation_experiment(
        db_session, settings=settings, actor_id=None
    )
    second = run_correlation_experiment(
        db_session, settings=settings, actor_id=None
    )
    assert first.id != second.id
    assert first.experiment_key != second.experiment_key
    assert first.metrics["case_count"] == 8
    assert first.metrics["precision"] is not None
    assert first.evidence_kind.value == "SYNTHETIC_FIXTURE"
    assert any("synthetic" in item.lower() for item in first.limitations)
    report = build_report(first, None)
    assert report["experiment_id"] == str(first.id)
    assert report["metrics"] == first.metrics
    assert report["methodology"]["method"] == first.method
    assert report["dataset"] is None

    decision = run_decision_experiment(
        db_session, settings=settings, actor_id=None
    )
    assert decision.experiment_type.value == "DECISION_SIMULATION"
    assert decision.evidence_kind.value == "SIMULATED_PLANNING"
    assert decision.metrics["deterministic_schedule"] is True
    assert decision.metrics["winner"] == "COST_EFFICIENT"
    assert any("No dispatch" in item for item in decision.limitations)
    for strategy in decision.metrics["strategies"].values():
        assert strategy["total_known_cost"] <= strategy["budget_limit"]
        blocked = [
            action for action in strategy["actions"] if action["status"] == "BLOCKED"
        ]
        assert any("Repair failed signal" in action["title"] for action in blocked)
        assert any("UNKNOWN availability" in warning for warning in strategy["warnings"])
    cost_actions = decision.metrics["strategies"]["COST_EFFICIENT"]["actions"]
    by_title = {action["title"]: action for action in cost_actions}
    assert (
        by_title["Clean blocked drain"]["start_minute"]
        >= by_title["Inspect flooded drain"]["end_minute"]
    )
