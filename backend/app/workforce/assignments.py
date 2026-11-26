"""Incident triage, assignment and completion-verification workflow.

All incident state changes go through the existing ``transition_incident``
service, so the single incident state machine and its immutable status history
remain authoritative. Nothing here auto-dispatches or executes real-world work.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import AuthenticatedUser
from app.core.exceptions import AppError
from app.models import (
    AssignmentStatus,
    Incident,
    IncidentAssignment,
    IncidentAssignmentEvent,
    IncidentStatus,
    Profile,
    Role,
    WorkerApplication,
    WorkerProfile,
)
from app.services.incidents import get_incident, transition_incident
from app.workforce.audit import emit
from app.workforce.dependencies import ActiveWorker
from app.workforce.notifications import notify
from app.workforce.workers import (
    candidates_for_incident,
    ensure_assignable,
    get_worker,
)

_ACTIVE_ASSIGNMENT_STATUSES = frozenset(
    {
        "OFFERED",
        "ACCEPTED",
        "IN_PROGRESS",
        "COMPLETION_SUBMITTED",
    }
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_assignment(
    session: Session, assignment_id: uuid.UUID, *, with_events: bool = True
) -> IncidentAssignment:
    query = select(IncidentAssignment)
    if with_events:
        query = query.options(
            selectinload(IncidentAssignment.events)
        )
    assignment = session.scalar(query.where(IncidentAssignment.id == assignment_id))
    if assignment is None:
        raise AppError(
            "Assignment not found.", status_code=404, code="assignment_not_found"
        )
    return assignment


def _owned_assignment(
    session: Session, assignment_id: uuid.UUID, worker: WorkerProfile
) -> IncidentAssignment:
    assignment = _get_assignment(session, assignment_id)
    if assignment.worker_id != worker.id:
        # Do not reveal the existence of another worker's assignment.
        raise AppError(
            "Assignment not found.", status_code=404, code="assignment_not_found"
        )
    return assignment


def _record(
    session: Session,
    assignment: IncidentAssignment,
    *,
    actor_id: uuid.UUID,
    new_status: AssignmentStatus,
    note: str | None,
) -> None:
    previous = assignment.status
    assignment.status = new_status
    session.add(
        IncidentAssignmentEvent(
            assignment_id=assignment.id,
            actor_id=actor_id,
            from_status=previous,
            to_status=new_status,
            note=note,
            created_at=_now(),
        )
    )
    emit(
        session,
        actor_id=actor_id,
        action=f"assignment_{new_status.value.lower()}",
        entity_type="incident_assignment",
        entity_id=assignment.id,
        previous_state=previous.value,
        new_state=new_status.value,
        metadata={"incident_id": assignment.incident_id, "note": note}
        if note
        else {"incident_id": assignment.incident_id},
    )


def _transition(
    session: Session,
    user: AuthenticatedUser,
    incident_id: uuid.UUID,
    target: IncidentStatus,
    note: str | None,
) -> None:
    transition_incident(
        session,
        user=user,
        incident_id=incident_id,
        target=target,
        department_id=None,
        note=note,
    )


def _notify_admins(
    session: Session,
    *,
    kind: str,
    title: str,
    body: str,
    assignment: IncidentAssignment,
) -> None:
    admins = session.scalars(
        select(Profile).where(
            Profile.role == Role.ADMIN, Profile.is_active.is_(True)
        )
    ).all()
    for admin in admins:
        notify(
            session,
            recipient_id=admin.id,
            kind=kind,
            title=title,
            body=body,
            entity_type="incident_assignment",
            entity_id=assignment.id,
        )


def _notify_worker(
    session: Session,
    *,
    worker: WorkerProfile,
    kind: str,
    title: str,
    body: str,
    assignment: IncidentAssignment,
) -> None:
    notify(
        session,
        recipient_id=worker.profile_id,
        kind=kind,
        title=title,
        body=body,
        entity_type="incident_assignment",
        entity_id=assignment.id,
    )


def assign_incident(
    session: Session,
    *,
    admin: AuthenticatedUser,
    incident_id: uuid.UUID,
    worker_profile_id: uuid.UUID,
    note: str | None,
    deadline: datetime | None,
) -> IncidentAssignment:
    incident = get_incident(session, incident_id, admin)
    worker = ensure_assignable(session, incident, worker_profile_id)
    ranked = candidates_for_incident(session, incident)
    rationale = next(
        (
            item["rationale"]
            for item in ranked
            if item["worker_profile_id"] == worker.id
        ),
        "Manual assignment; no automated dispatch performed.",
    )
    assignment = IncidentAssignment(
        incident_id=incident.id,
        worker_id=worker.id,
        assigned_by=admin.profile.id,
        status=AssignmentStatus.OFFERED,
        rationale=rationale,
        note=note,
        deadline=deadline,
    )
    session.add(assignment)
    session.flush()
    _record(
        session,
        assignment,
        actor_id=admin.profile.id,
        new_status=AssignmentStatus.OFFERED,
        note=note,
    )
    _transition(session, admin, incident.id, IncidentStatus.ASSIGNED, note)
    _notify_worker(
        session,
        worker=worker,
        kind="incident_assigned",
        title="New assignment offer",
        body=f"Incident {incident.id} has been assigned to you for review.",
        assignment=assignment,
    )
    session.commit()
    return _get_assignment(session, assignment.id)


def reassign_incident(
    session: Session,
    *,
    admin: AuthenticatedUser,
    assignment_id: uuid.UUID,
    worker_profile_id: uuid.UUID,
    note: str | None,
) -> IncidentAssignment:
    current = _get_assignment(session, assignment_id)
    if current.status.value not in _ACTIVE_ASSIGNMENT_STATUSES:
        raise AppError(
            "Only an active assignment can be reassigned.",
            status_code=409,
            code="assignment_not_active",
        )
    incident = get_incident(session, current.incident_id, admin)
    new_worker = ensure_assignable(session, incident, worker_profile_id)
    if new_worker.id == current.worker_id:
        raise AppError(
            "The incident is already assigned to this worker.",
            status_code=409,
            code="same_worker",
        )

    _record(
        session,
        current,
        actor_id=admin.profile.id,
        new_status=AssignmentStatus.CANCELLED,
        note=note or "Reassigned to another worker",
    )
    previous_worker = get_worker(session, current.worker_id)
    replacement = IncidentAssignment(
        incident_id=incident.id,
        worker_id=new_worker.id,
        assigned_by=admin.profile.id,
        status=AssignmentStatus.OFFERED,
        rationale=f"Reassigned by ADMIN from worker {current.worker_id}.",
        note=note,
        deadline=current.deadline,
    )
    session.add(replacement)
    session.flush()
    _record(
        session,
        replacement,
        actor_id=admin.profile.id,
        new_status=AssignmentStatus.OFFERED,
        note=note,
    )
    if incident.status is not IncidentStatus.ASSIGNED:
        _transition(session, admin, incident.id, IncidentStatus.ASSIGNED, note)
    _notify_worker(
        session,
        worker=previous_worker,
        kind="assignment_reassigned",
        title="Assignment reassigned",
        body=f"Incident {incident.id} was reassigned to another worker.",
        assignment=current,
    )
    _notify_worker(
        session,
        worker=new_worker,
        kind="incident_assigned",
        title="New assignment offer",
        body=f"Incident {incident.id} has been reassigned to you.",
        assignment=replacement,
    )
    session.commit()
    return _get_assignment(session, replacement.id)


def cancel_assignment(
    session: Session,
    *,
    admin: AuthenticatedUser,
    assignment_id: uuid.UUID,
    note: str | None,
) -> IncidentAssignment:
    assignment = _get_assignment(session, assignment_id)
    if assignment.status.value not in {"OFFERED", "ACCEPTED"}:
        raise AppError(
            "Only an offered or accepted assignment can be cancelled.",
            status_code=409,
            code="assignment_not_cancellable",
        )
    if not note:
        raise AppError(
            "A reason is required to cancel an assignment.",
            status_code=422,
            code="cancellation_reason_required",
        )
    incident = get_incident(session, assignment.incident_id, admin)
    worker = get_worker(session, assignment.worker_id)
    _record(
        session,
        assignment,
        actor_id=admin.profile.id,
        new_status=AssignmentStatus.CANCELLED,
        note=note,
    )
    if incident.status is IncidentStatus.ACCEPTED:
        _transition(session, admin, incident.id, IncidentStatus.ASSIGNED, note)
    _transition(session, admin, incident.id, IncidentStatus.VERIFIED, note)
    _notify_worker(
        session,
        worker=worker,
        kind="assignment_cancelled",
        title="Assignment cancelled",
        body=note,
        assignment=assignment,
    )
    session.commit()
    return _get_assignment(session, assignment.id)


def accept_assignment(
    session: Session,
    *,
    active: ActiveWorker,
    assignment_id: uuid.UUID,
    note: str | None,
) -> IncidentAssignment:
    assignment = _owned_assignment(session, assignment_id, active.worker)
    if assignment.status is not AssignmentStatus.OFFERED:
        raise AppError(
            "Only an offered assignment can be accepted.",
            status_code=409,
            code="assignment_not_offered",
        )
    incident = get_incident(session, assignment.incident_id, active.user)
    _record(
        session,
        assignment,
        actor_id=active.profile.id,
        new_status=AssignmentStatus.ACCEPTED,
        note=note,
    )
    _transition(session, active.user, incident.id, IncidentStatus.ACCEPTED, note)
    _notify_admins(
        session,
        kind="assignment_accepted",
        title="Assignment accepted",
        body=f"Worker {active.profile.full_name} accepted incident {incident.id}.",
        assignment=assignment,
    )
    session.commit()
    return _get_assignment(session, assignment.id)


def decline_assignment(
    session: Session,
    *,
    active: ActiveWorker,
    assignment_id: uuid.UUID,
    note: str | None,
) -> IncidentAssignment:
    assignment = _owned_assignment(session, assignment_id, active.worker)
    if assignment.status is not AssignmentStatus.OFFERED:
        raise AppError(
            "Only an offered assignment can be declined.",
            status_code=409,
            code="assignment_not_offered",
        )
    if not note:
        raise AppError(
            "A reason is required to decline an assignment.",
            status_code=422,
            code="decline_reason_required",
        )
    incident = get_incident(session, assignment.incident_id, active.user)
    _record(
        session,
        assignment,
        actor_id=active.profile.id,
        new_status=AssignmentStatus.DECLINED,
        note=note,
    )
    _transition(session, active.user, incident.id, IncidentStatus.VERIFIED, note)
    _notify_admins(
        session,
        kind="assignment_declined",
        title="Assignment declined",
        body=f"Worker {active.profile.full_name} declined incident {incident.id}: {note}",
        assignment=assignment,
    )
    session.commit()
    return _get_assignment(session, assignment.id)


def start_work(
    session: Session,
    *,
    active: ActiveWorker,
    assignment_id: uuid.UUID,
    note: str | None,
) -> IncidentAssignment:
    assignment = _owned_assignment(session, assignment_id, active.worker)
    if assignment.status is not AssignmentStatus.ACCEPTED:
        raise AppError(
            "Only an accepted assignment can be started.",
            status_code=409,
            code="assignment_not_accepted",
        )
    incident = get_incident(session, assignment.incident_id, active.user)
    _record(
        session,
        assignment,
        actor_id=active.profile.id,
        new_status=AssignmentStatus.IN_PROGRESS,
        note=note,
    )
    _transition(session, active.user, incident.id, IncidentStatus.IN_PROGRESS, note)
    emit(
        session,
        actor_id=active.profile.id,
        action="work_started",
        entity_type="incident_assignment",
        entity_id=assignment.id,
        metadata={"incident_id": assignment.incident_id},
    )
    _notify_admins(
        session,
        kind="work_started",
        title="Work started",
        body=f"Worker {active.profile.full_name} started incident {incident.id}.",
        assignment=assignment,
    )
    session.commit()
    return _get_assignment(session, assignment.id)


def update_progress(
    session: Session,
    *,
    active: ActiveWorker,
    assignment_id: uuid.UUID,
    note: str | None,
    progress_percent: int,
) -> IncidentAssignment:
    assignment = _owned_assignment(session, assignment_id, active.worker)
    if assignment.status is not AssignmentStatus.IN_PROGRESS:
        raise AppError(
            "Progress can only be updated on work in progress.",
            status_code=409,
            code="assignment_not_in_progress",
        )
    emit(
        session,
        actor_id=active.profile.id,
        action="work_progress_updated",
        entity_type="incident_assignment",
        entity_id=assignment.id,
        new_state=f"{progress_percent}%",
        metadata={"incident_id": assignment.incident_id, "note": note}
        if note
        else {"incident_id": assignment.incident_id},
    )
    session.commit()
    return _get_assignment(session, assignment.id)


def submit_completion(
    session: Session,
    *,
    active: ActiveWorker,
    assignment_id: uuid.UUID,
    note: str,
    evidence_note: str | None,
) -> IncidentAssignment:
    assignment = _owned_assignment(session, assignment_id, active.worker)
    if assignment.status is not AssignmentStatus.IN_PROGRESS:
        raise AppError(
            "Only work in progress can be completed.",
            status_code=409,
            code="assignment_not_in_progress",
        )
    incident = get_incident(session, assignment.incident_id, active.user)
    assignment.completion_note = note
    assignment.completed_at = _now()
    _record(
        session,
        assignment,
        actor_id=active.profile.id,
        new_status=AssignmentStatus.COMPLETION_SUBMITTED,
        note=note,
    )
    _transition(
        session,
        active.user,
        incident.id,
        IncidentStatus.COMPLETION_SUBMITTED,
        note,
    )
    emit(
        session,
        actor_id=active.profile.id,
        action="completion_submitted",
        entity_type="incident_assignment",
        entity_id=assignment.id,
        metadata={
            "incident_id": assignment.incident_id,
            "evidence_note": evidence_note,
        },
    )
    _notify_admins(
        session,
        kind="completion_submitted",
        title="Completion submitted for verification",
        body=f"Worker {active.profile.full_name} submitted completion for incident {incident.id}.",
        assignment=assignment,
    )
    session.commit()
    return _get_assignment(session, assignment.id)


def verify_completion(
    session: Session,
    *,
    admin: AuthenticatedUser,
    assignment_id: uuid.UUID,
    approve: bool,
    note: str | None,
) -> IncidentAssignment:
    assignment = _get_assignment(session, assignment_id)
    if assignment.status is not AssignmentStatus.COMPLETION_SUBMITTED:
        raise AppError(
            "Only a submitted completion can be verified.",
            status_code=409,
            code="completion_not_submitted",
        )
    if not approve and not note:
        raise AppError(
            "A reason is required when requesting rework.",
            status_code=422,
            code="review_note_required",
        )
    incident = get_incident(session, assignment.incident_id, admin)
    worker = get_worker(session, assignment.worker_id)
    assignment.review_note = note

    if approve:
        assignment.verified_at = _now()
        _record(
            session,
            assignment,
            actor_id=admin.profile.id,
            new_status=AssignmentStatus.VERIFIED_COMPLETED,
            note=note,
        )
        _transition(
            session,
            admin,
            incident.id,
            IncidentStatus.VERIFIED_COMPLETED,
            note,
        )
        _transition(session, admin, incident.id, IncidentStatus.RESOLVED, note)
        emit(
            session,
            actor_id=admin.profile.id,
            action="completion_verified",
            entity_type="incident_assignment",
            entity_id=assignment.id,
            metadata={"incident_id": incident.id},
        )
        emit(
            session,
            actor_id=admin.profile.id,
            action="incident_resolved",
            entity_type="incident",
            entity_id=incident.id,
            new_state=IncidentStatus.RESOLVED.value,
        )
        _notify_worker(
            session,
            worker=worker,
            kind="completion_verified",
            title="Completion verified",
            body=f"Incident {incident.id} was verified and resolved.",
            assignment=assignment,
        )
        if incident.reporter_id:
            notify(
                session,
                recipient_id=incident.reporter_id,
                kind="incident_resolved",
                title="Your report was resolved",
                body=f"Incident {incident.id} has been resolved.",
                entity_type="incident",
                entity_id=incident.id,
            )
    else:
        _record(
            session,
            assignment,
            actor_id=admin.profile.id,
            new_status=AssignmentStatus.IN_PROGRESS,
            note=note,
        )
        _transition(session, admin, incident.id, IncidentStatus.IN_PROGRESS, note)
        emit(
            session,
            actor_id=admin.profile.id,
            action="completion_rejected",
            entity_type="incident_assignment",
            entity_id=assignment.id,
            metadata={"incident_id": incident.id},
        )
        _notify_worker(
            session,
            worker=worker,
            kind="completion_rejected",
            title="Completion requires rework",
            body=note or "The submitted completion was not accepted.",
            assignment=assignment,
        )
    session.commit()
    return _get_assignment(session, assignment.id)


def list_assignments(
    session: Session,
    *,
    worker_profile_id: uuid.UUID | None = None,
    incident_id: uuid.UUID | None = None,
    status: AssignmentStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[IncidentAssignment], int]:
    query = select(IncidentAssignment).options(selectinload(IncidentAssignment.events))
    count_query = select(func.count()).select_from(IncidentAssignment)
    if worker_profile_id is not None:
        query = query.where(IncidentAssignment.worker_id == worker_profile_id)
        count_query = count_query.where(
            IncidentAssignment.worker_id == worker_profile_id
        )
    if incident_id is not None:
        query = query.where(IncidentAssignment.incident_id == incident_id)
        count_query = count_query.where(IncidentAssignment.incident_id == incident_id)
    if status is not None:
        query = query.where(IncidentAssignment.status == status)
        count_query = count_query.where(IncidentAssignment.status == status)
    total = int(session.scalar(count_query) or 0)
    rows = session.scalars(
        query.order_by(IncidentAssignment.created_at.desc()).limit(limit).offset(offset)
    ).all()
    return list(rows), total


def admin_overview(session: Session) -> dict[str, int]:
    incident_rows = session.execute(
        select(Incident.status, func.count()).group_by(Incident.status)
    ).all()
    incidents = {status: int(count) for status, count in incident_rows}
    totals = int(session.scalar(select(func.count()).select_from(Incident)) or 0)
    application_rows = session.execute(
        select(WorkerApplication.status, func.count()).group_by(
            WorkerApplication.status
        )
    ).all()
    applications = {status.value: int(count) for status, count in application_rows}
    worker_rows = session.execute(
        select(WorkerProfile.status, func.count()).group_by(WorkerProfile.status)
    ).all()
    workers = {status.value: int(count) for status, count in worker_rows}
    return {
        "total_incidents": totals,
        "unreviewed_incidents": incidents.get(IncidentStatus.OPEN, 0),
        "verified_awaiting_assignment": incidents.get(IncidentStatus.VERIFIED, 0),
        "assigned_incidents": incidents.get(IncidentStatus.ASSIGNED, 0),
        "in_progress_incidents": incidents.get(IncidentStatus.IN_PROGRESS, 0),
        "awaiting_verification": incidents.get(
            IncidentStatus.COMPLETION_SUBMITTED, 0
        ),
        "verified_completed": incidents.get(IncidentStatus.VERIFIED_COMPLETED, 0),
        "resolved_incidents": incidents.get(IncidentStatus.RESOLVED, 0),
        "rejected_incidents": applications.get("REJECTED", 0),
        "pending_applications": applications.get("PENDING", 0)
        + applications.get("UNDER_REVIEW", 0),
        "active_workers": workers.get("ACTIVE", 0),
        "suspended_workers": workers.get("SUSPENDED", 0),
    }
