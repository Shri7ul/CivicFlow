"""Pinned multi-region NYC 311 dataset specs and snapshot integrity tests."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.validation.dataset import (
    NYC311_DATASETS,
    NYC311_SPEC,
    canonical_hash,
    load_snapshot,
    normalize_nyc311_record,
    snapshot_path,
)

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_declares_the_four_pinned_public_datasets() -> None:
    assert set(NYC311_DATASETS) == {
        "nyc311-brooklyn-2025q1",
        "nyc311-brooklyn-2025q2",
        "nyc311-manhattan-2025q2",
        "nyc311-staten-island-2025q1",
    }
    assert NYC311_SPEC.dataset_key == "nyc311-brooklyn-2025q1"
    for key, spec in NYC311_DATASETS.items():
        assert spec.dataset_key == key
        assert spec.name and spec.description and spec.region
        assert spec.source_url.startswith("https://")
        assert "public" in spec.license_note.lower()
        assert spec.period_start < spec.period_end
        assert spec.period_start.tzinfo is not None
        assert spec.period_start < datetime(2026, 1, 1, tzinfo=timezone.utc)
        assert spec.bbox[0] < spec.bbox[2] and spec.bbox[1] < spec.bbox[3]
        assert spec.snapshot_filename.endswith(".json.gz")
        assert "/" not in spec.snapshot_filename
        assert spec.selected_types


def test_dataset_specs_are_immutable() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        NYC311_SPEC.bbox = (0.0, 0.0, 1.0, 1.0)  # type: ignore[misc]


def test_regions_do_not_overlap_in_the_same_period() -> None:
    periods = {}
    for spec in NYC311_DATASETS.values():
        periods.setdefault(spec.dataset_key, []).append(spec.period_start)
    brooklyn_q1 = NYC311_DATASETS["nyc311-brooklyn-2025q1"]
    brooklyn_q2 = NYC311_DATASETS["nyc311-brooklyn-2025q2"]
    assert brooklyn_q1.bbox == brooklyn_q2.bbox
    assert brooklyn_q1.period_end < brooklyn_q2.period_start
    manhattan = NYC311_DATASETS["nyc311-manhattan-2025q2"]
    assert manhattan.bbox != brooklyn_q2.bbox


def test_every_committed_snapshot_matches_its_declared_scope() -> None:
    for key, spec in NYC311_DATASETS.items():
        path = snapshot_path(BACKEND_ROOT, spec)
        assert path.exists(), f"missing snapshot for {key}"
        payload = load_snapshot(path)
        assert payload["dataset_key"] == key
        assert payload["metadata"]["query"]["bbox"] == list(spec.bbox)
        assert payload["metadata"]["request_url"].startswith(spec.source_url)
        assert payload["license_note"] == spec.license_note
        assert payload["period_start"] == spec.period_start.isoformat()
        assert payload["period_end"] == spec.period_end.isoformat()
        assert payload["snapshot_sha256"] == canonical_hash(payload["records"])
        assert payload["record_count"] == len(payload["records"])
        assert payload["record_count"] > 0
        assert payload["rejected_count"] >= 0
        assert len(payload["snapshot_sha256"]) == 64
        assert payload["metadata"]["retrieved_at"]
        for record in payload["records"]:
            assert spec.bbox[0] <= record["latitude"] <= spec.bbox[2]
            assert spec.bbox[1] <= record["longitude"] <= spec.bbox[3]
            observed = datetime.fromisoformat(record["observed_at"])
            assert spec.period_start <= observed <= spec.period_end
            assert record["complaint_type"] in spec.selected_types
            assert record["external_id"]


def test_normalization_rejects_rows_from_another_dataset() -> None:
    row = {
        "unique_key": "311-phase9-1",
        "created_date": "2025-04-15T12:00:00.000",
        "complaint_type": "Street Condition",
        "descriptor": "Pothole",
        "latitude": "40.6900",
        "longitude": "-73.9800",
        "borough": "BROOKLYN",
        "status": "Open",
    }
    manhattan = NYC311_DATASETS["nyc311-manhattan-2025q2"]
    with pytest.raises(ValueError, match="outside the declared dataset region"):
        normalize_nyc311_record(row, manhattan)
    brooklyn_q2 = NYC311_DATASETS["nyc311-brooklyn-2025q2"]
    assert normalize_nyc311_record(row, brooklyn_q2)["external_id"] == "311-phase9-1"