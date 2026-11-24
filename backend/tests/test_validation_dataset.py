"""Dataset normalization, snapshot integrity, and provenance tests."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from app.validation import service as validation_service
from app.validation.dataset import (
    canonical_hash,
    load_snapshot,
    normalize_nyc311_record,
    normalize_rows,
    write_snapshot,
)
from app.validation.service import ValidationError, dataset_records


def _row(**overrides: object) -> dict:
    row = {
        "unique_key": "311-1",
        "created_date": "2025-02-01T12:00:00.000",
        "complaint_type": "Street Condition",
        "descriptor": "Pothole",
        "latitude": "40.6900",
        "longitude": "-73.9800",
        "borough": "BROOKLYN",
        "status": "Open",
    }
    row.update(overrides)
    return row


def test_normalization_validates_bounds_and_period() -> None:
    record = normalize_nyc311_record(_row())
    assert record["external_id"] == "311-1"
    assert record["category"] == "ROADS"
    assert record["severity"] == "MEDIUM"
    assert record["status"] == "OPEN"
    assert record["observed_at"].startswith("2025-02-01T12:00:00")
    with pytest.raises(ValueError, match="unsupported complaint_type"):
        normalize_nyc311_record(_row(complaint_type="Unknown type"))
    with pytest.raises(ValueError, match="outside the declared dataset period"):
        normalize_nyc311_record(_row(created_date="2025-05-01T00:00:00"))
    with pytest.raises(ValueError, match="outside the declared dataset region"):
        normalize_nyc311_record(_row(latitude="40.8000"))
    with pytest.raises(ValueError, match="invalid coordinates"):
        normalize_nyc311_record(_row(latitude="NaN"))


def test_normalization_deduplicates_and_records_rejections() -> None:
    records, rejected = normalize_rows(
        [
            _row(),
            _row(created_date="2025-02-01T13:00:00.000"),
            _row(unique_key="311-2", complaint_type="Rodent"),
            _row(unique_key="311-3", latitude="0"),
        ]
    )
    assert [item["external_id"] for item in records] == ["311-1", "311-2"]
    assert len(rejected) == 2
    assert "duplicate unique_key" in rejected[0]["reason"]
    assert "outside the declared dataset region" in rejected[1]["reason"]


def test_snapshot_round_trip_checks_hash_and_count(tmp_path: Path) -> None:
    record = normalize_nyc311_record(_row())
    path = tmp_path / "snapshot.json.gz"
    digest = write_snapshot(
        path,
        records=[record],
        rejected=[{"reason": "fixture"}],
        metadata={"retrieved_at": "2025-04-01T00:00:00+00:00"},
    )
    assert digest == canonical_hash([record])
    payload = load_snapshot(path)
    assert payload["record_count"] == 1
    assert payload["snapshot_sha256"] == digest

    with gzip.open(path, "rb") as handle:
        tampered = json.load(handle)
    tampered["records"][0]["category"] = "SANITATION"
    with gzip.open(path, "wb") as handle:
        handle.write(json.dumps(tampered).encode("utf-8"))
    with pytest.raises(ValueError, match="checksum mismatch"):
        load_snapshot(path)


def test_dataset_records_reject_unsafe_snapshot_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(validation_service, "DATA_ROOT", tmp_path / "allowed")
    dataset = type(
        "Dataset",
        (),
        {
            "snapshot_path": "../../etc/passwd",
            "snapshot_sha256": "0" * 64,
            "record_count": 1,
            "source_id": None,
        },
    )()
    with pytest.raises(ValidationError) as error:
        dataset_records(None, dataset)  # type: ignore[arg-type]
    assert error.value.code == "unsafe_snapshot_path"
