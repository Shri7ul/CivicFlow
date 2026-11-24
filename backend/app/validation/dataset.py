"""NYC 311 dataset normalization and reproducible snapshot I/O.

This module is intentionally limited to public, aggregate service-request data.
It never reads citizen accounts, evidence, or operational incident records.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from app.models import IncidentCategory, IncidentSeverity, IncidentStatus

NYC311_DATASET_KEY = "nyc311-brooklyn-2025q1"
NYC311_SOURCE_URL = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"
NYC311_SCHEMA_VERSION = "nyc311-normalized-v1"
NYC311_REGION = "Brooklyn, New York City (bbox 40.680,-73.990 to 40.710,-73.950)"
NYC311_PERIOD_START = datetime(2025, 1, 1, tzinfo=timezone.utc)
NYC311_PERIOD_END = datetime(2025, 3, 31, 23, 59, 59, tzinfo=timezone.utc)
NYC311_BBOX = (40.680, -73.990, 40.710, -73.950)
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


def normalize_nyc311_record(row: dict) -> dict:
    """Validate and normalize one public 311 row without inventing fields."""
    complaint_type = str(row.get("complaint_type") or "").strip()
    if complaint_type not in CATEGORY_MAP:
        raise ValueError(f"unsupported complaint_type: {complaint_type!r}")
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
    if not NYC311_PERIOD_START <= created_at <= NYC311_PERIOD_END:
        raise ValueError("timestamp outside the declared dataset period")
    if not (
        NYC311_BBOX[0] <= latitude <= NYC311_BBOX[2]
        and NYC311_BBOX[1] <= longitude <= NYC311_BBOX[3]
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


def normalize_rows(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    records: dict[str, dict] = {}
    rejected: list[dict] = []
    for index, row in enumerate(rows):
        try:
            record = normalize_nyc311_record(row)
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


def fetch_nyc311_rows(*, limit: int) -> tuple[list[dict], dict]:
    quoted = "','".join(NYC311_SELECTED_TYPES)
    where = (
        "created_date between '2025-01-01T00:00:00' and '2025-03-31T23:59:59' "
        "AND latitude between 40.680 and 40.710 "
        "AND longitude between -73.990 and -73.950 "
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
    url = f"{NYC311_SOURCE_URL}?{urlencode(params)}"
    with urlopen(url, timeout=180) as response:  # noqa: S310 - fixed public URL
        rows = json.load(response)
    metadata = {
        "request_url": url,
        "query": {
            "period_start": NYC311_PERIOD_START.isoformat(),
            "period_end": NYC311_PERIOD_END.isoformat(),
            "bbox": list(NYC311_BBOX),
            "complaint_types": list(NYC311_SELECTED_TYPES),
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


def snapshot_path(backend_root: Path) -> Path:
    return (
        backend_root
        / "data"
        / "validation"
        / "nyc311_brooklyn_2025q1.json.gz"
    )


def write_snapshot(
    path: Path,
    *,
    records: list[dict],
    rejected: list[dict],
    metadata: dict,
) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = canonical_hash(records)
    payload = {
        "dataset_key": NYC311_DATASET_KEY,
        "schema_version": NYC311_SCHEMA_VERSION,
        "source_url": NYC311_SOURCE_URL,
        "license_note": NYC311_LICENSE_NOTE,
        "region": NYC311_REGION,
        "period_start": NYC311_PERIOD_START.isoformat(),
        "period_end": NYC311_PERIOD_END.isoformat(),
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


def validate_normalized_record(record: dict) -> None:
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
        category = IncidentCategory(str(record["category"]))
        severity = IncidentSeverity(str(record["severity"]))
        IncidentStatus(str(record["status"]))
        latitude = float(record["latitude"])
        longitude = float(record["longitude"])
    except (TypeError, ValueError) as error:
        raise ValueError("snapshot record has invalid typed fields") from error
    if not NYC311_PERIOD_START <= observed <= NYC311_PERIOD_END:
        raise ValueError("snapshot record timestamp outside the declared period")
    if not (
        math.isfinite(latitude)
        and math.isfinite(longitude)
        and NYC311_BBOX[0] <= latitude <= NYC311_BBOX[2]
        and NYC311_BBOX[1] <= longitude <= NYC311_BBOX[3]
    ):
        raise ValueError("snapshot record coordinates outside the declared region")
    if category is None or severity is None:  # pragma: no cover - enum guards
        raise ValueError("snapshot record category/severity invalid")


def validate_normalized_records(records: list[dict]) -> None:
    seen: set[str] = set()
    for record in records:
        validate_normalized_record(record)
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
    validate_normalized_records(records)
    return payload
