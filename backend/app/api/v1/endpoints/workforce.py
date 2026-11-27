"""Municipal workforce APIs: applications, workers, assignments, audit, notifications."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser, get_current_user, require_active_user, require_admin
from app.core.exceptions import AppError
from app.db.session import get_db_session
from app.models import (
    AssignmentStatus,
    IncidentAssignment,
    Profile,
    Role,
    WorkerApplication,
    WorkerApplicationStatus,
    WorkerProfile,
    WorkerStatus,
    WorkforceEvent,
    WorkforceNotification,
)
from app.schemas.workforce import (
    AdminOverviewResponse,
    ApplicationListResponse,
    ApplicationReviewRequest,
    AssignmentCandidateResponse,
    AssignmentCreateRequest,
    AssignmentListResponse,
    AssignmentNoteRequest,
    AssignmentResponse,
    CandidateListResponse,
    CompletionRequest,
    EventListResponse,
    NotificationListResponse,
    NotificationResponse,
    ProgressRequest,
    ReassignRequest,
    VerificationRequest,
    WorkerApplicationCreate,
    WorkerApplicationResponse,
    WorkerListResponse,
    WorkerProfileResponse,
    WorkforceEventResponse,
)
from app.services.incidents import get_incident
from app.workforce.applications import (
    get_own_application,
    list_applications,
    review_application,
    submit_application,
)
from app.workforce.assignments import (
    accept_assignment,
    admin_overview,
    assign_incident,
    cancel_assignment,
    decline_assignment,
    list_assignments,
    reassign_incident,
    start_work,
    submit_completion,
    update_progress,
    verify_completion,
)
from app.workforce.dependencies import ActiveWorker, require_active_worker
from app.workforce.notifications import get_for_recipient, list_for_recipient
from app.workforce.workers import (
    assignment_counts,
    candidates_for_incident,
    get_worker,
    list_workers,
    set_worker_status,
)

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db_session)]
AdminUser = Annotated[AuthenticatedUser, Depends(require_admin)]
ActiveUser = Annotated[AuthenticatedUser, Depends(require_active_user)]
WorkerUser = Annotated[ActiveWorker, Depends(require_active_worker)]


def _worker_response(
    session: Session, worker: WorkerProfile
) -> WorkerProfileResponse:
    profile = session.get(Profile, worker.profile_id)
    active, total = assignment_counts(session, worker.id)
    return WorkerProfileResponse(
        id=worker.id,
        profile_id=worker.profile_id,
        application_id=worker.application_id,
        specialization=worker.specialization,
        department_id=worker.department_id,
        service_area=worker.service_area,
        status=worker.status,
        approved_by=worker.approved_by,
        approved_at=worker.approved_at,
        full_name=profile.full_name if profile else None,
        active_assignments=active,
        total_assignments=total,
    )


# ---------------------------------------------------------------- applications


@router.post(
    "/applications",
    response_model=WorkerApplicationResponse,
    status_code=201,
    summary="Apply for worker status",
)
def apply_for_worker(
    payload: WorkerApplicationCreate,
    session: DbSession,
    user: ActiveUser,
) -> WorkerApplication:
    return submit_application(session, user=user, payload=payload)


@router.get(
    "/applications/mine",
    response_model=WorkerApplicationResponse,
    summary="Read the caller's worker application",
)
def my_application(session: DbSession, user: ActiveUser) -> WorkerApplication:
    application = get_own_application(session, user.profile.id)
    if application is None:
        raise AppError(
            "No worker application exists for this account.",
            status_code=404,
            code="application_not_found",
        )
    return application


@router.get(
    "/applications",
    response_model=ApplicationListResponse,
    summary="List worker applications (ADMIN)",
)
def list_worker_applications(
    session: DbSession,
    _admin: AdminUser,
    status: WorkerApplicationStatus | None = None,
    specialization: str | None = None,
    department_id: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ApplicationListResponse:
    rows, total = list_applications(
        session,
        status=status,
        specialization=specialization,
        department_id=department_id,
        limit=limit,
        offset=offset,
    )
    return ApplicationListResponse(
        items=[WorkerApplicationResponse.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/applications/{application_id}",
    response_model=WorkerApplicationResponse,
    summary="Open a worker application (ADMIN)",
)
def read_application(
    application_id: uuid.UUID, session: DbSession, _admin: AdminUser
) -> WorkerApplication:
    application = session.get(WorkerApplication, application_id)
    if application is None:
        raise AppError(
            "Worker application not found.",
            status_code=404,
            code="application_not_found",
        )
    return application


@router.post(
    "/applications/{application_id}/review",
    response_model=WorkerApplicationResponse,
    summary="Review a worker application (ADMIN)",
)
def review_worker_application(
    application_id: uuid.UUID,
    payload: ApplicationReviewRequest,
    session: DbSession,
    admin: AdminUser,
) -> WorkerApplication:
    return review_application(
        session,
        admin=admin,
        application_id=application_id,
        request=payload,
    )


# --------------------------------------------------------------------- workers


@router.get(
    "/workers",
    response_model=WorkerListResponse,
    summary="List workers (ADMIN)",
)
def list_all_workers(
    session: DbSession,
    _admin: AdminUser,
    status: WorkerStatus | None = None,
    specialization: str | None = None,
    department_id: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> WorkerListResponse:
    rows, total = list_workers(
        session,
        status=status,
        specialization=specialization,
        department_id=department_id,
        limit=limit,
        offset=offset,
    )
    return WorkerListResponse(
        items=[_worker_response(session, row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/workers/me",
    response_model=WorkerProfileResponse,
    summary="Read the caller's approved worker profile",
)
def my_worker_profile(session: DbSession, worker: WorkerUser) -> WorkerProfileResponse:
    return _worker_response(session, worker.worker)


@router.post(
    "/workers/{worker_profile_id}/suspend",
    response_model=WorkerProfileResponse,
    summary="Suspend a worker (ADMIN)",
)
def suspend_worker(
    worker_profile_id: uuid.UUID,
    payload: AssignmentNoteRequest,
    session: DbSession,
    admin: AdminUser,
) -> WorkerProfileResponse:
    worker = set_worker_status(
        session,
        admin=admin,
        worker_profile_id=worker_profile_id,
        status=WorkerStatus.SUSPENDED,
        reason=payload.note,
    )
    return _worker_response(session, worker)


@router.post(
    "/workers/{worker_profile_id}/reactivate",
    response_model=WorkerProfileResponse,
    summary="Reactivate a worker (ADMIN)",
)
def reactivate_worker(
    worker_profile_id: uuid.UUID,
    session: DbSession,
    admin: AdminUser,
) -> WorkerProfileResponse:
    worker = set_worker_status(
        session,
        admin=admin,
        worker_profile_id=worker_profile_id,
        status=WorkerStatus.ACTIVE,
        reason="Reactivated by administrator",
    )
    return _worker_response(session, worker)


# ------------------------------------------------------------------- overview


@router.get(
    "/admin/overview",
    response_model=AdminOverviewResponse,
    summary="Real workforce and incident counts (ADMIN)",
)
def admin_dashboard_overview(session: DbSession, _admin: AdminUser) -> AdminOverviewResponse:
    return AdminOverviewResponse(**admin_overview(session))


# ----------------------------------------------------------------- assignments


@router.get(
    "/assignments/candidates",
    response_model=CandidateListResponse,
    summary="Rank eligible workers for a verified incident (ADMIN)",
)
def assignment_candidates(
    session: DbSession,
    _admin: AdminUser,
    incident_id: uuid.UUID,
) -> CandidateListResponse:
    incident = get_incident(session, incident_id, _admin)
    candidates = candidates_for_incident(session, incident)
    return CandidateListResponse(
        incident_id=incident.id,
        items=[AssignmentCandidateResponse(**item) for item in candidates],
    )


@router.post(
    "/assignments",
    response_model=AssignmentResponse,
    status_code=201,
    summary="Assign a verified incident to a worker (ADMIN)",
)
def create_assignment(
    payload: AssignmentCreateRequest, session: DbSession, admin: AdminUser
) -> IncidentAssignment:
    return assign_incident(
        session,
        admin=admin,
        incident_id=payload.incident_id,
        worker_profile_id=payload.worker_profile_id,
        note=payload.note,
        deadline=payload.deadline,
    )


@router.get(
    "/assignments",
    response_model=AssignmentListResponse,
    summary="List assignments (ADMIN or assigned worker)",
)
def list_work_assignments(
    session: DbSession,
    user: ActiveUser,
    incident_id: uuid.UUID | None = None,
    status: AssignmentStatus | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> AssignmentListResponse:
    if user.profile.role is Role.CITIZEN:
        raise AppError(
            "Worker authorization is required.",
            status_code=403,
            code="insufficient_role",
        )
    worker_profile_id = None
    if user.profile.role is not Role.ADMIN:
        worker = session.scalar(
            select(WorkerProfile).where(WorkerProfile.profile_id == user.profile.id)
        )
        if worker is None:
            raise AppError(
                "Worker profile not found.",
                status_code=404,
                code="worker_not_found",
            )
        worker_profile_id = worker.id
    rows, total = list_assignments(
        session,
        worker_profile_id=worker_profile_id,
        incident_id=incident_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return AssignmentListResponse(
        items=[AssignmentResponse.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/assignments/{assignment_id}",
    response_model=AssignmentResponse,
    summary="Open an assignment",
)
def read_assignment(
    assignment_id: uuid.UUID, session: DbSession, user: ActiveUser
) -> IncidentAssignment:
    assignment = session.scalar(
        select(IncidentAssignment).where(IncidentAssignment.id == assignment_id)
    )
    if assignment is None:
        raise AppError(
            "Assignment not found.", status_code=404, code="assignment_not_found"
        )
    if user.profile.role is not Role.ADMIN:
        worker = session.scalar(
            select(WorkerProfile).where(WorkerProfile.profile_id == user.profile.id)
        )
        if worker is None or assignment.worker_id != worker.id:
            raise AppError(
                "Assignment not found.", status_code=404, code="assignment_not_found"
            )
    return assignment


@router.post(
    "/assignments/{assignment_id}/reassign",
    response_model=AssignmentResponse,
    summary="Reassign an incident (ADMIN)",
)
def reassign(
    assignment_id: uuid.UUID,
    payload: ReassignRequest,
    session: DbSession,
    admin: AdminUser,
) -> IncidentAssignment:
    return reassign_incident(
        session,
        admin=admin,
        assignment_id=assignment_id,
        worker_profile_id=payload.worker_profile_id,
        note=payload.note,
    )


@router.post(
    "/assignments/{assignment_id}/cancel",
    response_model=AssignmentResponse,
    summary="Cancel an assignment (ADMIN)",
)
def cancel(
    assignment_id: uuid.UUID,
    payload: AssignmentNoteRequest,
    session: DbSession,
    admin: AdminUser,
) -> IncidentAssignment:
    return cancel_assignment(
        session,
        admin=admin,
        assignment_id=assignment_id,
        note=payload.note,
    )


@router.post(
    "/assignments/{assignment_id}/accept",
    response_model=AssignmentResponse,
    summary="Accept an assignment (approved worker)",
)
def accept(
    assignment_id: uuid.UUID,
    payload: AssignmentNoteRequest,
    session: DbSession,
    worker: WorkerUser,
) -> IncidentAssignment:
    return accept_assignment(
        session,
        active=worker,
        assignment_id=assignment_id,
        note=payload.note,
    )


@router.post(
    "/assignments/{assignment_id}/decline",
    response_model=AssignmentResponse,
    summary="Decline an assignment (approved worker)",
)
def decline(
    assignment_id: uuid.UUID,
    payload: AssignmentNoteRequest,
    session: DbSession,
    worker: WorkerUser,
) -> IncidentAssignment:
    return decline_assignment(
        session,
        active=worker,
        assignment_id=assignment_id,
        note=payload.note,
    )


@router.post(
    "/assignments/{assignment_id}/start",
    response_model=AssignmentResponse,
    summary="Start work (approved worker)",
)
def start(
    assignment_id: uuid.UUID,
    payload: AssignmentNoteRequest,
    session: DbSession,
    worker: WorkerUser,
) -> IncidentAssignment:
    return start_work(
        session,
        active=worker,
        assignment_id=assignment_id,
        note=payload.note,
    )


@router.post(
    "/assignments/{assignment_id}/progress",
    response_model=AssignmentResponse,
    summary="Record work progress (approved worker)",
)
def progress(
    assignment_id: uuid.UUID,
    payload: ProgressRequest,
    session: DbSession,
    worker: WorkerUser,
) -> IncidentAssignment:
    return update_progress(
        session,
        active=worker,
        assignment_id=assignment_id,
        note=payload.note,
        progress_percent=payload.progress_percent,
    )


@router.post(
    "/assignments/{assignment_id}/complete",
    response_model=AssignmentResponse,
    summary="Submit completion for verification (approved worker)",
)
def complete(
    assignment_id: uuid.UUID,
    payload: CompletionRequest,
    session: DbSession,
    worker: WorkerUser,
) -> IncidentAssignment:
    return submit_completion(
        session,
        active=worker,
        assignment_id=assignment_id,
        note=payload.note,
        evidence_note=payload.evidence_note,
    )


@router.post(
    "/assignments/{assignment_id}/verify",
    response_model=AssignmentResponse,
    summary="Verify or reject a completion (ADMIN)",
)
def verify(
    assignment_id: uuid.UUID,
    payload: VerificationRequest,
    session: DbSession,
    admin: AdminUser,
) -> IncidentAssignment:
    return verify_completion(
        session,
        admin=admin,
        assignment_id=assignment_id,
        approve=payload.approve,
        note=payload.note,
    )


# -------------------------------------------------------------- audit & notices


@router.get(
    "/events",
    response_model=EventListResponse,
    summary="Read immutable workforce audit events (ADMIN)",
)
def list_events(
    session: DbSession,
    _admin: AdminUser,
    entity_type: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> EventListResponse:
    query = select(WorkforceEvent)
    count_query = select(func.count()).select_from(WorkforceEvent)
    if entity_type:
        query = query.where(WorkforceEvent.entity_type == entity_type)
        count_query = count_query.where(WorkforceEvent.entity_type == entity_type)
    total = int(session.scalar(count_query) or 0)
    rows = session.scalars(
        query.order_by(WorkforceEvent.created_at.desc()).limit(limit).offset(offset)
    ).all()
    return EventListResponse(
        items=[WorkforceEventResponse.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/notifications",
    response_model=NotificationListResponse,
    summary="Read the caller's in-app notifications",
)
def list_notifications(session: DbSession, user: ActiveUser) -> NotificationListResponse:
    # A deployment that has not applied the workforce migration yet gets an
    # empty inbox rather than a 500 that breaks the whole dashboard.
    rows = list_for_recipient(session, user.profile.id)
    unread = sum(1 for row in rows if row.read_at is None)
    return NotificationListResponse(
        items=[NotificationResponse.model_validate(row) for row in rows],
        total=len(rows),
        unread=unread,
    )


@router.post(
    "/notifications/{notification_id}/read",
    response_model=NotificationResponse,
    summary="Mark a notification as read",
)
def mark_notification_read(
    notification_id: uuid.UUID, session: DbSession, user: ActiveUser
) -> WorkforceNotification:
    notification = get_for_recipient(session, notification_id, user.profile.id)
    if notification is None:
        raise AppError(
            "Notification not found.", status_code=404, code="notification_not_found"
        )
    if notification.read_at is None:
        notification.read_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(notification)
    return notification
