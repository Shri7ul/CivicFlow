"""Independent recomputation and serialization for evidence snapshots."""

from __future__ import annotations

import hashlib
import json
import math
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser
from app.governance.errors import GovernanceError
from app.models.enums import (
    EvidenceSnapshotStatus,
    InfrastructureValidationStatus,
    SnapshotVerificationStatus,
)
from app.models.evidence import EvidenceSnapshot, EvidenceSnapshotEvent
from app.models.infrastructure import InfrastructureAsset
from app.models.pilot import InfrastructureSource, InfrastructureSourceEvent



def _hash(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical(value: object) -> str:
    return _hash(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    )


def get_snapshot(session: Session, snapshot_id: uuid.UUID) -> EvidenceSnapshot:
    snapshot = session.get(EvidenceSnapshot, snapshot_id)
    if snapshot is None:
        raise GovernanceError(
            "Evidence snapshot not found",
            status_code=404,
            code="evidence_snapshot_not_found",
        )
    return snapshot


def validate_infrastructure_source_metadata(
    session: Session,
    snapshot: EvidenceSnapshot,
    actor: AuthenticatedUser,
) -> InfrastructureSource | None:
    """Verify registry metadata after independent snapshot recomputation.

    This is metadata validation only. It does not assert that a bridge is in the
    reported physical condition and it is never a substitute for field review.
    """

    if snapshot.infrastructure_source_id is None:
        return None
    source = session.get(InfrastructureSource, snapshot.infrastructure_source_id)
    if source is None or source.validation_status == InfrastructureValidationStatus.REJECTED:
        return None
    required = (
        "provider",
        "source_url",
        "license_note",
        "retrieved_at",
        "dataset_version",
        "geographic_coverage",
        "crs",
        "schema_version",
        "snapshot_sha256",
        "update_frequency",
        "known_limitations",
    )
    missing = [field for field in required if not getattr(source, field)]
    hash_matches = source.snapshot_sha256 == snapshot.snapshot_sha256
    if missing or not hash_matches:
        source.details = {
            **source.details,
            "metadata_validation": {
                "status": "INCOMPLETE",
                "missing": missing,
                "snapshot_hash_matches": hash_matches,
            },
        }
        session.commit()
        return source
    if source.validation_status == InfrastructureValidationStatus.VERIFIED:
        return source
    previous = source.validation_status
    source.validation_status = InfrastructureValidationStatus.VERIFIED
    source.details = {
        **source.details,
        "metadata_validation": {
            "status": "COMPLETE",
            "method": "automated required-field and snapshot-hash check",
            "validated_at": datetime.now(timezone.utc).isoformat(),
            "limitation": "Metadata only; physical condition is not field-verified.",
        },
    }
    session.add(
        InfrastructureSourceEvent(
            source_id=source.id,
            action="AUTOMATED_METADATA_VALIDATION",
            from_status=previous,
            to_status=InfrastructureValidationStatus.VERIFIED,
            actor_id=actor.profile.id,
            actor_email=actor.email,
            note=(
                "Required registry fields and snapshot hash matched after "
                "independent recomputation. This does not verify physical asset "
                "condition, geometry in the field, or coverage completeness."
            ),
            created_at=datetime.now(timezone.utc),
        )
    )
    session.commit()
    return source


def verify_snapshot(
    session: Session, snapshot: EvidenceSnapshot, actor: AuthenticatedUser
) -> tuple[EvidenceSnapshot, bool]:
    """Recompute hashes/counts from stored bytes without trusting acquisition."""

    if snapshot.status != EvidenceSnapshotStatus.VALIDATED:
        raise GovernanceError(
            "Only validated snapshots can be independently recomputed",
            status_code=409,
            code="snapshot_not_validated",
        )
    if snapshot.verification_status == SnapshotVerificationStatus.AUTOMATED_RECOMPUTATION:
        if snapshot.infrastructure_source_id is not None:
            validate_infrastructure_source_metadata(session, snapshot, actor)
        return snapshot, False

    checks: list[dict[str, str]] = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append(
            {"check": name, "status": "PASS" if passed else "FAIL", "detail": detail}
        )

    raw_ok = (
        snapshot.raw_content is not None
        and snapshot.raw_sha256 is not None
        and _hash(snapshot.raw_content) == snapshot.raw_sha256
    )
    check(
        "raw_sha256_recomputed",
        raw_ok,
        "Stored raw bytes reproduce raw_sha256." if raw_ok else "Raw bytes/hash mismatch.",
    )

    parsed: Any = None
    normalized_ok = False
    try:
        if snapshot.normalized_content is not None:
            parsed = json.loads(snapshot.normalized_content)
        normalized_ok = (
            isinstance(parsed, list)
            and snapshot.snapshot_sha256 is not None
            and _canonical(parsed) == snapshot.snapshot_sha256
        )
    except (json.JSONDecodeError, UnicodeDecodeError):
        parsed = None
    check(
        "normalized_sha256_recomputed",
        normalized_ok,
        "Stored normalized records reproduce snapshot_sha256."
        if normalized_ok
        else "Normalized bytes/hash mismatch.",
    )

    record_count_ok = isinstance(parsed, list) and len(parsed) == snapshot.record_count
    check(
        "record_count_recomputed",
        record_count_ok,
        f"Stored rows: {len(parsed) if isinstance(parsed, list) else 'unparseable'}; "
        f"declared: {snapshot.record_count}.",
    )

    bbox_ok = True
    if isinstance(parsed, list) and parsed:
        points = []
        for row in parsed:
            if not isinstance(row, dict):
                bbox_ok = False
                break
            lat, lon = row.get("latitude"), row.get("longitude")
            if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                if math.isfinite(lat) and math.isfinite(lon):
                    points.append((lon, lat))
        if points:
            bbox = [
                min(p[0] for p in points),
                min(p[1] for p in points),
                max(p[0] for p in points),
                max(p[1] for p in points),
            ]
            if snapshot.validation_dataset_id is not None and len(snapshot.bbox or []) == 4:
                # Research datasets retain the registered study bbox; verify that
                # every point, not only the extent, lies inside it.
                west, south, east, north = (float(v) for v in snapshot.bbox)
                bbox_ok = all(
                    south - 1e-9 <= point[1] <= north + 1e-9
                    and west - 1e-9 <= point[0] <= east + 1e-9
                    for point in points
                )
            else:
                bbox_ok = all(
                    abs(float(a) - float(b)) < 1e-9
                    for a, b in zip(bbox, snapshot.bbox or [])
                ) and len(snapshot.bbox or []) == 4
    check(
        "spatial_bbox_recomputed",
        bbox_ok,
        "Recomputed WGS84 bounding box matches the snapshot."
        if bbox_ok
        else "Spatial bounding box mismatch.",
    )

    if snapshot.infrastructure_source_id is not None:
        asset_count = int(
            session.scalar(
                select(func.count())
                .select_from(InfrastructureAsset)
                .where(InfrastructureAsset.snapshot_id == snapshot.id)
            )
            or 0
        )
        asset_ids = set(
            session.scalars(
                select(InfrastructureAsset.external_id).where(
                    InfrastructureAsset.snapshot_id == snapshot.id
                )
            ).all()
        )
        expected_ids = {
            str(row.get("external_id"))
            for row in parsed
            if isinstance(parsed, list) and isinstance(row, dict)
        }
        asset_ok = asset_count == snapshot.record_count and asset_ids == expected_ids
        check(
            "infrastructure_assets_recomputed",
            asset_ok,
            f"{asset_count} linked assets; expected {snapshot.record_count} IDs.",
        )
    else:
        asset_ok = True
        check(
            "research_dataset_link",
            snapshot.validation_dataset_id is not None,
            "Snapshot is linked to a validation dataset."
            if snapshot.validation_dataset_id is not None
            else "No validation dataset link.",
        )

    passed = raw_ok and normalized_ok and record_count_ok and bbox_ok and asset_ok
    snapshot.verification_checks = checks
    snapshot.verified_at = datetime.now(timezone.utc)
    snapshot.verification_note = (
        "Automated independent recomputation from retained bytes; not a human review."
    )
    snapshot.verification_status = (
        SnapshotVerificationStatus.AUTOMATED_RECOMPUTATION
        if passed
        else SnapshotVerificationStatus.FAILED
    )
    session.add(
        EvidenceSnapshotEvent(
            snapshot_id=snapshot.id,
            action="AUTOMATED_RECOMPUTATION",
            from_status=snapshot.status,
            to_status=snapshot.status,
            actor_id=actor.profile.id,
            actor_email=actor.email,
            note=(
                "Hashes, counts and spatial extent recomputed from stored bytes. "
                "This verifies data integrity, not ground truth or human review."
            ),
            created_at=datetime.now(timezone.utc),
        )
    )
    session.commit()
    if not passed:
        raise GovernanceError(
            "Snapshot recomputation failed; evidence is not verified",
            status_code=409,
            code="snapshot_verification_failed",
        )
    if snapshot.infrastructure_source_id is not None:
        validate_infrastructure_source_metadata(session, snapshot, actor)
    return snapshot, True


def freshness_days(snapshot: EvidenceSnapshot) -> int | None:
    anchor = snapshot.data_period_end or snapshot.retrieved_at
    if anchor is None:
        return None
    aware = anchor if anchor.tzinfo else anchor.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - aware).days


def _is_osm_research_context(snapshot: EvidenceSnapshot) -> bool:
    """Public OSM context is real acquired data, never operational evidence."""

    return (
        snapshot.geographic_context_key == "BD-DHAKA"
        and snapshot.source_key.startswith("dhaka-osm")
    )


def serialize_snapshot(snapshot: EvidenceSnapshot, *, detail: bool = False) -> dict:
    payload = {
        "id": str(snapshot.id),
        "snapshot_key": snapshot.snapshot_key,
        "kind": snapshot.kind.value,
        "status": snapshot.status.value,
        "source_key": snapshot.source_key,
        "source_url": snapshot.source_url,
        "provider": snapshot.provider,
        "license_note": snapshot.license_note,
        "dataset_version": snapshot.dataset_version,
        "retrieved_at": snapshot.retrieved_at.isoformat(),
        "snapshot_sha256": snapshot.snapshot_sha256,
        "raw_sha256": snapshot.raw_sha256,
        "schema_version": snapshot.schema_version,
        "schema_fingerprint": snapshot.schema_fingerprint,
        "record_count": snapshot.record_count,
        "raw_record_count": snapshot.raw_record_count,
        "duplicate_count": snapshot.duplicate_count,
        "invalid_count": snapshot.invalid_count,
        "missing_fields": snapshot.missing_fields,
        "byte_size": snapshot.byte_size,
        "crs": snapshot.crs,
        "bbox": snapshot.bbox or [],
        "data_period_start": (
            snapshot.data_period_start.isoformat() if snapshot.data_period_start else None
        ),
        "data_period_end": (
            snapshot.data_period_end.isoformat() if snapshot.data_period_end else None
        ),
        "geographic_coverage": snapshot.geographic_coverage,
        "geographic_context_key": snapshot.geographic_context_key or "UNKNOWN",
        "quality_status": snapshot.quality_status.value,
        "quality_checks": snapshot.quality_checks or [],
        "lineage": snapshot.lineage or {},
        "failure_reason": snapshot.failure_reason,
        "verification_status": snapshot.verification_status.value,
        "verification_checks": snapshot.verification_checks or [],
        "verification_note": snapshot.verification_note,
        "verified_at": snapshot.verified_at.isoformat() if snapshot.verified_at else None,
        "is_current": snapshot.is_current,
        "freshness_days": freshness_days(snapshot),
        "raw_available": snapshot.raw_content is not None,
        "normalized_available": snapshot.normalized_content is not None,
        "validation_dataset_id": (
            str(snapshot.validation_dataset_id)
            if snapshot.validation_dataset_id
            else None
        ),
        "infrastructure_source_id": (
            str(snapshot.infrastructure_source_id)
            if snapshot.infrastructure_source_id
            else None
        ),
        "created_by": str(snapshot.created_by) if snapshot.created_by else None,
        "created_at": snapshot.created_at.isoformat(),
        "provenance": (
            "PUBLIC_OSM_RESEARCH"
            if _is_osm_research_context(snapshot)
            else "REAL"
            if snapshot.provenance_kind.value == "OPERATIONAL"
            else snapshot.provenance_kind.value
        ),
        "provenance_kind": snapshot.provenance_kind.value,
        "readiness": (
            "RESEARCH_CONTEXT_ONLY"
            if _is_osm_research_context(snapshot)
            else "REAL_ACQUIRED"
            if snapshot.status == EvidenceSnapshotStatus.VALIDATED
            and snapshot.quality_status.value != "FAIL"
            and snapshot.provenance_kind.value == "OPERATIONAL"
            else "NOT_OPERATIONAL_EVIDENCE"
        ),
        "disclaimer": (
            "OpenStreetMap research context is community-mapped, not authoritative "
            "infrastructure, not field-verified and never operational evidence. "
            if _is_osm_research_context(snapshot)
            else ""
        )
        + (
            "Snapshot integrity is not operational validation. Acquired bytes are "
            "provided by the named source; CivicFlow did not independently inspect "
            "the physical asset."
        ),
    }
    if detail:
        payload["lineage_detail"] = {
            "normalization": snapshot.lineage.get("normalization"),
            "coordinate_fallback_count": snapshot.lineage.get(
                "coordinate_fallback_count"
            ),
            "acquisition": snapshot.lineage.get("acquisition"),
            "raw_record_count": snapshot.raw_record_count,
            "duplicate_history_rows": snapshot.duplicate_count,
        }
    return payload
