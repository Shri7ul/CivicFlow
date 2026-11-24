"""Real, bounded Dhaka infrastructure-context acquisition from OpenStreetMap.

This module reuses the Phase 11 acquisition contract (allowlisted URL, no
redirects, bounded bytes/records, hashes, lineage, failure-safe snapshots).
It deliberately produces **research context**:

* OSM ways are community-mapped features, not verified field assets.
* No observation timestamp is invented for an OSM feature.
* No incident, complaint, ground-truth label, dispatch target or safety claim
  is created.
* The snapshot is tagged ``BD-DHAKA`` and confined to a small registered cell.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser
from app.evidence.acquisition import (
    MAX_RECORDS,
    AcquisitionError,
    SourceDefinition,
    _canonical_hash,
    _get_or_create_source,
    _hash_bytes,
    _snapshot_event,
    fetch_source_bytes,
    record_failure,
)
from app.geo.contexts import BD_DHAKA, DHAKA_OSM_RESEARCH_CELL
from app.models.enums import (
    AssetType,
    EvidenceQualityStatus,
    EvidenceSnapshotKind,
    EvidenceSnapshotStatus,
    ProvenanceKind,
    SnapshotVerificationStatus,
)
from app.models.evidence import EvidenceSnapshot
from app.models.infrastructure import InfrastructureAsset
from app.models.pilot import InfrastructureSourceEvent

MIN_CONTEXT_FEATURES = 20


def _safe_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _asset_type(tags: dict[str, Any]) -> AssetType:
    if str(tags.get("bridge") or "").lower() in {"yes", "true"}:
        return AssetType.BRIDGE
    waterway = str(tags.get("waterway") or "").lower()
    if waterway in {"drain", "stream", "river", "canal", "ditch"}:
        return AssetType.DRAIN
    if tags.get("highway"):
        return AssetType.ROAD
    return AssetType.OTHER


def normalize_osm_context_rows(
    payload: object, *, cell: Any = DHAKA_OSM_RESEARCH_CELL
) -> dict[str, Any]:
    """Deterministically normalize an Overpass ``out geom`` JSON payload."""

    if not isinstance(payload, dict) or not isinstance(payload.get("elements"), list):
        raise AcquisitionError("Overpass payload must contain an elements array", code="invalid_schema")
    elements = payload["elements"]
    if len(elements) > MAX_RECORDS:
        raise AcquisitionError("Overpass payload exceeds record limit", code="too_many_records")

    records: dict[str, dict[str, Any]] = {}
    rejected = 0
    geometry_points_outside_cell = 0
    for element in elements:
        if not isinstance(element, dict) or element.get("type") != "way":
            rejected += 1
            continue
        geometry = element.get("geometry")
        if not isinstance(geometry, list) or not geometry:
            rejected += 1
            continue
        latitudes = [_safe_float(point.get("lat")) if isinstance(point, dict) else None for point in geometry]
        longitudes = [_safe_float(point.get("lon")) if isinstance(point, dict) else None for point in geometry]
        if any(value is None for value in latitudes + longitudes):
            rejected += 1
            continue
        latitude = sum(latitudes) / len(latitudes)
        longitude = sum(longitudes) / len(longitudes)
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            rejected += 1
            continue
        if not cell.contains(latitude, longitude):
            rejected += 1
            continue
        geometry_points_outside_cell += sum(
            1
            for point_lat, point_lon in zip(latitudes, longitudes)
            if not cell.contains(point_lat, point_lon)
        )
        tags = element.get("tags") if isinstance(element.get("tags"), dict) else {}
        asset_type = _asset_type(tags)
        external_id = f"osm-way-{element.get('id')}"
        name = str(tags.get("name") or "").strip()
        if not name:
            name = f"OSM way {element.get('id')} ({asset_type.value})"
        record = {
            "external_id": external_id,
            "osm_id": element.get("id"),
            "asset_type": asset_type.value,
            "name": name[:200],
            "latitude": round(latitude, 7),
            "longitude": round(longitude, 7),
            "highway": str(tags.get("highway") or "") or None,
            "waterway": str(tags.get("waterway") or "") or None,
            "bridge": str(tags.get("bridge") or "") or None,
            "surface": str(tags.get("surface") or "") or None,
            "geometry_points": len(geometry),
        }
        previous = records.get(external_id)
        # A bridge classification is more specific than a generic highway way.
        if previous is None or (
            previous["asset_type"] == AssetType.ROAD.value
            and record["asset_type"] != AssetType.ROAD.value
        ):
            records[external_id] = record

    normalized = sorted(records.values(), key=lambda item: item["external_id"])
    lats = [item["latitude"] for item in normalized]
    lons = [item["longitude"] for item in normalized]
    bbox = [min(lons), min(lats), max(lons), max(lats)] if normalized else []
    checks = [
        {
            "check": "records_present",
            "status": "PASS" if normalized else "FAIL",
            "detail": f"{len(elements)} raw OSM elements received.",
        },
        {
            "check": "bounded_records",
            "status": "PASS" if len(elements) <= MAX_RECORDS else "FAIL",
            "detail": f"Raw elements must not exceed {MAX_RECORDS}.",
        },
        {
            "check": "unique_external_ids",
            "status": "PASS" if len(records) == len({item["external_id"] for item in normalized}) else "FAIL",
            "detail": "OSM way ids deduplicated deterministically.",
        },
        {
            "check": "spatial_containment",
            "status": "PASS" if normalized and rejected == 0 else ("WARN" if normalized else "FAIL"),
            "detail": (
                f"{rejected} element(s) rejected for missing/invalid geometry or "
                "for falling outside the registered Dhaka research cell."
            ),
        },
        {
            "check": "geometry_within_research_cell",
            "status": "WARN" if geometry_points_outside_cell else "PASS",
            "detail": (
                f"{geometry_points_outside_cell} geometry vertex/vertices lie "
                "outside the registered research cell; ways are clipped by "
                "Overpass to the query bbox and centroids remain inside."
            ),
        },
        {
            "check": "minimum_context_features",
            "status": "PASS" if len(normalized) >= MIN_CONTEXT_FEATURES else "FAIL",
            "detail": f"{len(normalized)} normalized features; minimum {MIN_CONTEXT_FEATURES}.",
        },
        {
            "check": "coordinate_crs",
            "status": "PASS" if bbox else "FAIL",
            "detail": "Overpass geometry treated as WGS84 (EPSG:4326).",
        },
        {
            "check": "no_observation_timestamp_invented",
            "status": "PASS",
            "detail": "OSM features have no per-feature observation date; only retrieval time is recorded.",
        },
    ]
    if any(item["status"] == "FAIL" for item in checks):
        quality = EvidenceQualityStatus.FAIL
    elif any(item["status"] == "WARN" for item in checks):
        quality = EvidenceQualityStatus.WARN
    else:
        quality = EvidenceQualityStatus.PASS
    return {
        "records": normalized,
        "normalized_bytes": json.dumps(
            normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8"),
        "bbox": bbox,
        "record_count": len(normalized),
        "raw_record_count": len(elements),
        "rejected": rejected,
        "quality_status": quality,
        "quality_checks": checks,
    }


def acquire_dhaka_osm_context(
    session: Session,
    definition: SourceDefinition,
    actor: AuthenticatedUser | None,
    *,
    fetcher: Callable[[str], bytes] | None = None,
    retrieved_at: datetime | None = None,
) -> tuple[EvidenceSnapshot, bool]:
    """Acquire one pinned OSM research cell snapshot, preserving valid prior data."""

    retrieved_at = retrieved_at or datetime.now(timezone.utc)
    try:
        raw = (fetcher or fetch_source_bytes)(definition.url)
    except AcquisitionError as error:
        record_failure(session, definition, actor, retrieved_at, error.message)
        raise
    raw_hash = _hash_bytes(raw)
    try:
        result = normalize_osm_context_rows(json.loads(raw))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        record_failure(session, definition, actor, retrieved_at, "invalid_json")
        raise AcquisitionError("Overpass body is not valid JSON", code="invalid_json") from error
    except AcquisitionError as error:
        record_failure(session, definition, actor, retrieved_at, error.message)
        raise

    normalized_hash = _canonical_hash(result["records"])
    existing = session.scalar(
        select(EvidenceSnapshot).where(
            EvidenceSnapshot.source_key == definition.source_key,
            EvidenceSnapshot.snapshot_sha256 == normalized_hash,
        )
    )
    if existing is not None:
        return existing, False

    source = _get_or_create_source(session, definition, actor, retrieved_at)
    validated = result["quality_status"] != EvidenceQualityStatus.FAIL
    snapshot = EvidenceSnapshot(
        snapshot_key=f"{definition.source_key}-{normalized_hash[:12]}",
        kind=EvidenceSnapshotKind.INFRASTRUCTURE,
        status=(
            EvidenceSnapshotStatus.VALIDATED
            if validated
            else EvidenceSnapshotStatus.QUARANTINED
        ),
        source_key=definition.source_key,
        source_url=definition.url,
        provider=definition.provider,
        license_note=definition.license_note,
        dataset_version=f"{definition.dataset_version_prefix}@{retrieved_at.date().isoformat()}",
        retrieved_at=retrieved_at,
        snapshot_sha256=normalized_hash,
        raw_sha256=raw_hash,
        schema_version=definition.schema_version,
        schema_fingerprint=definition.schema_version,
        record_count=result["record_count"],
        raw_record_count=result["raw_record_count"],
        invalid_count=result["rejected"],
        byte_size=len(result["normalized_bytes"]),
        media_type="application/json",
        crs="EPSG:4326",
        bbox=result["bbox"],
        geographic_coverage=definition.geographic_coverage,
        geographic_context_key=BD_DHAKA.key,
        provenance_kind=ProvenanceKind.OPERATIONAL,
        quality_status=result["quality_status"],
        quality_checks=result["quality_checks"],
        lineage={
            "source_key": definition.source_key,
            "source_url": definition.url,
            "raw_sha256": raw_hash,
            "normalization": "osm-overpass-dhaka-context-v1, deduplicated by OSM way id",
            "geographic_context_key": BD_DHAKA.key,
            "geographic_cell_geojson": DHAKA_OSM_RESEARCH_CELL.as_geojson(),
            "retrieved_at": retrieved_at.isoformat(),
            "attribution": "© OpenStreetMap contributors, ODbL 1.0",
            "configuration_used_for_selection": False,
            "note": (
                "Public community-mapped infrastructure context for research "
                "only. Not authoritative, not human-verified, not operational "
                "ground truth, and not an incident or complaint record."
            ),
            "acquisition": "pinned allowlisted Overpass GET; redirects disabled",
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
            f"Dhaka OSM research context: {len(raw)} raw bytes, "
            f"{result['record_count']} features, {result['rejected']} rejected."
        ),
    )

    if not validated:
        source.retrieved_at = retrieved_at
        session.commit()
        return snapshot, True

    previous_current = session.scalars(
        select(EvidenceSnapshot).where(
            EvidenceSnapshot.source_key == definition.source_key,
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
            "source": definition.source_key,
            "geographic_context_key": BD_DHAKA.key,
            "osm_id": record["osm_id"],
            "asset_type": record["asset_type"],
            "highway": record["highway"],
            "waterway": record["waterway"],
            "bridge": record["bridge"],
            "surface": record["surface"],
            "geometry_points": record["geometry_points"],
            "snapshot_key": snapshot.snapshot_key,
            "data_class": "PUBLIC_OSM_RESEARCH_CONTEXT",
            "field_verified": False,
        }
        description = (
            f"OpenStreetMap feature {record['external_id']} in the central Dhaka "
            "research cell. Community-mapped context; not field-verified."
        )
        location = f"POINT({record['longitude']} {record['latitude']})"
        if asset is None:
            asset = InfrastructureAsset(
                name=record["name"],
                asset_type=AssetType(record["asset_type"]),
                location=location,
                description=description,
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
            asset.asset_type = AssetType(record["asset_type"])
            asset.location = location
            asset.description = description
            asset.metadata_json = metadata
            asset.snapshot_id = snapshot.id
            asset.is_active = True

    source.retrieved_at = retrieved_at
    source.snapshot_sha256 = normalized_hash
    source.dataset_version = (
        f"{definition.dataset_version_prefix}@{retrieved_at.date().isoformat()}"
    )
    source.details = {
        **source.details,
        "latest_snapshot_id": str(snapshot.id),
        "latest_snapshot_key": snapshot.snapshot_key,
        "asset_count": result["record_count"],
        "quality_status": result["quality_status"].value,
        "geographic_context_key": BD_DHAKA.key,
        "data_class": "PUBLIC_OSM_RESEARCH_CONTEXT",
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
                f"Acquired {result['record_count']} OSM research-context features "
                "in BD-DHAKA. This does not validate infrastructure or authorize "
                "any pilot action."
            ),
        )
    )
    session.commit()
    return snapshot, True
