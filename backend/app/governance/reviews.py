"""Human-in-the-loop review of persisted risk cells.

The service never updates a risk score, factor, evidence row, or model run.
Only the review case status and a new append-only event are written.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser
from app.governance.errors import GovernanceError
from app.models.enums import PilotStatus, RiskReviewStatus, Role
from app.models.pilot import Pilot, PilotReviewer, RiskReviewCase, RiskReviewEvent
from app.models.profile import Profile
from app.models.risk import RiskCellSnapshot, RiskModelRun


CASE_TRANSITIONS: dict[RiskReviewStatus, set[RiskReviewStatus]] = {
    RiskReviewStatus.UNREVIEWED: {
        RiskReviewStatus.IN_REVIEW,
        RiskReviewStatus.ACCEPTED,
        RiskReviewStatus.REJECTED,
        RiskReviewStatus.NEEDS_INVESTIGATION,
        RiskReviewStatus.NEEDS_MORE_DATA,
    },
    RiskReviewStatus.IN_REVIEW: {
        RiskReviewStatus.ACCEPTED,
        RiskReviewStatus.REJECTED,
        RiskReviewStatus.NEEDS_INVESTIGATION,
        RiskReviewStatus.NEEDS_MORE_DATA,
    },
    RiskReviewStatus.NEEDS_INVESTIGATION: {RiskReviewStatus.IN_REVIEW},
    RiskReviewStatus.NEEDS_MORE_DATA: {RiskReviewStatus.IN_REVIEW},
    RiskReviewStatus.ACCEPTED: {RiskReviewStatus.IN_REVIEW},
    RiskReviewStatus.REJECTED: {RiskReviewStatus.IN_REVIEW},
}

PILOT_REVIEW_STATUSES = {
    PilotStatus.APPROVED,
    PilotStatus.ACTIVE,
    PilotStatus.PAUSED,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_case(session: Session, case_id: uuid.UUID) -> RiskReviewCase:
    case = session.get(RiskReviewCase, case_id)
    if case is None:
        raise GovernanceError(
            "Review case not found", status_code=404, code="review_case_not_found"
        )
    return case


def _active_staff(session: Session, profile_id: uuid.UUID) -> Profile:
    profile = session.get(Profile, profile_id)
    if (
        profile is None
        or not profile.is_active
        or profile.role not in {Role.WORKER, Role.ADMIN}
    ):
        raise GovernanceError(
            "Reviewers must be active staff profiles",
            code="invalid_reviewer",
        )
    return profile


def create_case(
    session: Session,
    run_id: uuid.UUID,
    cell_id: uuid.UUID,
    pilot_id: uuid.UUID | None,
    assigned_reviewer_id: uuid.UUID | None,
    actor: AuthenticatedUser,
) -> RiskReviewCase:
    run = session.get(RiskModelRun, run_id)
    cell = session.get(RiskCellSnapshot, cell_id)
    if run is None or cell is None:
        raise GovernanceError(
            "Risk run or cell not found",
            status_code=404,
            code="risk_evidence_not_found",
        )
    if cell.run_id != run.id:
        raise GovernanceError(
            "The selected risk cell does not belong to the selected run",
            code="risk_cell_run_mismatch",
        )
    pilot = None
    if pilot_id is not None:
        pilot = session.get(Pilot, pilot_id)
        if pilot is None:
            raise GovernanceError(
                "Pilot not found", status_code=404, code="pilot_not_found"
            )
        if pilot.status not in PILOT_REVIEW_STATUSES:
            raise GovernanceError(
                "Reviews can only be linked to an approved, active or paused pilot",
                status_code=409,
                code="pilot_not_reviewable",
            )
    if assigned_reviewer_id is not None:
        _active_staff(session, assigned_reviewer_id)
        if pilot is not None:
            pilot_reviewers = set(
                session.scalars(
                    select(PilotReviewer.profile_id).where(
                        PilotReviewer.pilot_id == pilot.id
                    )
                ).all()
            )
            if pilot_reviewers and assigned_reviewer_id not in pilot_reviewers:
                raise GovernanceError(
                    "The assigned reviewer is not assigned to this pilot",
                    code="reviewer_not_on_pilot",
                )
    existing = session.scalar(
        select(RiskReviewCase).where(
            RiskReviewCase.run_id == run.id,
            RiskReviewCase.cell_id == cell.id,
        )
    )
    if existing is not None:
        raise GovernanceError(
            f"A review case already exists for this cell ({existing.id})",
            status_code=409,
            code="review_case_exists",
        )
    case = RiskReviewCase(
        run_id=run.id,
        cell_id=cell.id,
        pilot_id=pilot.id if pilot else None,
        assigned_reviewer_id=assigned_reviewer_id,
        created_by=actor.profile.id,
        status=RiskReviewStatus.UNREVIEWED,
    )
    session.add(case)
    session.flush()
    session.add(
        RiskReviewEvent(
            case_id=case.id,
            from_status=None,
            to_status=RiskReviewStatus.UNREVIEWED,
            actor_id=actor.profile.id,
            actor_email=actor.email,
            note="Review case created. This is not a hazard verification.",
        )
    )
    session.commit()
    return case


def decide(
    session: Session,
    case: RiskReviewCase,
    target: RiskReviewStatus,
    note: str | None,
    requested_evidence: str | None,
    actor: AuthenticatedUser,
) -> RiskReviewCase:
    session.refresh(case, with_for_update=True)
    allowed = CASE_TRANSITIONS[case.status]
    if target not in allowed:
        raise GovernanceError(
            f"Review status cannot move from {case.status.value} to {target.value}",
            status_code=409,
            code="invalid_review_transition",
        )
    if case.assigned_reviewer_id is not None:
        if actor.profile.id != case.assigned_reviewer_id and actor.profile.role != Role.ADMIN:
            raise GovernanceError(
                "Only the assigned reviewer or an administrator may decide this case",
                status_code=403,
                code="reviewer_not_assigned",
            )
    if case.pilot_id is not None:
        pilot_reviewers = set(
            session.scalars(
                select(PilotReviewer.profile_id).where(
                    PilotReviewer.pilot_id == case.pilot_id
                )
            ).all()
        )
        if (
            pilot_reviewers
            and actor.profile.id not in pilot_reviewers
            and actor.profile.role != Role.ADMIN
        ):
            raise GovernanceError(
                "Reviewer is not assigned to the linked pilot",
                status_code=403,
                code="reviewer_not_on_pilot",
            )
    clean_note = note.strip() if note else None
    clean_requested = requested_evidence.strip() if requested_evidence else None
    if target in {
        RiskReviewStatus.ACCEPTED,
        RiskReviewStatus.REJECTED,
        RiskReviewStatus.NEEDS_INVESTIGATION,
        RiskReviewStatus.NEEDS_MORE_DATA,
    } and not clean_note:
        raise GovernanceError(
            "A reviewer note is required for this decision",
            code="review_note_required",
        )
    if target == RiskReviewStatus.NEEDS_MORE_DATA and not clean_requested:
        raise GovernanceError(
            "requested_evidence is required for NEEDS_MORE_DATA",
            code="requested_evidence_required",
        )
    previous = case.status
    case.status = target
    case.last_decision_at = _now()
    session.add(
        RiskReviewEvent(
            case_id=case.id,
            from_status=previous,
            to_status=target,
            actor_id=actor.profile.id,
            actor_email=actor.email,
            note=clean_note,
            requested_evidence=clean_requested,
        )
    )
    session.commit()
    return case


def events_for(session: Session, case_id: uuid.UUID) -> list[RiskReviewEvent]:
    return list(
        session.scalars(
            select(RiskReviewEvent)
            .where(RiskReviewEvent.case_id == case_id)
            .order_by(RiskReviewEvent.created_at, RiskReviewEvent.id)
        ).all()
    )
