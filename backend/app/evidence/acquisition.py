"""Allowlisted, bounded acquisition of real infrastructure data.

Only hard-coded source definitions may be fetched. There is no client-supplied
URL path. Redirects are not followed, response bytes are capped, transient
failures are retried a bounded number of times, and failed acquisitions never
mark an older valid snapshot as superseded or replace its assets.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
import uuid
from dataclasses import dataclass
from urllib.parse import quote
from datetime import datetime, timezone
from typing import Any, Callable

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser
from app.geo.contexts import BD_DHAKA, DHAKA_OSM_RESEARCH_CELL
from app.governance.errors import GovernanceError
from app.models.enums import (
    AssetType,
    EvidenceQualityStatus,
    EvidenceSnapshotKind,
    EvidenceSnapshotStatus,
    SnapshotVerificationStatus,
)
from app.models.evidence import EvidenceSnapshot, EvidenceSnapshotEvent
from app.models.infrastructure import InfrastructureAsset
from app.models.pilot import InfrastructureSource, InfrastructureSourceEvent

NYC_BRIDGE_URL = (
    "https://data.cityofnewyork.us/resource/4yue-vjfc.json"
    "?$limit=5000&$order=bin"
)
NYC_BRIDGE_SOURCE = "nyc-dot-bridge-ratings"
MAX_RESPONSE_BYTES = 12_000_000
MAX_RECORDS = 5_000
NYC_BBOX = (40.4, -74.3, 41.0, -73.6)  # lat_min, lon_min, lat_max, lon_max
BRIDGE_SCHEMA_VERSION = "nyc-dot-bridge-ratings-v1"
BRIDGE_LICENSE = (
    "NYC Open Data public dataset published by the NYC Department of "
    "Transportation. Use is subject to the NYC Open Data Terms of Use; no SPDX "
    "license is declared by the portal metadata. Attribution: NYC DOT."
)


@dataclass(frozen=True)
class SourceDefinition:
    source_key: str
    kind: EvidenceSnapshotKind
    url: str
    provider: str
    license_note: str
    schema_version: str
    geographic_coverage: str
    crs: str
    update_frequency: str
    known_limitations: str
    # Geography and normalizer identity. Defaults preserve the historical NYC
    # bridge definition exactly; new sources must declare them explicitly.
    geographic_context_key: str = "US-NYC"
    normalization_kind: str = "nyc_bridges"
    display_name: str = "NYC DOT Bridge Ratings"
    category: str = "BRIDGES"
    access_method: str = "Socrata HTTPS JSON"
    source_id: str = "4yue-vjfc"
    dataset_version_prefix: str = "4yue-vjfc"


# Pinned, read-only OpenStreetMap Overpass query for a small central-Dhaka
# research cell. This is infrastructure *context*, not authoritative civic
# infrastructure and never an operational incident or verified ground truth.
_OSM_S, _OSM_W, _OSM_N, _OSM_E = DHAKA_OSM_RESEARCH_CELL.as_latlon()
DHAKA_OSM_QUERY = (
    "[out:json][timeout:25][maxsize:8000000];"
    f"(way[highway]({_OSM_S},{_OSM_W},{_OSM_N},{_OSM_E});"
    f"way[bridge]({_OSM_S},{_OSM_W},{_OSM_N},{_OSM_E});"
    f"way[waterway]({_OSM_S},{_OSM_W},{_OSM_N},{_OSM_E}););"
    "out geom;"
)
DHAKA_OSM_SOURCE = "dhaka-osm-context-v1"
DHAKA_OSM_URL = (
    "https://overpass-api.de/api/interpreter?data=" + quote(DHAKA_OSM_QUERY, safe="")
)
DHAKA_OSM_LICENSE = (
    "© OpenStreetMap contributors, available under the Open Database License "
    "(ODbL 1.0): https://www.openstreetmap.org/copyright. Retrieved through "
    "the public Overpass API (https://overpass-api.de/) under its usage "
    "policy. Attribution is mandatory. OSM is community-mapped context: it is "
    "not an authoritative DNCC/DSCC/RAJUK/WASA asset register, has no "
    "guaranteed completeness or update frequency, and is not field-verified."
)

SOURCES: dict[str, SourceDefinition] = {
    DHAKA_OSM_SOURCE: SourceDefinition(
        source_key=DHAKA_OSM_SOURCE,
        kind=EvidenceSnapshotKind.INFRASTRUCTURE,
        url=DHAKA_OSM_URL,
        provider="OpenStreetMap contributors (via Overpass API)",
        license_note=DHAKA_OSM_LICENSE,
        schema_version="osm-overpass-dhaka-context-v1",
        geographic_coverage=(
            f"Central Dhaka research cell, bbox {DHAKA_OSM_RESEARCH_CELL.as_geojson()} "
            "(GeoJSON west,south,east,north). Not an administrative boundary."
        ),
        crs="EPSG:4326 (OSM/Overpass WGS84 geometry)",
        update_frequency="Community-mapped; no guaranteed refresh interval",
        known_limitations=(
            "Bounded to a small central-Dhaka research cell. Community mapping "
            "quality and completeness are unverified. Records are map features "
            "used for infrastructure context only, never verified field assets, "
            "incidents, complaints, dispatch targets or safety claims."
        ),
        geographic_context_key=BD_DHAKA.key,
        normalization_kind="osm_context",
        display_name="Dhaka OSM infrastructure context (research cell)",
        category="OSM_CONTEXT",
        access_method="Pinned Overpass interpreter GET; redirects disabled",
        source_id="overpass-dhaka-context-v1",
        dataset_version_prefix="osm-dhaka-research-cell",
    ),
    NYC_BRIDGE_SOURCE: SourceDefinition(
        source_key=NYC_BRIDGE_SOURCE,
        kind=EvidenceSnapshotKind.INFRASTRUCTURE,
        url=NYC_BRIDGE_URL,
        provider="NYC Department of Transportation (DOT)",
        license_note=BRIDGE_LICENSE,
        schema_version=BRIDGE_SCHEMA_VERSION,
        geographic_coverage="New York City, all five boroughs (bridge records)",
        crs="EPSG:4326 (validated coordinates; portal does not declare a CRS field)",
        update_frequency="Portal dataset updated irregularly; inspection dates vary",
        known_limitations=(
            "Historical inspection rows repeat each BIN. Only the latest inspection "
            "per BIN is normalized. Many recent rows omit coordinates; the most "
            "recent valid coordinate for that BIN is used and flagged. Ratings are "
            "inspection observations, not a real-time condition or dispatch signal."
        ),
    )
}


class AcquisitionError(Exception):
    """Bounded acquisition failed without modifying current data."""

    def __init__(self, message: str, *, code: str = "acquisition_failed") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return _hash_bytes(encoded)


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _safe_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _valid_coordinates(row: dict[str, Any]) -> tuple[float, float] | None:
    lat = _safe_float(row.get("x_coord_lat"))
    lon = _safe_float(row.get("y_coord_lon"))
    if lat is None or lon is None:
        return None
    if not (NYC_BBOX[0] <= lat <= NYC_BBOX[2] and NYC_BBOX[1] <= lon <= NYC_BBOX[3]):
        return None
    return lat, lon


def _assert_allowed(url: str) -> None:
    allowed = {definition.url for definition in SOURCES.values()}
    if url not in allowed:
        raise AcquisitionError("Source URL is not allowlisted", code="source_not_allowed")


def fetch_source_bytes(url: str) -> bytes:
    """Fetch an allowlisted JSON endpoint without redirects or unbounded bodies."""

    _assert_allowed(url)
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            chunks: list[bytes] = []
            total = 0
            with httpx.stream(
                "GET",
                url,
                timeout=httpx.Timeout(45.0, connect=10.0),
                follow_redirects=False,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "CivicFlow-Evidence/1.0 (research; contact: civicflow)",
                },
            ) as response:
                if response.status_code in {429, 500, 502, 503, 504} and attempt == 0:
                    last_error = AcquisitionError(
                        f"Source returned HTTP {response.status_code}",
                        code="source_unavailable",
                    )
                    time.sleep(0.5)
                    continue
                if response.status_code != 200:
                    raise AcquisitionError(
                        f"Source returned HTTP {response.status_code}",
                        code="source_unavailable",
                    )
                content_type = response.headers.get("content-type", "").lower()
                if "json" not in content_type:
                    raise AcquisitionError(
                        "Source did not return JSON", code="unexpected_content_type"
                    )
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > MAX_RESPONSE_BYTES:
                        raise AcquisitionError(
                            "Source response exceeded the size limit",
                            code="response_too_large",
                        )
                    chunks.append(chunk)
            if total == 0:
                raise AcquisitionError("Source returned an empty body", code="empty_response")
            return b"".join(chunks)
        except AcquisitionError as error:
            if error.code in {"source_unavailable", "response_too_large"} and attempt == 0:
                last_error = error
                continue
            raise
        except (httpx.TimeoutException, httpx.TransportError) as error:
            last_error = error
            if attempt == 0:
                continue
    raise AcquisitionError(
        f"Source acquisition failed: {type(last_error).__name__}",
        code="source_unavailable",
    )


def normalize_bridge_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Deterministically collapse inspection history to one record per BIN."""

    if not isinstance(rows, list):
        raise AcquisitionError("Bridge payload must be a JSON array", code="invalid_schema")
    if len(rows) > MAX_RECORDS:
        raise AcquisitionError("Bridge payload exceeds record limit", code="too_many_records")

    histories: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        bin_value = str(row.get("bin") or "").strip()
        if not bin_value:
            continue
        histories.setdefault(bin_value, []).append(row)

    normalized: list[dict[str, Any]] = []
    invalid_count = 0
    fallback_coordinates = 0
    missing_fields = 0
    periods: list[datetime] = []
    required = (
        "bin",
        "boro",
        "feature_carried",
        "feature_crossed",
        "inspection_date",
    )

    for bin_value, history in histories.items():
        def sort_key(item: dict[str, Any]) -> tuple[datetime, str, str]:
            return (
                _parse_datetime(item.get("inspection_date"))
                or datetime.min.replace(tzinfo=timezone.utc),
                str(item.get("rating_source") or ""),
                str(item.get("current_rating") or ""),
            )

        history = sorted(history, key=sort_key)
        latest = history[-1]
        coordinates = _valid_coordinates(latest)
        coordinate_source = "LATEST_INSPECTION"
        if coordinates is None:
            for prior in reversed(history[:-1]):
                coordinates = _valid_coordinates(prior)
                if coordinates is not None:
                    coordinate_source = "PRIOR_INSPECTION"
                    fallback_coordinates += 1
                    break
        if coordinates is None:
            invalid_count += 1
            continue
        if any(not str(latest.get(field) or "").strip() for field in required):
            invalid_count += 1
            continue
        inspected = _parse_datetime(latest.get("inspection_date"))
        if inspected is None:
            invalid_count += 1
            continue
        periods.append(inspected)
        missing_fields += sum(
            1 for field in ("feature_carried", "feature_crossed", "current_rating")
            if not str(latest.get(field) or "").strip()
        )
        lat, lon = coordinates
        carried = str(latest.get("feature_carried") or "").strip()
        crossed = str(latest.get("feature_crossed") or "").strip()
        current_rating = _safe_float(latest.get("current_rating"))
        name = f"{carried or 'Bridge'} over {crossed or 'unknown feature'}"[:200]
        normalized.append(
            {
                "external_id": bin_value,
                "asset_type": AssetType.BRIDGE.value,
                "name": name,
                "borough": str(latest.get("boro") or "").strip(),
                "feature_carried": carried,
                "feature_crossed": crossed,
                "bridge_type": str(latest.get("bridge_type") or "").strip() or None,
                "owner_code": str(latest.get("other_owner") or "").strip() or None,
                "spans": _safe_float(latest.get("spans")),
                "rating_source": str(latest.get("rating_source") or "").strip() or None,
                "current_rating": current_rating,
                "verbal_rating": str(latest.get("verbal_rating") or "").strip() or None,
                "general_recommendation": _safe_float(latest.get("general_recommendation")),
                "deck_area_sq_ft": _safe_float(latest.get("deck_area_sq_ft")),
                "replacement_cost": _safe_float(latest.get("replacement_cost")),
                "inspection_date": inspected.isoformat(),
                "latitude": lat,
                "longitude": lon,
                "coordinate_source": coordinate_source,
                "source_row_count": len(history),
            }
        )

    normalized.sort(key=lambda item: item["external_id"])
    ids = [item["external_id"] for item in normalized]
    duplicate_normalized = len(ids) - len(set(ids))
    valid_ratio = (len(normalized) / len(histories)) if histories else 0.0
    checks = [
        {
            "check": "records_present",
            "status": "PASS" if rows else "FAIL",
            "detail": f"{len(rows)} raw rows received.",
        },
        {
            "check": "bounded_records",
            "status": "PASS" if len(rows) <= MAX_RECORDS else "FAIL",
            "detail": f"Raw rows must not exceed {MAX_RECORDS}.",
        },
        {
            "check": "unique_external_ids",
            "status": "PASS" if duplicate_normalized == 0 else "FAIL",
            "detail": f"{duplicate_normalized} duplicate normalized BIN value(s).",
        },
        {
            "check": "coordinate_coverage",
            "status": "PASS" if valid_ratio >= 0.9 else ("WARN" if valid_ratio >= 0.5 else "FAIL"),
            "detail": (
                f"{len(normalized)} of {len(histories)} unique BINs have valid NYC "
                f"coordinates; {invalid_count} omitted."
            ),
        },
        {
            "check": "coordinate_fallback",
            "status": "WARN" if fallback_coordinates else "PASS",
            "detail": (
                f"{fallback_coordinates} record(s) used the most recent prior "
                "inspection with a valid coordinate."
            ),
        },
        {
            "check": "minimum_asset_count",
            "status": "PASS" if len(normalized) >= 100 else "FAIL",
            "detail": f"{len(normalized)} normalized assets; minimum 100.",
        },
        {
            "check": "inspection_dates",
            "status": "PASS" if periods else "FAIL",
            "detail": (
                f"Inspection dates range {min(periods).date()} to {max(periods).date()}."
                if periods
                else "No valid inspection dates."
            ),
        },
        {
            "check": "schema_required_fields",
            "status": "PASS" if invalid_count == 0 else "WARN",
            "detail": f"{invalid_count} record(s) omitted for missing required fields.",
        },
    ]
    if any(item["status"] == "FAIL" for item in checks):
        quality = EvidenceQualityStatus.FAIL
    elif any(item["status"] == "WARN" for item in checks):
        quality = EvidenceQualityStatus.WARN
    else:
        quality = EvidenceQualityStatus.PASS

    lats = [item["latitude"] for item in normalized]
    lons = [item["longitude"] for item in normalized]
    bbox = [min(lons), min(lats), max(lons), max(lats)] if normalized else []
    normalized_bytes = json.dumps(
        normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return {
        "records": normalized,
        "normalized_bytes": normalized_bytes,
        "bbox": bbox,
        "record_count": len(normalized),
        "raw_record_count": len(rows),
        "duplicate_count": max(len(rows) - len(histories), 0),
        "invalid_count": invalid_count,
        "missing_fields": missing_fields,
        "quality_status": quality,
        "quality_checks": checks,
        "data_period_start": min(periods) if periods else None,
        "data_period_end": max(periods) if periods else None,
        "crs": "EPSG:4326",
        "schema_fingerprint": _canonical_hash(sorted(rows[0].keys())) if rows and isinstance(rows[0], dict) else None,
    }


def _get_or_create_source(
    session: Session,
    definition: SourceDefinition,
    actor: AuthenticatedUser | None,
    retrieved_at: datetime,
) -> InfrastructureSource:
    source = session.scalar(
        select(InfrastructureSource).where(
            InfrastructureSource.source_key == definition.source_key
        )
    )
    if source is None:
        source = InfrastructureSource(
            source_key=definition.source_key,
            name=definition.display_name,
            category=definition.category,
            source_url=definition.url,
            provider=definition.provider,
            license_note=definition.license_note,
            retrieved_at=retrieved_at,
            dataset_version=f"{definition.dataset_version_prefix}@{retrieved_at.date().isoformat()}",
            geographic_coverage=definition.geographic_coverage,
            crs=definition.crs,
            schema_version=definition.schema_version,
            update_frequency=definition.update_frequency,
            known_limitations=definition.known_limitations,
            details={
                "access_method": definition.access_method,
                "source_id": definition.source_id,
                "geographic_context_key": definition.geographic_context_key,
                "acquisition": "allowlisted, bounded, no redirects",
            },
            created_by=actor.profile.id if actor else None,
        )
        session.add(source)
        session.flush()
    return source


def _snapshot_event(
    session: Session,
    snapshot: EvidenceSnapshot,
    action: str,
    from_status: EvidenceSnapshotStatus | None,
    to_status: EvidenceSnapshotStatus,
    actor: AuthenticatedUser | None,
    note: str | None,
) -> None:
    session.add(
        EvidenceSnapshotEvent(
            snapshot_id=snapshot.id,
            action=action,
            from_status=from_status,
            to_status=to_status,
            actor_id=actor.profile.id if actor else None,
            actor_email=actor.email if actor else None,
            note=note,
            created_at=datetime.now(timezone.utc),
        )
    )


def record_failure(
    session: Session,
    definition: SourceDefinition,
    actor: AuthenticatedUser | None,
    retrieved_at: datetime,
    reason: str,
) -> EvidenceSnapshot:
    source = _get_or_create_source(session, definition, actor, retrieved_at)
    snapshot = EvidenceSnapshot(
        snapshot_key=(
            f"{definition.source_key}-failed-{retrieved_at:%Y%m%dT%H%M%SZ}-"
            f"{uuid.uuid4().hex[:8]}"
        ),
        kind=definition.kind,
        status=EvidenceSnapshotStatus.FAILED,
        source_key=definition.source_key,
        source_url=definition.url,
        provider=definition.provider,
        license_note=definition.license_note,
        dataset_version=f"{definition.dataset_version_prefix}@{retrieved_at.date().isoformat()}",
        retrieved_at=retrieved_at,
        schema_version=definition.schema_version,
        geographic_context_key=definition.geographic_context_key,
        failure_reason=reason[:2000],
        quality_status=EvidenceQualityStatus.UNKNOWN,
        quality_checks=[{"check": "acquisition", "status": "FAIL", "detail": reason[:500]}],
        infrastructure_source_id=source.id,
        created_by=actor.profile.id if actor else None,
    )
    session.add(snapshot)
    session.flush()
    _snapshot_event(
        session,
        snapshot,
        "ACQUISITION_FAILED",
        None,
        EvidenceSnapshotStatus.FAILED,
        actor,
        reason[:2000],
    )
    session.commit()
    return snapshot


def acquire_infrastructure_source(
    session: Session,
    source_key: str,
    actor: AuthenticatedUser | None,
    *,
    fetcher: Callable[[str], bytes] | None = None,
) -> tuple[EvidenceSnapshot, bool]:
    """Acquire and integrate one allowlisted source, preserving prior valid data."""

    definition = SOURCES.get(source_key)
    if definition is None:
        raise GovernanceError(
            "Unknown acquisition source",
            status_code=404,
            code="source_not_found",
        )
    retrieved_at = _utc_now()
    if definition.normalization_kind == "osm_context":
        from app.evidence.dhaka_osm import acquire_dhaka_osm_context

        return acquire_dhaka_osm_context(
            session, definition, actor, fetcher=fetcher, retrieved_at=retrieved_at
        )
    try:
        raw = (fetcher or fetch_source_bytes)(definition.url)
    except AcquisitionError as error:
        record_failure(session, definition, actor, retrieved_at, error.message)
        raise
    if len(raw) > MAX_RESPONSE_BYTES:
        record_failure(session, definition, actor, retrieved_at, "response_too_large")
        raise AcquisitionError("Source response exceeded the size limit", code="response_too_large")
    raw_hash = _hash_bytes(raw)
    try:
        rows = json.loads(raw)
        result = normalize_bridge_rows(rows)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        record_failure(session, definition, actor, retrieved_at, "invalid_json")
        raise AcquisitionError("Source body is not valid JSON", code="invalid_json") from error

    normalized_hash = _canonical_hash(result["records"])
    existing = session.scalar(
        select(EvidenceSnapshot).where(
            EvidenceSnapshot.source_key == source_key,
            EvidenceSnapshot.snapshot_sha256 == normalized_hash,
        )
    )
    if existing is not None:
        return existing, False

    source = _get_or_create_source(session, definition, actor, retrieved_at)
    validated = result["quality_status"] != EvidenceQualityStatus.FAIL
    snapshot = EvidenceSnapshot(
        snapshot_key=f"{source_key}-{normalized_hash[:12]}",
        kind=definition.kind,
        status=(
            EvidenceSnapshotStatus.VALIDATED
            if validated
            else EvidenceSnapshotStatus.QUARANTINED
        ),
        source_key=source_key,
        source_url=definition.url,
        provider=definition.provider,
        license_note=definition.license_note,
        dataset_version=f"{definition.dataset_version_prefix}@{retrieved_at.date().isoformat()}",
        retrieved_at=retrieved_at,
        geographic_context_key=definition.geographic_context_key,
        snapshot_sha256=normalized_hash,
        raw_sha256=raw_hash,
        schema_version=definition.schema_version,
        schema_fingerprint=result["schema_fingerprint"],
        record_count=result["record_count"],
        raw_record_count=result["raw_record_count"],
        duplicate_count=result["duplicate_count"],
        invalid_count=result["invalid_count"],
        missing_fields=result["missing_fields"],
        byte_size=len(result["normalized_bytes"]),
        media_type="application/json",
        crs=result["crs"],
        bbox=result["bbox"],
        data_period_start=result["data_period_start"],
        data_period_end=result["data_period_end"],
        geographic_coverage=definition.geographic_coverage,
        quality_status=result["quality_status"],
        quality_checks=result["quality_checks"],
        lineage={
            "source_key": source_key,
            "source_url": definition.url,
            "raw_sha256": raw_hash,
            "normalization": "latest inspection per BIN, sorted external_id",
            "schema_version": definition.schema_version,
            "retrieved_at": retrieved_at.isoformat(),
            "raw_record_count": result["raw_record_count"],
            "duplicate_history_rows": result["duplicate_count"],
            "coordinate_fallback_count": sum(
                1 for row in result["records"] if row["coordinate_source"] == "PRIOR_INSPECTION"
            ),
            "acquisition": "allowlisted bounded HTTPS; redirects disabled",
        },
        verification_status=SnapshotVerificationStatus.PENDING,
        is_current=validated,
        infrastructure_source_id=source.id,
        raw_content=raw,
        normalized_content=result["normalized_bytes"],
        created_by=actor.profile.id if actor else None,
    )
    session.add(snapshot)
    session.flush()
    _snapshot_event(
        session,
        snapshot,
        "ACQUIRED",
        None,
        snapshot.status,
        actor,
        (
            f"Allowlisted acquisition: {len(raw)} raw bytes, "
            f"{result['record_count']} normalized assets, "
            f"{result['invalid_count']} omitted."
        ),
    )

    if not validated:
        source.retrieved_at = retrieved_at
        session.commit()
        return snapshot, True

    previous_current = session.scalars(
        select(EvidenceSnapshot).where(
            EvidenceSnapshot.source_key == source_key,
            EvidenceSnapshot.is_current.is_(True),
            EvidenceSnapshot.id != snapshot.id,
        )
    ).all()
    for previous in previous_current:
        previous.is_current = False

    incoming_ids = {record["external_id"] for record in result["records"]}
    for asset in session.scalars(
        select(InfrastructureAsset).where(
            InfrastructureAsset.source_id == source.id,
            InfrastructureAsset.is_active.is_(True),
        )
    ).all():
        if asset.external_id not in incoming_ids:
            asset.is_active = False

    for record in result["records"]:
        asset = session.scalar(
            select(InfrastructureAsset).where(
                InfrastructureAsset.source_id == source.id,
                InfrastructureAsset.external_id == record["external_id"],
            )
        )
        metadata = {
            "source": source_key,
            "source_dataset": "4yue-vjfc",
            "borough": record["borough"],
            "bridge_type": record["bridge_type"],
            "owner_code": record["owner_code"],
            "spans": record["spans"],
            "rating_source": record["rating_source"],
            "current_rating": record["current_rating"],
            "verbal_rating": record["verbal_rating"],
            "general_recommendation": record["general_recommendation"],
            "deck_area_sq_ft": record["deck_area_sq_ft"],
            "replacement_cost": record["replacement_cost"],
            "inspection_date": record["inspection_date"],
            "coordinate_source": record["coordinate_source"],
            "source_row_count": record["source_row_count"],
            "snapshot_key": snapshot.snapshot_key,
        }
        location = f"POINT({record['longitude']} {record['latitude']})"
        if asset is None:
            asset = InfrastructureAsset(
                name=record["name"],
                asset_type=AssetType.BRIDGE,
                location=location,
                description=(
                    f"NYC DOT bridge BIN {record['external_id']}; latest inspection "
                    f"{record['inspection_date']}; rating {record['current_rating']}."
                ),
                criticality_score=0,
                is_active=True,
                metadata_json=metadata,
                source_id=source.id,
                snapshot_id=snapshot.id,
                external_id=record["external_id"],
            )
            session.add(asset)
        else:
            asset.name = record["name"]
            asset.location = location
            asset.description = (
                f"NYC DOT bridge BIN {record['external_id']}; latest inspection "
                f"{record['inspection_date']}; rating {record['current_rating']}."
            )
            asset.metadata_json = metadata
            asset.snapshot_id = snapshot.id
            asset.is_active = True

    source.retrieved_at = retrieved_at
    source.snapshot_sha256 = normalized_hash
    source.dataset_version = f"{definition.dataset_version_prefix}@{retrieved_at.date().isoformat()}"
    source.details = {
        **source.details,
        "latest_snapshot_id": str(snapshot.id),
        "latest_snapshot_key": snapshot.snapshot_key,
        "asset_count": result["record_count"],
        "quality_status": result["quality_status"].value,
        "acquisition": "allowlisted, bounded, redirects disabled",
    }
    session.add(
        InfrastructureSourceEvent(
            source_id=source.id,
            action="ACQUIRED",
            from_status=source.validation_status,
            to_status=source.validation_status,
            actor_id=actor.profile.id if actor else None,
            actor_email=actor.email if actor else None,
            note=(
                f"Acquired {result['record_count']} bridge assets from 4yue-vjfc. "
                "This records data availability, not a validation decision."
            ),
        )
    )
    session.commit()
    return snapshot, True
