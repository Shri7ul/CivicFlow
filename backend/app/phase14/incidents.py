"""Pilot-scoped incident handling and processing interlock.

A CRITICAL incident stops *pilot processing* inside the platform. It never
triggers real-world emergency response, dispatch or public alerts.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser
from app.geo.contexts import BoundingBox, require_context
from app.governance.errors import GovernanceError
from app.models.enums import (
    PilotIncidentSeverity,
    PilotIncidentStatus,
    PilotStatus,
    Role,
)
from app.models.phase14 import PilotIncident, PilotIncidentEvent
from app.models.pilot import Pilot

TRANSITIONS: dict[PilotIncidentStatus, set[PilotIncidentStatus]] = {
    PilotIncidentStatus.OPEN: {PilotIncidentStatus.INVESTIGATING},
    PilotIncidentStatus.INVESTIGATING: {PilotIncidentStatus.MITIGATED},
    PilotIncidentStatus.MITIGATED: {PilotIncidentStatus.RESOLVED},
    PilotIncidentStatus.RESOLVED: {PilotIncidentStatus.CLOSED},
    PilotIncidentStatus.CLOSED: set(),
}
BLOCKING_STATUSES = {
    PilotIncidentStatus.OPEN,
    PilotIncidentStatus.INVESTIGATING,
    PilotIncidentStatus.MITIGATED,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fail(message: str, *, code: str, status_code: int = 400) -> None:
    raise GovernanceError(message, code=code, status_code=status_code)


def get_incident(session: Session, incident_id: uuid.UUID) -> PilotIncident:
    incident = session.get(PilotIncident, incident_id)
    if incident is None:
        _fail("Pilot incident not found", code="pilot_incident_not_found", status_code=404)
    return incident


def _event(
    session: Session,
    incident: PilotIncident,
    action: str,
    previous: PilotIncidentStatus | None,
    actor: AuthenticatedUser,
    note: str | None,
) -> None:
    session.add(
        PilotIncidentEvent(
            incident_id=incident.id,
            action=action,
            from_status=previous,
            to_status=incident.status,
            actor_id=actor.profile.id,
            actor_email=actor.email,
            note=note,
            created_at=_now(),
        )
    )


def open_incident(session: Session, payload: Any, actor: AuthenticatedUser) -> PilotIncident:
    if actor.profile.role not in {Role.WORKER, Role.ADMIN}:
        _fail("Only staff can open a pilot incident", code="incident_forbidden", status_code=403)
    pilot = session.get(Pilot, payload.pilot_id)
    if pilot is None:
        _fail("Pilot not found", code="pilot_not_found", status_code=404)
    if pilot.status not in {PilotStatus.APPROVED, PilotStatus.ACTIVE, PilotStatus.PAUSED}:
        _fail("Incidents can only be opened for a governed pilot", code="pilot_not_governed", status_code=409)
    context = require_context(pilot.geographic_context_key)
    if payload.bbox and not context.bbox.contains_bbox(BoundingBox.from_geojson(payload.bbox)):
        _fail("Incident bbox is outside the pilot context", code="context_mismatch", status_code=422)

    critical = payload.severity == PilotIncidentSeverity.CRITICAL
    incident = PilotIncident(
        incident_key=f"pinc-{uuid.uuid4().hex}",
        pilot_id=pilot.id,
        geographic_context_key=pilot.geographic_context_key,
        title=payload.title,
        description=payload.description,
        severity=payload.severity,
        status=PilotIncidentStatus.OPEN,
        source=payload.source,
        related_observation_id=payload.related_observation_id,
        processing_stopped=critical,
        impact_summary=(
            "CRITICAL: pilot processing is stopped pending human review. "
            "No real-world response was triggered."
            if critical
            else None
        ),
        opened_at=payload.opened_at or _now(),
        created_by=actor.profile.id,
    )
    session.add(incident)
    session.flush()
    _event(
        session,
        incident,
        "OPENED",
        None,
        actor,
        (
            "CRITICAL incident opened; pilot processing interlock engaged."
            if critical
            else "Pilot incident opened."
        ),
    )
    session.commit()
    return incident


def transition_incident(
    session: Session, incident: PilotIncident, payload: Any, actor: AuthenticatedUser
) -> PilotIncident:
    if actor.profile.role != Role.ADMIN:
        _fail("Only an administrator can transition a pilot incident", code="incident_transition_forbidden", status_code=403)
    session.refresh(incident, with_for_update=True)
    try:
        target = PilotIncidentStatus((payload.status or "").upper())
    except ValueError:
        _fail("Unsupported incident status", code="invalid_incident_status", status_code=422)
    if target not in TRANSITIONS[incident.status]:
        _fail(
            f"Incident transition {incident.status.value} -> {target.value} is not allowed",
            code="invalid_incident_transition",
            status_code=409,
        )
    note = (payload.note or "").strip()
    if target in {
        PilotIncidentStatus.INVESTIGATING,
        PilotIncidentStatus.MITIGATED,
        PilotIncidentStatus.RESOLVED,
        PilotIncidentStatus.CLOSED,
    } and len(note) < 10:
        _fail("A note of at least 10 characters is required for this transition", code="note_required", status_code=422)
    previous = incident.status
    incident.status = target
    now = _now()
    if target == PilotIncidentStatus.INVESTIGATING:
        incident.investigating_at = now
    elif target == PilotIncidentStatus.MITIGATED:
        incident.mitigated_at = now
    elif target == PilotIncidentStatus.RESOLVED:
        incident.resolved_at = now
        incident.resolution_note = note
    elif target == PilotIncidentStatus.CLOSED:
        incident.closed_at = now
    _event(session, incident, "STATUS_CHANGED", previous, actor, note)
    session.commit()
    return incident


def resume_processing(
    session: Session, incident: PilotIncident, note: str, actor: AuthenticatedUser
) -> PilotIncident:
    """Explicitly lift the processing interlock after a resolved incident."""

    if actor.profile.role != Role.ADMIN:
        _fail("Only an administrator can resume pilot processing", code="resume_forbidden", status_code=403)
    session.refresh(incident, with_for_update=True)
    if incident.status not in {PilotIncidentStatus.RESOLVED, PilotIncidentStatus.CLOSED}:
        _fail("Processing can only resume after resolution or closure", code="incident_not_resolved", status_code=409)
    if len((note or "").strip()) < 10:
        _fail("A justification of at least 10 characters is required", code="note_required", status_code=422)
    if not incident.processing_stopped:
        _fail("This incident has no active processing interlock", code="no_processing_stop", status_code=409)
    incident.processing_stopped = False
    incident.impact_summary = (
        f"{incident.impact_summary or ''} | interlock lifted by {actor.email}: {note.strip()}"
    )
    _event(session, incident, "PROCESSING_RESUMED", incident.status, actor, note)
    session.commit()
    return incident


def processing_allowed(session: Session, pilot_id: uuid.UUID) -> dict:
    pilot = session.get(Pilot, pilot_id)
    if pilot is None:
        return {"allowed": False, "reasons": ["pilot_not_found"]}
    reasons: list[str] = []
    if pilot.status != PilotStatus.ACTIVE:
        reasons.append(f"pilot_status_{pilot.status.value.lower()}")
    blocking = session.scalar(
        select(func.count())
        .select_from(PilotIncident)
        .where(
            PilotIncident.pilot_id == pilot_id,
            PilotIncident.severity == PilotIncidentSeverity.CRITICAL,
            PilotIncident.processing_stopped.is_(True),
            PilotIncident.status.in_(BLOCKING_STATUSES),
        )
    )
    if (blocking or 0) > 0:
        reasons.append("critical_incident_processing_stop")
    return {"allowed": not reasons, "reasons": reasons}


def events_for(session: Session, incident_id: uuid.UUID) -> list[PilotIncidentEvent]:
    return list(
        session.scalars(
            select(PilotIncidentEvent)
            .where(PilotIncidentEvent.incident_id == incident_id)
            .order_by(PilotIncidentEvent.created_at, PilotIncidentEvent.id)
        ).all()
    )
