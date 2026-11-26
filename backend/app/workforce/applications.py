"""Worker application submission and ADMIN review lifecycle."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser
from app.core.exceptions import AppError
from app.models import (
    Department,
    Profile,
    Role,
    WorkerApplication,
    WorkerApplicationStatus,
    WorkerProfile,
    WorkerStatus,
)
from app.schemas.workforce import (
    ApplicationReviewRequest,
    WorkerApplicationCreate,
)
from app.services.profiles import change_profile_role
from app.workforce.audit import emit
from app.workforce.notifications import notify

_TERMINAL = frozenset(
    {WorkerApplicationStatus.APPROVED, WorkerApplicationStatus.REJECTED}
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_application(
    session: Session, application_id: uuid.UUID
) -> WorkerApplication:
    application = session.get(WorkerApplication, application_id)
    if application is None:
        raise AppError(
            "Worker application not found.",
            status_code=404,
            code="application_not_found",
        )
    return application


def _notify_admins(
    session: Session,
    *,
    kind: str,
    title: str,
    body: str,
    application: WorkerApplication,
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
            entity_type="worker_application",
            entity_id=application.id,
        )


def submit_application(
    session: Session,
    *,
    user: AuthenticatedUser,
    payload: WorkerApplicationCreate,
) -> WorkerApplication:
    if user.profile.role is not Role.CITIZEN:
        raise AppError(
            "Only CITIZEN accounts may apply for worker status.",
            status_code=409,
            code="application_not_allowed",
        )
    existing = session.scalar(
        select(WorkerApplication).where(
            WorkerApplication.applicant_id == user.profile.id
        )
    )
    if existing is not None:
        raise AppError(
            "A worker application already exists for this account.",
            status_code=409,
            code="duplicate_application",
        )

    department_id = payload.department_id
    if department_id is not None:
        department = session.get(Department, department_id)
        if department is None or not department.is_active:
            raise AppError(
                "Department not found or inactive.",
                status_code=422,
                code="invalid_department",
            )

    application = WorkerApplication(
        applicant_id=user.profile.id,
        full_name=payload.full_name,
        phone=payload.phone,
        email=payload.email,
        specialization=payload.specialization,
        department_id=department_id,
        service_area=payload.service_area,
        address=payload.address,
        experience=payload.experience,
        credentials_note=payload.credentials_note,
        status=WorkerApplicationStatus.PENDING,
    )
    session.add(application)
    # The UUID default is assigned on INSERT; flush before emitting the audit
    # event so the immutable event carries a non-null entity id.
    session.flush()
    emit(
        session,
        actor_id=user.profile.id,
        action="worker_application_submitted",
        entity_type="worker_application",
        entity_id=application.id,
        new_state=WorkerApplicationStatus.PENDING.value,
    )
    _notify_admins(
        session,
        kind="worker_application_submitted",
        title="New worker application",
        body=f"{application.full_name} applied for {application.specialization}.",
        application=application,
    )
    session.commit()
    session.refresh(application)
    return application


def get_own_application(
    session: Session, profile_id: uuid.UUID
) -> WorkerApplication | None:
    return session.scalar(
        select(WorkerApplication).where(
            WorkerApplication.applicant_id == profile_id
        )
    )


def list_applications(
    session: Session,
    *,
    status: WorkerApplicationStatus | None = None,
    specialization: str | None = None,
    department_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[WorkerApplication], int]:
    query = select(WorkerApplication)
    count_query = select(func.count()).select_from(WorkerApplication)
    if status is not None:
        query = query.where(WorkerApplication.status == status)
        count_query = count_query.where(WorkerApplication.status == status)
    if specialization:
        query = query.where(
            func.lower(WorkerApplication.specialization)
            == specialization.strip().lower()
        )
        count_query = count_query.where(
            func.lower(WorkerApplication.specialization)
            == specialization.strip().lower()
        )
    if department_id is not None:
        query = query.where(WorkerApplication.department_id == department_id)
        count_query = count_query.where(
            WorkerApplication.department_id == department_id
        )
    total = int(session.scalar(count_query) or 0)
    rows = session.scalars(
        query.order_by(WorkerApplication.created_at.desc()).limit(limit).offset(offset)
    ).all()
    return list(rows), total


def review_application(
    session: Session,
    *,
    admin: AuthenticatedUser,
    application_id: uuid.UUID,
    request: ApplicationReviewRequest,
) -> WorkerApplication:
    application = _get_application(session, application_id)
    previous = application.status

    if request.decision in {"APPROVE", "REJECT"} and previous in _TERMINAL:
        raise AppError(
            "This application has already been decided.",
            status_code=409,
            code="application_already_decided",
        )
    if request.decision in {"REJECT", "REQUEST_INFO"} and not request.note:
        raise AppError(
            "A review note is required for rejection or an information request.",
            status_code=422,
            code="review_note_required",
        )

    application.reviewer_id = admin.profile.id
    application.reviewed_at = _now()
    application.review_note = request.note

    if request.decision == "UNDER_REVIEW":
        application.status = WorkerApplicationStatus.UNDER_REVIEW
        emit(
            session,
            actor_id=admin.profile.id,
            action="worker_application_under_review",
            entity_type="worker_application",
            entity_id=application.id,
            previous_state=previous.value,
            new_state=application.status.value,
        )
        session.commit()
        session.refresh(application)
        return application

    if request.decision == "REQUEST_INFO":
        application.status = WorkerApplicationStatus.ADDITIONAL_INFORMATION_REQUIRED
        emit(
            session,
            actor_id=admin.profile.id,
            action="worker_application_additional_information",
            entity_type="worker_application",
            entity_id=application.id,
            previous_state=previous.value,
            new_state=application.status.value,
        )
        notify(
            session,
            recipient_id=application.applicant_id,
            kind="worker_application_additional_information",
            title="Additional information requested",
            body=request.note or "The reviewer requested more information.",
            entity_type="worker_application",
            entity_id=application.id,
        )
        session.commit()
        session.refresh(application)
        return application

    if request.decision == "REJECT":
        application.status = WorkerApplicationStatus.REJECTED
        emit(
            session,
            actor_id=admin.profile.id,
            action="worker_application_rejected",
            entity_type="worker_application",
            entity_id=application.id,
            previous_state=previous.value,
            new_state=application.status.value,
        )
        notify(
            session,
            recipient_id=application.applicant_id,
            kind="worker_application_rejected",
            title="Worker application not approved",
            body=request.note or "The application was not approved.",
            entity_type="worker_application",
            entity_id=application.id,
        )
        session.commit()
        session.refresh(application)
        return application

    # APPROVE — grant WORKER through the existing audited, self-change-guarded
    # service, then create the operational profile.
    application.status = WorkerApplicationStatus.APPROVED
    existing_worker = session.scalar(
        select(WorkerProfile).where(WorkerProfile.application_id == application.id)
    )
    if existing_worker is None:
        change_profile_role(
            session,
            actor=admin.profile,
            target_profile_id=application.applicant_id,
            new_role=Role.WORKER,
            reason=request.note or f"Approved worker application {application.id}",
        )
        existing_worker = WorkerProfile(
            profile_id=application.applicant_id,
            application_id=application.id,
            specialization=application.specialization,
            department_id=application.department_id,
            service_area=application.service_area,
            status=WorkerStatus.ACTIVE,
            approved_by=admin.profile.id,
            approved_at=_now(),
        )
        session.add(existing_worker)
        try:
            session.commit()
        except Exception:
            session.rollback()
            change_profile_role(
                session,
                actor=admin.profile,
                target_profile_id=application.applicant_id,
                new_role=Role.CITIZEN,
                reason="Rollback of failed worker approval",
            )
            raise
    else:
        session.commit()
    session.refresh(application)

    emit(
        session,
        actor_id=admin.profile.id,
        action="worker_application_approved",
        entity_type="worker_application",
        entity_id=application.id,
        previous_state=previous.value,
        new_state=application.status.value,
        metadata={"worker_profile_id": existing_worker.id},
    )
    notify(
        session,
        recipient_id=application.applicant_id,
        kind="worker_application_approved",
        title="Worker application approved",
        body="Your worker profile is active. You can access the worker workspace.",
        entity_type="worker_application",
        entity_id=application.id,
    )
    session.commit()
    session.refresh(application)
    return application


def application_counts(session: Session) -> dict[str, int]:
    rows = session.execute(
        select(WorkerApplication.status, func.count())
        .group_by(WorkerApplication.status)
    ).all()
    return {status.value: int(count) for status, count in rows}


