"""Worker management, workload and explainable assignment eligibility."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser
from app.core.exceptions import AppError
from app.models import (
    Incident,
    IncidentAssignment,
    IncidentCategory,
    IncidentStatus,
    Profile,
    Role,
    WorkerProfile,
    WorkerStatus,
)
from app.workforce.audit import emit
from app.workforce.notifications import notify

_ACTIVE_ASSIGNMENT_STATUSES = frozenset(
    {
        IncidentStatus.VERIFIED,
        IncidentStatus.ASSIGNED,
        IncidentStatus.ACCEPTED,
        IncidentStatus.IN_PROGRESS,
        IncidentStatus.COMPLETION_SUBMITTED,
    }
)

_ASSIGNMENT_WORKLOAD = frozenset(
    {
        "OFFERED",
        "ACCEPTED",
        "IN_PROGRESS",
        "COMPLETION_SUBMITTED",
    }
)

# Configurable keyword groups used only for ranking. No ward boundaries are
# inferred: service-area strings are supplied by the application itself.
_CATEGORY_KEYWORDS: dict[IncidentCategory, frozenset[str]] = {
    IncidentCategory.ROADS: frozenset({"road", "roads", "highway", "street"}),
    IncidentCategory.DRAINAGE: frozenset({"drain", "drainage", "water", "flood"}),
    IncidentCategory.SANITATION: frozenset({"sanitation", "waste", "clean", "refuse"}),
    IncidentCategory.UTILITIES: frozenset({"utility", "utilities", "power", "electric"}),
    IncidentCategory.PUBLIC_SAFETY: frozenset({"safety", "police", "security"}),
    IncidentCategory.HEALTH: frozenset({"health", "medical", "clinic", "hospital"}),
    IncidentCategory.ENVIRONMENT: frozenset({"environment", "forestry", "pollution"}),
    IncidentCategory.OTHER: frozenset({"general", "other"}),
}


def get_worker(session: Session, worker_profile_id: uuid.UUID) -> WorkerProfile:
    worker = session.get(WorkerProfile, worker_profile_id)
    if worker is None:
        raise AppError(
            "Worker profile not found.", status_code=404, code="worker_not_found"
        )
    return worker


def list_workers(
    session: Session,
    *,
    status: WorkerStatus | None = None,
    specialization: str | None = None,
    department_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[WorkerProfile], int]:
    query = select(WorkerProfile).join(Profile, Profile.id == WorkerProfile.profile_id)
    count_query = (
        select(func.count())
        .select_from(WorkerProfile)
        .join(Profile, Profile.id == WorkerProfile.profile_id)
    )
    if status is not None:
        query = query.where(WorkerProfile.status == status)
        count_query = count_query.where(WorkerProfile.status == status)
    if specialization:
        expression = func.lower(WorkerProfile.specialization) == specialization.strip().lower()
        query = query.where(expression)
        count_query = count_query.where(expression)
    if department_id is not None:
        query = query.where(WorkerProfile.department_id == department_id)
        count_query = count_query.where(WorkerProfile.department_id == department_id)
    total = int(session.scalar(count_query) or 0)
    rows = session.scalars(
        query.order_by(Profile.full_name).limit(limit).offset(offset)
    ).all()
    return list(rows), total


def worker_workload(session: Session, worker_profile_id: uuid.UUID) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(IncidentAssignment)
            .where(
                IncidentAssignment.worker_id == worker_profile_id,
                IncidentAssignment.status.in_(_ASSIGNMENT_WORKLOAD),
            )
        )
        or 0
    )


def assignment_counts(session: Session, worker_profile_id: uuid.UUID) -> tuple[int, int]:
    totals = session.execute(
        select(IncidentAssignment.status, func.count())
        .where(IncidentAssignment.worker_id == worker_profile_id)
        .group_by(IncidentAssignment.status)
    ).all()
    active = sum(
        int(count)
        for status, count in totals
        if status.value in _ASSIGNMENT_WORKLOAD
    )
    return active, sum(int(count) for _, count in totals)


def set_worker_status(
    session: Session,
    *,
    admin: AuthenticatedUser,
    worker_profile_id: uuid.UUID,
    status: WorkerStatus,
    reason: str | None,
) -> WorkerProfile:
    worker = get_worker(session, worker_profile_id)
    previous = worker.status
    if previous is status:
        return worker
    if status is WorkerStatus.SUSPENDED and not reason:
        raise AppError(
            "A reason is required to suspend a worker.",
            status_code=422,
            code="suspension_reason_required",
        )
    worker.status = status
    emit(
        session,
        actor_id=admin.profile.id,
        action="worker_suspended" if status is WorkerStatus.SUSPENDED else "worker_reactivated",
        entity_type="worker_profile",
        entity_id=worker.id,
        previous_state=previous.value,
        new_state=status.value,
        metadata={"reason": reason} if reason else None,
    )
    notify(
        session,
        recipient_id=worker.profile_id,
        kind="worker_suspended" if status is WorkerStatus.SUSPENDED else "worker_reactivated",
        title="Worker status changed",
        body=reason or f"Your worker status is now {status.value}.",
        entity_type="worker_profile",
        entity_id=worker.id,
    )
    session.commit()
    session.refresh(worker)
    return worker


def _area_match(worker: WorkerProfile, incident: Incident) -> bool:
    if (
        worker.department_id is not None
        and worker.department_id == incident.assigned_department_id
    ):
        return True
    area = worker.service_area.strip().lower()
    if not area:
        return False
    haystack = (incident.address or "").lower()
    return area in haystack or haystack in area


def _specialization_match(worker: WorkerProfile, incident: Incident) -> bool:
    keywords = _CATEGORY_KEYWORDS.get(incident.category, frozenset())
    text = worker.specialization.lower()
    return any(keyword in text for keyword in keywords)


def candidates_for_incident(
    session: Session, incident: Incident
) -> list[dict[str, Any]]:
    """Return deterministic, explainable candidates. Never auto-dispatches."""
    workers = session.scalars(
        select(WorkerProfile)
        .join(Profile, Profile.id == WorkerProfile.profile_id)
        .where(
            WorkerProfile.status == WorkerStatus.ACTIVE,
            Profile.is_active.is_(True),
        )
    ).all()

    already_assigned = set(
        session.scalars(
            select(IncidentAssignment.worker_id).where(
                IncidentAssignment.incident_id == incident.id,
                IncidentAssignment.status.in_(
                    {"OFFERED", "ACCEPTED", "IN_PROGRESS", "COMPLETION_SUBMITTED"}
                ),
            )
        ).all()
    )

    results: list[dict[str, Any]] = []
    for worker in workers:
        profile = session.get(Profile, worker.profile_id)
        workload = worker_workload(session, worker.id)
        area = _area_match(worker, incident)
        specialty = _specialization_match(worker, incident)
        already = worker.id in already_assigned
        eligible = not already
        score = (2 if area else 0) + (2 if specialty else 0) - workload
        reasons = [
            "active approved worker",
            f"service area {'match' if area else 'not matched'}",
            f"specialization {'match' if specialty else 'not matched'}",
            f"{workload} active assignment(s)",
        ]
        if already:
            reasons.append("already assigned to this incident")
        rationale = "; ".join(reasons)
        results.append(
            {
                "worker_profile_id": worker.id,
                "profile_id": worker.profile_id,
                "full_name": profile.full_name if profile else "Unknown",
                "specialization": worker.specialization,
                "service_area": worker.service_area,
                "department_id": worker.department_id,
                "active_assignments": workload,
                "area_match": area,
                "specialization_match": specialty,
                "eligible": eligible,
                "rationale": rationale,
                "_score": score,
            }
        )
    results.sort(key=lambda item: (-int(item["_score"]), str(item["worker_profile_id"])))
    for item in results:
        item.pop("_score", None)
    return results


def ensure_assignable(
    session: Session, incident: Incident, worker_profile_id: uuid.UUID
) -> WorkerProfile:
    worker = get_worker(session, worker_profile_id)
    if worker.status is not WorkerStatus.ACTIVE:
        raise AppError(
            "The worker is not active.", status_code=409, code="worker_not_active"
        )
    applicant = session.get(Profile, worker.profile_id)
    if applicant is None or applicant.role is not Role.WORKER or not applicant.is_active:
        raise AppError(
            "The worker account is not authorized.",
            status_code=409,
            code="worker_not_authorized",
        )
    if incident.status not in _ACTIVE_ASSIGNMENT_STATUSES and incident.status is not IncidentStatus.VERIFIED:
        raise AppError(
            "The incident is not verified and awaiting assignment.",
            status_code=409,
            code="incident_not_assignable",
        )
    current = session.scalar(
        select(IncidentAssignment).where(
            IncidentAssignment.incident_id == incident.id,
            IncidentAssignment.status.in_(
                {"OFFERED", "ACCEPTED", "IN_PROGRESS", "COMPLETION_SUBMITTED"}
            ),
        )
    )
    if current is not None and current.worker_id != worker.id:
        raise AppError(
            "This incident is already assigned to an active worker.",
            status_code=409,
            code="incident_already_assigned",
        )
    return worker
