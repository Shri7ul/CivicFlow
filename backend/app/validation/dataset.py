"""Parameterized NYC 311 dataset normalization and reproducible snapshot I/O.

The Phase 8 Brooklyn Q1 specification remains the default for compatibility.
Phase 9 adds independently pinned region/period snapshots rather than silently
reinterpreting an existing dataset key.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from app.models import IncidentCategory, IncidentSeverity, IncidentStatus

NYC311_SOURCE_URL = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"
NYC311_SCHEMA_VERSION = "nyc311-normalized-v1"
NYC311_LICENSE_NOTE = (
    "NYC Open Data / NYC 311 Service Requests. Public municipal open data; "
    "see https://opendata.cityofnewyork.us/overview/#termsofuse. The Socrata "
    "view metadata did not expose an SPDX license field, so this project does "
    "not assert a specific license beyond the portal terms."
)
NYC311_SELECTED_TYPES = (
    "Street Condition",
    "Traffic Signal Condition",
    "Water System",
    "Sewer",
    "Rodent",
    "Dirty Condition",
    "Missed Collection",
    "UNSANITARY CONDITION",
    "HEAT/HOT WATER",
    "Street Light Condition",
    "Curb Condition",
    "Sidewalk Condition",
)


@dataclass(frozen=True)
class NYC311DatasetSpec:
    dataset_key: str
    name: str
    description: str
    region: str
    bbox: tuple[float, float, float, float]
    period_start: datetime
    period_end: datetime
    snapshot_filename: str
    selected_types: tuple[str, ...] = NYC311_SELECTED_TYPES

    @property
    def source_url(self) -> str:
        return NYC311_SOURCE_URL

    @property
    def license_note(self) -> str:
        return NYC311_LICENSE_NOTE


def _utc(year: int, month: int, day: int, hour: int = 0) -> datetime:
    return datetime(year, month, day, hour, tzinfo=timezone.utc)


NYC311_BROOKLYN_Q1 = NYC311DatasetSpec(
    dataset_key="nyc311-brooklyn-2025q1",
    name="NYC 311 Brooklyn Q1 2025 validation slice",
    description=(
        "Bounded public 311 service-request activity used to validate "
        "spatial-temporal risk ranking and sensitivity. Not verified hazard "
        "impact and not municipal ground truth."
    ),
    region="Brooklyn, New York City (bbox 40.680,-73.990 to 40.710,-73.950)",
    bbox=(40.680, -73.990, 40.710, -73.950),
    period_start=_utc(2025, 1, 1),
    period_end=datetime(2025, 3, 31, 23, 59, 59, tzinfo=timezone.utc),
    snapshot_filename="nyc311_brooklyn_2025q1.json.gz",
)
NYC311_BROOKLYN_Q2 = NYC311DatasetSpec(
    dataset_key="nyc311-brooklyn-2025q2",
    name="NYC 311 Brooklyn Q2 2025 temporal validation slice",
    description=(
        "Same Brooklyn bbox as the Phase 8 slice but a later quarter, used as "
        "an external temporal validation period. Public complaint activity is "
        "not verified hazard impact."
    ),
    region="Brooklyn, New York City (bbox 40.680,-73.990 to 40.710,-73.950)",
    bbox=(40.680, -73.990, 40.710, -73.950),
    period_start=_utc(2025, 4, 1),
    period_end=datetime(2025, 6, 30, 23, 59, 59, tzinfo=timezone.utc),
    snapshot_filename="nyc311_brooklyn_2025q2.json.gz",
)
NYC311_MANHATTAN_Q2 = NYC311DatasetSpec(
    dataset_key="nyc311-manhattan-2025q2",
    name="NYC 311 Manhattan Q2 2025 cross-region slice",
    description=(
        "Bounded Lower East Side/Midtown South public 311 activity used for "
        "cross-region external validation. Complaint activity is not hazard "
        "impact ground truth."
    ),
    region="Manhattan, New York City (bbox 40.705,-73.995 to 40.745,-73.955)",
    bbox=(40.705, -73.995, 40.745, -73.955),
    period_start=_utc(2025, 4, 1),
    period_end=datetime(2025, 6, 30, 23, 59, 59, tzinfo=timezone.utc),
    snapshot_filename="nyc311_manhattan_2025q2.json.gz",
)
NYC311_STATEN_ISLAND_Q1 = NYC311DatasetSpec(
    dataset_key="nyc311-staten-island-2025q1",
    name="NYC 311 Staten Island Q1 2025 sparse slice",
    description=(
        "Bounded Staten Island public 311 activity selected to exercise a "
        "sparser geography than the original Brooklyn slice. Not verified "
        "hazard impact."
    ),
    region="Staten Island, New York City (bbox 40.550,-74.200 to 40.640,-74.100)",
    bbox=(40.550, -74.200, 40.640, -74.100),
    period_start=_utc(2025, 1, 1),
    period_end=datetime(2025, 3, 31, 23, 59, 59, tzinfo=timezone.utc),
    snapshot_filename="nyc311_staten_island_2025q1.json.gz",
)

NYC311_DATASETS: dict[str, NYC311DatasetSpec] = {
    spec.dataset_key: spec
    for spec in (
        NYC311_BROOKLYN_Q1,
        NYC311_BROOKLYN_Q2,
        NYC311_MANHATTAN_Q2,
        NYC311_STATEN_ISLAND_Q1,
    )
}
NYC311_SPEC = NYC311_BROOKLYN_Q1
NYC311_DATASET_KEY = NYC311_SPEC.dataset_key
NYC311_REGION = NYC311_SPEC.region
NYC311_PERIOD_START = NYC311_SPEC.period_start
NYC311_PERIOD_END = NYC311_SPEC.period_end
NYC311_BBOX = NYC311_SPEC.bbox

CATEGORY_MAP: dict[str, IncidentCategory] = {
    "Street Condition": IncidentCategory.ROADS,
    "Traffic Signal Condition": IncidentCategory.ROADS,
    "Street Light Condition": IncidentCategory.ROADS,
    "Curb Condition": IncidentCategory.ROADS,
    "Sidewalk Condition": IncidentCategory.ROADS,
    "Water System": IncidentCategory.DRAINAGE,
    "Sewer": IncidentCategory.DRAINAGE,
    "Rodent": IncidentCategory.SANITATION,
    "Dirty Condition": IncidentCategory.SANITATION,
    "Missed Collection": IncidentCategory.SANITATION,
    "UNSANITARY CONDITION": IncidentCategory.SANITATION,
    "HEAT/HOT WATER": IncidentCategory.UTILITIES,
}

SEVERITY_MAP: dict[str, IncidentSeverity] = {
    "Street Condition": IncidentSeverity.MEDIUM,
    "Curb Condition": IncidentSeverity.MEDIUM,
    "Sidewalk Condition": IncidentSeverity.MEDIUM,
    "Street Light Condition": IncidentSeverity.MEDIUM,
    "Traffic Signal Condition": IncidentSeverity.HIGH,
    "Water System": IncidentSeverity.HIGH,
    "Sewer": IncidentSeverity.HIGH,
    "HEAT/HOT WATER": IncidentSeverity.HIGH,
    "Rodent": IncidentSeverity.MEDIUM,
    "Dirty Condition": IncidentSeverity.LOW,
    "Missed Collection": IncidentSeverity.LOW,
    "UNSANITARY CONDITION": IncidentSeverity.MEDIUM,
}


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _status(value: str | None) -> IncidentStatus:
    normalized = (value or "").strip().upper()
    if normalized in {"CLOSED", "RESOLVED"}:
        return IncidentStatus.CLOSED
    if normalized in {"IN PROGRESS", "ASSIGNED"}:
        return IncidentStatus.IN_PROGRESS
    return IncidentStatus.OPEN


def _spec(spec: NYC311DatasetSpec | None) -> NYC311DatasetSpec:
    return spec or NYC311_SPEC


def normalize_nyc311_record(
    row: dict, spec: NYC311DatasetSpec | None = None
) -> dict:
    """Validate and normalize one public 311 row without inventing fields."""
    spec = _spec(spec)
    complaint_type = str(row.get("complaint_type") or "").strip()
    if complaint_type not in CATEGORY_MAP:
        raise ValueError(f"unsupported complaint_type: {complaint_type!r}")
    if complaint_type not in spec.selected_types:
        raise ValueError(f"complaint_type outside the declared dataset: {complaint_type!r}")
    external_id = str(row.get("unique_key") or "").strip()
    if not external_id:
        raise ValueError("unique_key is required")
    latitude = float(row.get("latitude"))
    longitude = float(row.get("longitude"))
    if not (
        math.isfinite(latitude)
        and math.isfinite(longitude)
        and -90 <= latitude <= 90
        and -180 <= longitude <= 180
    ):
        raise ValueError("invalid coordinates")
    created_at = _parse_timestamp(str(row.get("created_date") or ""))
    if not spec.period_start <= created_at <= spec.period_end:
        raise ValueError("timestamp outside the declared dataset period")
    if not (
        spec.bbox[0] <= latitude <= spec.bbox[2]
        and spec.bbox[1] <= longitude <= spec.bbox[3]
    ):
        raise ValueError("coordinate outside the declared dataset region")
    return {
        "external_id": external_id,
        "observed_at": created_at.isoformat(),
        "complaint_type": complaint_type,
        "descriptor": (row.get("descriptor") or "").strip() or None,
        "latitude": round(latitude, 7),
        "longitude": round(longitude, 7),
        "borough": (row.get("borough") or "").strip() or None,
        "source_status": (row.get("status") or "").strip() or None,
        "status": _status(row.get("status")).value,
        "category": CATEGORY_MAP[complaint_type].value,
        "severity": SEVERITY_MAP[complaint_type].value,
    }


def canonical_hash(records: list[dict]) -> str:
    payload = json.dumps(
        records, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def normalize_rows(
    rows: list[dict], spec: NYC311DatasetSpec | None = None
) -> tuple[list[dict], list[dict]]:
    spec = _spec(spec)
    records: dict[str, dict] = {}
    rejected: list[dict] = []
    for index, row in enumerate(rows):
        try:
            record = normalize_nyc311_record(row, spec)
        except (TypeError, ValueError) as error:
            rejected.append(
                {
                    "index": index,
                    "external_id": str(row.get("unique_key") or ""),
                    "reason": str(error),
                }
            )
            continue
        if record["external_id"] in records:
            rejected.append(
                {
                    "index": index,
                    "external_id": record["external_id"],
                    "reason": "duplicate unique_key",
                }
            )
            continue
        records[record["external_id"]] = record
    normalized = sorted(
        records.values(),
        key=lambda item: (item["observed_at"], item["external_id"]),
    )
    return normalized, rejected


def fetch_nyc311_rows(
    *, limit: int, spec: NYC311DatasetSpec | None = None
) -> tuple[list[dict], dict]:
    spec = _spec(spec)
    quoted = "','".join(spec.selected_types)
    where = (
        f"created_date between '{spec.period_start.strftime('%Y-%m-%dT%H:%M:%S')}' "
        f"and '{spec.period_end.strftime('%Y-%m-%dT%H:%M:%S')}' "
        f"AND latitude between {spec.bbox[0]} and {spec.bbox[2]} "
        f"AND longitude between {spec.bbox[1]} and {spec.bbox[3]} "
        f"AND complaint_type in ('{quoted}')"
    )
    params = {
        "$select": (
            "unique_key,created_date,complaint_type,descriptor,"
            "latitude,longitude,borough,status"
        ),
        "$where": where,
        "$order": "created_date,unique_key",
        "$limit": str(limit + 1),
    }
    url = f"{spec.source_url}?{urlencode(params)}"
    with urlopen(url, timeout=180) as response:  # noqa: S310 - fixed public URL
        rows = json.load(response)
    metadata = {
        "request_url": url,
        "query": {
            "dataset_key": spec.dataset_key,
            "period_start": spec.period_start.isoformat(),
            "period_end": spec.period_end.isoformat(),
            "bbox": list(spec.bbox),
            "complaint_types": list(spec.selected_types),
            "order": "created_date,unique_key",
        },
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "row_count_raw": len(rows),
        "limit_plus_one": limit + 1,
    }
    if len(rows) > limit:
        raise ValueError(
            "NYC 311 query returned more rows than the configured validation cap"
        )
    return rows, metadata


def snapshot_path(
    backend_root: Path, spec: NYC311DatasetSpec | None = None
) -> Path:
    return backend_root / "data" / "validation" / _spec(spec).snapshot_filename


def write_snapshot(
    path: Path,
    *,
    records: list[dict],
    rejected: list[dict],
    metadata: dict,
    spec: NYC311DatasetSpec | None = None,
) -> str:
    spec = _spec(spec)
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = canonical_hash(records)
    payload = {
        "dataset_key": spec.dataset_key,
        "schema_version": NYC311_SCHEMA_VERSION,
        "source_url": spec.source_url,
        "license_note": spec.license_note,
        "region": spec.region,
        "bbox": list(spec.bbox),
        "period_start": spec.period_start.isoformat(),
        "period_end": spec.period_end.isoformat(),
        "snapshot_sha256": digest,
        "record_count": len(records),
        "rejected_count": len(rejected),
        "rejected": rejected[:100],
        "metadata": metadata,
        "records": records,
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    with gzip.open(path, "wb") as handle:
        handle.write(encoded)
    return digest


MAX_SNAPSHOT_BYTES = 50 * 1024 * 1024


def _snapshot_constraints(
    payload: dict,
) -> tuple[datetime, datetime, tuple[float, float, float, float]]:
    period_start = _parse_timestamp(str(payload["period_start"]))
    period_end = _parse_timestamp(str(payload["period_end"]))
    bbox_payload = payload.get("bbox")
    bbox = (
        tuple(float(value) for value in bbox_payload)
        if isinstance(bbox_payload, list) and len(bbox_payload) == 4
        else NYC311_BBOX
    )
    if not (
        -90 <= bbox[0] < bbox[2] <= 90
        and -180 <= bbox[1] < bbox[3] <= 180
    ):
        raise ValueError("validation snapshot bbox is invalid")
    return period_start, period_end, bbox


def validate_normalized_record(
    record: dict,
    *,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
    bbox: tuple[float, float, float, float] | None = None,
) -> None:
    period_start = period_start or NYC311_PERIOD_START
    period_end = period_end or NYC311_PERIOD_END
    bbox = bbox or NYC311_BBOX
    required = (
        "external_id",
        "observed_at",
        "complaint_type",
        "latitude",
        "longitude",
        "status",
        "category",
        "severity",
    )
    if not isinstance(record, dict):
        raise ValueError("snapshot record must be an object")
    for key in required:
        if record.get(key) in (None, ""):
            raise ValueError(f"snapshot record missing {key}")
    if not str(record["external_id"]).strip():
        raise ValueError("snapshot record has a blank external_id")
    try:
        observed = _parse_timestamp(str(record["observed_at"]))
        IncidentCategory(str(record["category"]))
        IncidentSeverity(str(record["severity"]))
        IncidentStatus(str(record["status"]))
        latitude = float(record["latitude"])
        longitude = float(record["longitude"])
    except (TypeError, ValueError) as error:
        raise ValueError("snapshot record has invalid typed fields") from error
    if observed < period_start or observed > period_end:
        raise ValueError("snapshot record timestamp outside the declared period")
    if not (
        math.isfinite(latitude)
        and math.isfinite(longitude)
        and bbox[0] <= latitude <= bbox[2]
        and bbox[1] <= longitude <= bbox[3]
    ):
        raise ValueError("snapshot record coordinates outside the declared region")


def validate_normalized_records(
    records: list[dict],
    *,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
    bbox: tuple[float, float, float, float] | None = None,
) -> None:
    seen: set[str] = set()
    for record in records:
        validate_normalized_record(
            record,
            period_start=period_start,
            period_end=period_end,
            bbox=bbox,
        )
        external_id = str(record["external_id"])
        if external_id in seen:
            raise ValueError("snapshot contains duplicate external_id values")
        seen.add(external_id)


def load_snapshot(path: Path) -> dict:
    if path.stat().st_size > MAX_SNAPSHOT_BYTES:
        raise ValueError("validation snapshot exceeds the maximum compressed size")
    with gzip.open(path, "rb") as handle:
        payload = json.load(handle)
    records = payload.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("validation snapshot has no records")
    if payload.get("schema_version") != NYC311_SCHEMA_VERSION:
        raise ValueError("validation snapshot schema version is unsupported")
    digest = canonical_hash(records)
    if digest != payload.get("snapshot_sha256"):
        raise ValueError("validation snapshot checksum mismatch")
    if len(records) != payload.get("record_count"):
        raise ValueError("validation snapshot record count mismatch")
    period_start, period_end, bbox = _snapshot_constraints(payload)
    validate_normalized_records(
        records, period_start=period_start, period_end=period_end, bbox=bbox
    )
    return payload
