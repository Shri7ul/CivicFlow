"""Controlled-pilot lifecycle with explicit, auditable transitions."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser
from app.governance.errors import GovernanceError
from app.governance.readiness import assess_readiness
from app.governance.serialization import serialize_pilot, serialize_transition
from app.models.enums import PilotReviewerRole, PilotStatus, PilotTransitionAction, Role
from app.models.pilot import Pilot, PilotReviewer, PilotTransition
from app.models.profile import Profile


ACTION_RULES: dict[PilotTransitionAction, set[PilotStatus]] = {
    PilotTransitionAction.SUBMIT: {PilotStatus.DRAFT},
    PilotTransitionAction.APPROVE: {PilotStatus.PENDING_APPROVAL},
    PilotTransitionAction.REJECT: {PilotStatus.PENDING_APPROVAL},
    PilotTransitionAction.ACTIVATE: {PilotStatus.APPROVED},
    PilotTransitionAction.PAUSE: {PilotStatus.ACTIVE},
    PilotTransitionAction.RESUME: {PilotStatus.PAUSED},
    PilotTransitionAction.COMPLETE: {PilotStatus.ACTIVE, PilotStatus.PAUSED},
    PilotTransitionAction.ARCHIVE: {
        PilotStatus.DRAFT,
        PilotStatus.COMPLETED,
        PilotStatus.REJECTED,
    },
}

ACTION_TARGET: dict[PilotTransitionAction, PilotStatus] = {
    PilotTransitionAction.SUBMIT: PilotStatus.PENDING_APPROVAL,
    PilotTransitionAction.APPROVE: PilotStatus.APPROVED,
    PilotTransitionAction.REJECT: PilotStatus.REJECTED,
    PilotTransitionAction.ACTIVATE: PilotStatus.ACTIVE,
    PilotTransitionAction.PAUSE: PilotStatus.PAUSED,
    PilotTransitionAction.RESUME: PilotStatus.ACTIVE,
    PilotTransitionAction.COMPLETE: PilotStatus.COMPLETED,
    PilotTransitionAction.ARCHIVE: PilotStatus.ARCHIVED,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _text(value: str | None, *, field: str, required: bool = False) -> str | None:
    cleaned = value.strip() if value else ""
    if required and not cleaned:
        raise GovernanceError(f"{field} is required for this action", code="note_required")
    if len(cleaned) > 4000:
        raise GovernanceError(f"{field} is too long", code="note_too_long")
    return cleaned or None


def get_pilot(session: Session, pilot_id: uuid.UUID) -> Pilot:
    pilot = session.get(Pilot, pilot_id)
    if pilot is None:
        raise GovernanceError("Pilot not found", status_code=404, code="pilot_not_found")
    return pilot


def _require_admin_profile(session: Session, profile_id: uuid.UUID) -> Profile:
    profile = session.get(Profile, profile_id)
    if profile is None or not profile.is_active or profile.role != Role.ADMIN:
        raise GovernanceError(
            "Pilot owners and reviewers must be active administrators",
            code="invalid_pilot_owner",
        )
    return profile


def create_pilot(
    session: Session, payload: object, actor: AuthenticatedUser
) -> Pilot:
    data = payload
    existing = session.scalar(
        select(Pilot.id).where(Pilot.pilot_key == data.pilot_key)
    )
    if existing is not None:
        raise GovernanceError(
            "A pilot with this key already exists",
            status_code=409,
            code="pilot_key_conflict",
        )
    owner_id = data.owner_id or actor.profile.id
    _require_admin_profile(session, owner_id)
    pilot = Pilot(
        pilot_key=data.pilot_key,
        name=data.name,
        description=data.description,
        mode=data.mode,
        region=data.region,
        bbox=data.bbox or [],
        start_date=data.start_date,
        end_date=data.end_date,
        eligible_categories=data.eligible_categories,
        evaluation_protocol=data.evaluation_protocol.strip(),
        operational_restrictions=data.operational_restrictions,
        data_sources=data.data_sources,
        evaluation_criteria=data.evaluation_criteria,
        owner_id=owner_id,
        created_by=actor.profile.id,
        status=PilotStatus.DRAFT,
    )
    session.add(pilot)
    try:
        session.flush()
    except IntegrityError as error:
        session.rollback()
        raise GovernanceError(
            "Pilot could not be created from the supplied fields",
            status_code=409,
            code="pilot_conflict",
        ) from error
    session.add(
        PilotTransition(
            pilot_id=pilot.id,
            from_status=None,
            to_status=PilotStatus.DRAFT,
            action=PilotTransitionAction.CREATE,
            actor_id=actor.profile.id,
            actor_email=actor.email,
            note="Pilot created in DRAFT. Creation is not approval or activation.",
        )
    )
    session.commit()
    return pilot


def add_reviewer(
    session: Session,
    pilot: Pilot,
    profile_id: uuid.UUID,
    role: PilotReviewerRole,
    actor: AuthenticatedUser,
) -> PilotReviewer:
    if pilot.status in {PilotStatus.ARCHIVED, PilotStatus.REJECTED}:
        raise GovernanceError(
            "Reviewers cannot be added to an archived or rejected pilot",
            status_code=409,
            code="pilot_closed",
        )
    profile = _require_admin_profile(session, profile_id)
    existing = session.scalar(
        select(PilotReviewer.id).where(
            PilotReviewer.pilot_id == pilot.id,
            PilotReviewer.profile_id == profile.id,
        )
    )
    if existing is not None:
        raise GovernanceError(
            "This profile is already assigned to the pilot",
            status_code=409,
            code="reviewer_conflict",
        )
    reviewer = PilotReviewer(
        pilot_id=pilot.id,
        profile_id=profile.id,
        role=role,
        added_by=actor.profile.id,
    )
    session.add(reviewer)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise GovernanceError(
            "Reviewer assignment conflicted with an existing row",
            status_code=409,
            code="reviewer_conflict",
        ) from error
    return reviewer


def reviewer_payload(session: Session, pilot_id: uuid.UUID) -> list[dict]:
    rows = session.execute(
        select(PilotReviewer, Profile)
        .join(Profile, Profile.id == PilotReviewer.profile_id)
        .where(PilotReviewer.pilot_id == pilot_id)
        .order_by(PilotReviewer.created_at)
    ).all()
    return [
        {
            "id": str(reviewer.id),
            "profile_id": str(reviewer.profile_id),
            "full_name": profile.full_name,
            "role": reviewer.role.value,
            "added_by": str(reviewer.added_by) if reviewer.added_by else None,
            "created_at": reviewer.created_at.isoformat(),
        }
        for reviewer, profile in rows
    ]


def reviewer_ids(session: Session, pilot_id: uuid.UUID) -> set[uuid.UUID]:
    return set(
        session.scalars(
            select(PilotReviewer.profile_id).where(PilotReviewer.pilot_id == pilot_id)
        ).all()
    )


def history(session: Session, pilot_id: uuid.UUID) -> list[dict]:
    rows = session.scalars(
        select(PilotTransition)
        .where(PilotTransition.pilot_id == pilot_id)
        .order_by(PilotTransition.created_at, PilotTransition.id)
    ).all()
    return [serialize_transition(event) for event in rows]


def transition(
    session: Session,
    pilot: Pilot,
    action: PilotTransitionAction,
    actor: AuthenticatedUser,
    note: str | None,
) -> Pilot:
    session.refresh(pilot, with_for_update=True)
    allowed = ACTION_RULES[action]
    if pilot.status not in allowed:
        raise GovernanceError(
            f"Action {action.value} is not allowed from {pilot.status.value}",
            status_code=409,
            code="invalid_pilot_transition",
        )
    clean_note = _text(note, field="note")

    if action in {PilotTransitionAction.REJECT, PilotTransitionAction.PAUSE}:
        clean_note = _text(note, field="reason", required=True)
    if action == PilotTransitionAction.APPROVE:
        if actor.profile.id in {pilot.created_by, pilot.owner_id}:
            raise GovernanceError(
                "The pilot creator or owner cannot approve the same pilot",
                status_code=403,
                code="separation_of_duties",
            )
        reviewers = reviewer_ids(session, pilot.id)
        if not reviewers:
            raise GovernanceError(
                "At least one reviewer must be assigned before approval",
                status_code=409,
                code="reviewer_required",
            )
        if len(pilot.evaluation_criteria or []) == 0 or not pilot.evaluation_protocol:
            raise GovernanceError(
                "Evaluation protocol and criteria must be complete before approval",
                status_code=409,
                code="evaluation_plan_incomplete",
            )
    if action in {PilotTransitionAction.ACTIVATE, PilotTransitionAction.RESUME}:
        if action == PilotTransitionAction.ACTIVATE and actor.profile.id == pilot.approved_by:
            raise GovernanceError(
                "The approving administrator cannot also activate the pilot",
                status_code=403,
                code="separation_of_duties",
            )
        now = _now()
        if now > _aware(pilot.end_date):
            raise GovernanceError(
                "The pilot evaluation window has ended",
                status_code=409,
                code="pilot_window_expired",
            )
        report = assess_readiness(session, pilot)
        if not report["ready_for_activation"]:
            raise GovernanceError(
                "Readiness gates are not met: "
                + "; ".join(report["activation_blockers"][:6]),
                status_code=409,
                code="readiness_not_met",
            )
        pilot.activation_readiness = report

    from_status = pilot.status
    target = ACTION_TARGET[action]
    now = _now()
    if action == PilotTransitionAction.APPROVE:
        pilot.approved_by = actor.profile.id
        pilot.approved_at = now
    elif action == PilotTransitionAction.REJECT:
        pilot.rejection_reason = clean_note
    elif action == PilotTransitionAction.ACTIVATE:
        pilot.activated_by = actor.profile.id
        pilot.activated_at = now
    elif action == PilotTransitionAction.PAUSE:
        pilot.paused_at = now
        pilot.paused_by = actor.profile.id
        pilot.pause_reason = clean_note
    elif action == PilotTransitionAction.RESUME:
        pilot.paused_at = None
        pilot.paused_by = None
        pilot.pause_reason = None
    elif action == PilotTransitionAction.COMPLETE:
        pilot.completed_at = now
    elif action == PilotTransitionAction.ARCHIVE:
        pilot.archived_at = now

    pilot.status = target
    session.add(
        PilotTransition(
            pilot_id=pilot.id,
            from_status=from_status,
            to_status=target,
            action=action,
            actor_id=actor.profile.id,
            actor_email=actor.email,
            note=clean_note,
        )
    )
    session.commit()
    return pilot


def pilot_summary(session: Session, pilot: Pilot) -> dict:
    reviewer_count = session.scalar(
        select(func.count())
        .select_from(PilotReviewer)
        .where(PilotReviewer.pilot_id == pilot.id)
    )
    payload = serialize_pilot(
        pilot, reviewers=reviewer_payload(session, pilot.id)
    )
    payload["reviewer_count"] = int(reviewer_count or 0)
    payload["history"] = history(session, pilot.id)
    payload["allowed_actions"] = [
        action.value
        for action, states in ACTION_RULES.items()
        if pilot.status in states
    ]
    return payload
