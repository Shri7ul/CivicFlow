"""Pilot boundary registration and human verification workflow.

The screening bbox registered in ``app.geo.contexts`` is explicitly not an
official boundary. A boundary becomes usable for a pilot only after a distinct
human verifies and then approves a hashed, provenance-complete registration.
Nothing in this module auto-approves a boundary.
"""

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
from app.geo.contexts import (
    BoundingBox,
    resolve_context_from_bbox,
    require_context,
)
from app.governance.errors import GovernanceError
from app.models.enums import BoundarySourceType, PilotBoundaryStatus
from app.models.phase14 import PilotBoundary, PilotBoundaryEvent

AUTHORITATIVE_SOURCES = {
    BoundarySourceType.OFFICIAL_ADMINISTRATIVE,
    BoundarySourceType.AUTHORITATIVE_PUBLIC,
}

TRANSITIONS: dict[str, tuple[set[PilotBoundaryStatus], PilotBoundaryStatus]] = {
    "SUBMIT": ({PilotBoundaryStatus.UNVERIFIED}, PilotBoundaryStatus.PENDING_REVIEW),
    "VERIFY": ({PilotBoundaryStatus.PENDING_REVIEW}, PilotBoundaryStatus.VERIFIED),
    "APPROVE": ({PilotBoundaryStatus.VERIFIED}, PilotBoundaryStatus.APPROVED),
    "REJECT": (
        {PilotBoundaryStatus.PENDING_REVIEW, PilotBoundaryStatus.VERIFIED},
        PilotBoundaryStatus.UNVERIFIED,
    ),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fail(message: str, *, code: str, status_code: int = 400) -> None:
    raise GovernanceError(message, code=code, status_code=status_code)


def _canonical_document(payload: Any) -> str:
    source_type = payload.source_type
    document = {
        "source_type": source_type.value if hasattr(source_type, "value") else str(source_type),
        "source_owner": payload.source_owner.strip(),
        "source_name": payload.source_name.strip(),
        "source_url": (payload.source_url or "").strip(),
        "source_date": payload.source_date.isoformat() if payload.source_date else None,
        "boundary_version": payload.boundary_version.strip(),
        "crs": payload.crs.strip(),
        "geometry_geojson": payload.geometry_geojson,
        "bbox_geojson": payload.bbox_geojson,
    }
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def validate_geometry(geometry: Any, bbox: list[float], context_key: str) -> tuple[dict, dict]:
    """Validate coordinates and polygon structure without trusting the client."""

    coordinate_errors: list[str] = []
    geometry_errors: list[str] = []
    ring_points: list[tuple[float, float]] = []

    if not isinstance(geometry, dict) or geometry.get("type") != "Polygon":
        geometry_errors.append("geometry_geojson must be a GeoJSON Polygon")
    else:
        rings = geometry.get("coordinates")
        if not isinstance(rings, list) or not rings:
            geometry_errors.append("Polygon must contain at least one ring")
        else:
            for index, ring in enumerate(rings):
                if not isinstance(ring, list) or len(ring) < 4:
                    geometry_errors.append(f"ring {index} must contain at least 4 positions")
                    continue
                parsed: list[tuple[float, float]] = []
                for position in ring:
                    if (
                        not isinstance(position, (list, tuple))
                        or len(position) != 2
                        or not all(isinstance(value, (int, float)) for value in position)
                    ):
                        coordinate_errors.append(f"ring {index} has a non-numeric position")
                        continue
                    lon, lat = float(position[0]), float(position[1])
                    if not (math.isfinite(lon) and math.isfinite(lat)):
                        coordinate_errors.append(f"ring {index} has a non-finite coordinate")
                        continue
                    if not (-180 <= lon <= 180) or not (-90 <= lat <= 90):
                        coordinate_errors.append(f"ring {index} has an out-of-range coordinate")
                        continue
                    parsed.append((lon, lat))
                if len(parsed) >= 4 and parsed[0] != parsed[-1]:
                    geometry_errors.append(f"ring {index} is not closed")
                ring_points.extend(parsed)
                if len(parsed) >= 3:
                    area2 = sum(
                        parsed[i][0] * parsed[(i + 1) % len(parsed)][1]
                        - parsed[(i + 1) % len(parsed)][0] * parsed[i][1]
                        for i in range(len(parsed))
                    )
                    if abs(area2) < 1e-12:
                        geometry_errors.append(f"ring {index} has zero area")

    try:
        declared = BoundingBox.from_geojson(bbox)
        context = require_context(context_key)
        if not context.bbox.contains_bbox(declared):
            geometry_errors.append("declared bbox is outside the registered context envelope")
        if ring_points:
            west = min(point[0] for point in ring_points)
            east = max(point[0] for point in ring_points)
            south = min(point[1] for point in ring_points)
            north = max(point[1] for point in ring_points)
            observed = BoundingBox(west, south, east, north)
            tolerance = 1e-8
            if (
                abs(observed.west - declared.west) > tolerance
                or abs(observed.south - declared.south) > tolerance
                or abs(observed.east - declared.east) > tolerance
                or abs(observed.north - declared.north) > tolerance
            ):
                geometry_errors.append("declared bbox does not match the geometry extent")
            if not context.bbox.contains_bbox(observed):
                geometry_errors.append("geometry extent is outside the registered context envelope")
    except (ValueError, TypeError) as error:
        coordinate_errors.append(str(error))

    coordinate_validation = {
        "valid": not coordinate_errors,
        "crs": "EPSG:4326" if context_key else "UNKNOWN",
        "checked_positions": len(ring_points),
        "errors": coordinate_errors,
    }
    geometry_validation = {
        "valid": not geometry_errors,
        "ring_count": len(geometry.get("coordinates", [])) if isinstance(geometry, dict) else 0,
        "closed": not any("not closed" in item for item in geometry_errors),
        "errors": geometry_errors,
    }
    return coordinate_validation, geometry_validation


def register_boundary(
    session: Session, payload: Any, actor: AuthenticatedUser
) -> PilotBoundary:
    context_key = require_context(payload.geographic_context_key).key
    declared = BoundingBox.from_geojson(payload.bbox_geojson)
    resolved = resolve_context_from_bbox(declared)
    if resolved != context_key:
        _fail(
            f"bbox resolves to {resolved}, not {context_key}; context cannot be client-selected",
            code="context_mismatch",
            status_code=422,
        )
    existing = session.scalar(
        select(PilotBoundary.id).where(PilotBoundary.boundary_key == payload.boundary_key)
    )
    if existing is not None:
        _fail("A boundary with this key already exists", code="boundary_key_conflict", status_code=409)

    coordinate_validation, geometry_validation = validate_geometry(
        payload.geometry_geojson, payload.bbox_geojson, context_key
    )
    if not coordinate_validation["valid"] or not geometry_validation["valid"]:
        _fail(
            "Boundary geometry validation failed: "
            + "; ".join(coordinate_validation["errors"] + geometry_validation["errors"]),
            code="boundary_geometry_invalid",
            status_code=422,
        )

    boundary = PilotBoundary(
        boundary_key=payload.boundary_key,
        name=payload.name,
        description=payload.description,
        pilot_id=payload.pilot_id,
        geographic_context_key=context_key,
        source_type=payload.source_type,
        source_owner=payload.source_owner,
        source_name=payload.source_name,
        source_url=payload.source_url,
        source_date=payload.source_date,
        boundary_version=payload.boundary_version,
        crs=payload.crs,
        geometry_geojson=payload.geometry_geojson,
        bbox_geojson=payload.bbox_geojson,
        coordinate_validation=coordinate_validation,
        geometry_validation=geometry_validation,
        provenance_note=payload.provenance_note,
        license_note=payload.license_note,
        integrity_sha256=hashlib.sha256(
            _canonical_document(payload).encode("utf-8")
        ).hexdigest(),
        status=PilotBoundaryStatus.UNVERIFIED,
        created_by=actor.profile.id,
    )
    session.add(boundary)
    session.flush()
    session.add(
        PilotBoundaryEvent(
            boundary_id=boundary.id,
            action="REGISTERED",
            from_status=None,
            to_status=PilotBoundaryStatus.UNVERIFIED,
            actor_id=actor.profile.id,
            actor_email=actor.email,
            note="Boundary registered as UNVERIFIED. No approval or pilot use asserted.",
            created_at=_now(),
        )
    )
    session.commit()
    return boundary


def _event(
    session: Session,
    boundary: PilotBoundary,
    action: str,
    previous: PilotBoundaryStatus,
    actor: AuthenticatedUser,
    note: str,
) -> None:
    session.add(
        PilotBoundaryEvent(
            boundary_id=boundary.id,
            action=action,
            from_status=previous,
            to_status=boundary.status,
            actor_id=actor.profile.id,
            actor_email=actor.email,
            note=note,
            created_at=_now(),
        )
    )


def transition_boundary(
    session: Session,
    boundary: PilotBoundary,
    action: str,
    payload: Any,
    actor: AuthenticatedUser,
) -> PilotBoundary:
    if action not in TRANSITIONS:
        _fail(f"Unknown boundary action {action}", code="unknown_boundary_action", status_code=422)
    session.refresh(boundary, with_for_update=True)
    allowed, target = TRANSITIONS[action]
    if boundary.status not in allowed:
        _fail(
            f"Action {action} is not allowed from {boundary.status.value}",
            code="invalid_boundary_transition",
            status_code=409,
        )
    previous = boundary.status
    note = (payload.note or "").strip()

    if action == "SUBMIT":
        required = (
            boundary.source_owner,
            boundary.source_name,
            boundary.source_url,
            boundary.boundary_version,
            boundary.provenance_note,
            boundary.license_note,
        )
        if not all(required) or boundary.source_date is None:
            _fail(
                "Source owner, name, URL, date, version, provenance and license are required before review",
                code="boundary_provenance_incomplete",
                status_code=422,
            )
        boundary.submitted_by = actor.profile.id
    elif action == "VERIFY":
        if actor.profile.id == boundary.submitted_by:
            _fail("The submitter cannot verify their own boundary", code="separation_of_duties", status_code=403)
        if len(note) < 10:
            _fail("A verification note of at least 10 characters is required", code="note_required", status_code=422)
        if not boundary.coordinate_validation.get("valid") or not boundary.geometry_validation.get("valid"):
            _fail("Cannot verify a boundary with failed geometry validation", code="boundary_geometry_invalid", status_code=422)
        boundary.reviewed_by = actor.profile.id
        boundary.reviewed_at = _now()
        boundary.decision_note = note
    elif action == "APPROVE":
        if actor.profile.id in {boundary.submitted_by, boundary.reviewed_by}:
            _fail(
                "Approval must be performed by a distinct human approver",
                code="separation_of_duties",
                status_code=403,
            )
        if boundary.source_type not in AUTHORITATIVE_SOURCES:
            _fail(
                "Only official or authoritative public boundary sources can be approved",
                code="boundary_source_not_authoritative",
                status_code=422,
            )
        if not (payload.approval_reference or "").strip() or len(note) < 10:
            _fail(
                "An approval reference and a rationale of at least 10 characters are required",
                code="approval_reference_required",
                status_code=422,
            )
        boundary.reviewed_at = _now()
        boundary.decision_note = f"{note} | approval_reference={(payload.approval_reference or '').strip()}"
    elif action == "REJECT":
        reason = (payload.rejection_reason or "").strip()
        if len(reason) < 10:
            _fail("A rejection reason of at least 10 characters is required", code="reason_required", status_code=422)
        boundary.rejection_reason = reason
        boundary.reviewed_by = None
        boundary.reviewed_at = None
        boundary.decision_note = None

    boundary.status = target
    event_note = note
    if action == "APPROVE":
        event_note = f"{note} | approval_reference={(payload.approval_reference or '').strip()}"
    elif action == "REJECT":
        event_note = boundary.rejection_reason or ""
    _event(session, boundary, action.upper(), previous, actor, event_note)
    session.commit()
    return boundary


def events_for(session: Session, boundary_id: uuid.UUID) -> list[PilotBoundaryEvent]:
    return list(
        session.scalars(
            select(PilotBoundaryEvent)
            .where(PilotBoundaryEvent.boundary_id == boundary_id)
            .order_by(PilotBoundaryEvent.created_at, PilotBoundaryEvent.id)
        ).all()
    )


def approved_for(session: Session, context_key: str, pilot_id: uuid.UUID | None = None) -> list[PilotBoundary]:
    statement = select(PilotBoundary).where(
        PilotBoundary.geographic_context_key == context_key,
        PilotBoundary.status == PilotBoundaryStatus.APPROVED,
    )
    if pilot_id is not None:
        statement = statement.where(PilotBoundary.pilot_id == pilot_id)
    return list(session.scalars(statement).all())


def count(session: Session, *, status: PilotBoundaryStatus | None = None) -> int:
    statement = select(func.count()).select_from(PilotBoundary)
    if status is not None:
        statement = statement.where(PilotBoundary.status == status)
    return int(session.scalar(statement) or 0)
