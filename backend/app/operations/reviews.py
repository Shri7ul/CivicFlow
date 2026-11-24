"""Human review and approval workflow for planning simulations."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    DecisionReview,
    DecisionReviewEvent,
    DecisionReviewStatus,
    DecisionSimulation,
    Profile,
    Role,
)


class ReviewError(ValueError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


def serialize_review(session: Session, review: DecisionReview) -> dict:
    submitter = session.get(Profile, review.submitted_by) if review.submitted_by else None
    reviewer = session.get(Profile, review.reviewed_by) if review.reviewed_by else None
    return {
        "id": str(review.id),
        "scenario_id": str(review.scenario_id),
        "simulation_id": str(review.simulation_id) if review.simulation_id else None,
        "title": review.title,
        "status": review.status.value,
        "submitted_by": str(review.submitted_by) if review.submitted_by else None,
        "submitted_by_name": submitter.full_name if submitter else None,
        "reviewed_by": str(review.reviewed_by) if review.reviewed_by else None,
        "reviewed_by_name": reviewer.full_name if reviewer else None,
        "submitted_at": review.submitted_at.isoformat() if review.submitted_at else None,
        "reviewed_at": review.reviewed_at.isoformat() if review.reviewed_at else None,
        "decision_note": review.decision_note,
        "created_at": review.created_at.isoformat(),
        "updated_at": review.updated_at.isoformat(),
        "execution_authorized": False,
        "dispatch_performed": False,
        "reservations_created": False,
    }


def serialize_event(event: DecisionReviewEvent) -> dict:
    return {
        "id": str(event.id),
        "from_status": event.from_status.value if event.from_status else None,
        "to_status": event.to_status.value,
        "actor_id": str(event.actor_id) if event.actor_id else None,
        "comment": event.comment,
        "created_at": event.created_at.isoformat(),
    }


def submit_review(
    session: Session,
    *,
    scenario_id: UUID,
    simulation_id: UUID,
    title: str,
    actor_id: UUID,
    comment: str | None,
) -> DecisionReview:
    simulation = session.get(DecisionSimulation, simulation_id)
    if simulation is None or simulation.scenario_id != scenario_id:
        raise ReviewError(
            "A persisted simulation from this scenario is required.",
            code="invalid_review_simulation",
        )
    active = session.scalar(
        select(DecisionReview).where(
            DecisionReview.scenario_id == scenario_id,
            DecisionReview.simulation_id == simulation_id,
            DecisionReview.status.in_(
                [
                    DecisionReviewStatus.SUBMITTED,
                    DecisionReviewStatus.APPROVED,
                    DecisionReviewStatus.REVISION_REQUESTED,
                ]
            ),
        )
    )
    if active is not None:
        raise ReviewError(
            "This simulation already has an active or approved review.",
            code="review_already_exists",
        )
    review = DecisionReview(
        scenario_id=scenario_id,
        simulation_id=simulation_id,
        status=DecisionReviewStatus.SUBMITTED,
        title=title.strip(),
        submitted_by=actor_id,
        submitted_at=datetime.now(timezone.utc),
    )
    session.add(review)
    try:
        session.flush()
        session.add(
            DecisionReviewEvent(
                review_id=review.id,
                from_status=None,
                to_status=DecisionReviewStatus.SUBMITTED,
                actor_id=actor_id,
                comment=comment,
            )
        )
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ReviewError(
            "A concurrent submission already created an active review for this simulation.",
            code="review_already_exists",
        ) from error
    session.refresh(review)
    return review


def decide_review(
    session: Session,
    review: DecisionReview,
    *,
    decision: DecisionReviewStatus,
    actor: Profile,
    comment: str | None,
) -> DecisionReview:
    if decision not in {
        DecisionReviewStatus.APPROVED,
        DecisionReviewStatus.REJECTED,
        DecisionReviewStatus.REVISION_REQUESTED,
    }:
        raise ReviewError("Unsupported review decision.", code="invalid_review_decision")
    if review.status not in {
        DecisionReviewStatus.SUBMITTED,
        DecisionReviewStatus.REVISION_REQUESTED,
    }:
        raise ReviewError(
            "Only submitted or revision-requested reviews can be decided.",
            code="review_not_actionable",
        )
    if actor.role != Role.ADMIN:
        raise ReviewError("Only an administrator can decide a plan review.", code="forbidden")
    if review.submitted_by == actor.id:
        raise ReviewError(
            "A submitter cannot approve or reject their own plan review.",
            code="self_approval_forbidden",
        )
    previous = review.status
    review.status = decision
    review.reviewed_by = actor.id
    review.reviewed_at = datetime.now(timezone.utc)
    review.decision_note = comment
    session.add(
        DecisionReviewEvent(
            review_id=review.id,
            from_status=previous,
            to_status=decision,
            actor_id=actor.id,
            comment=comment,
        )
    )
    session.commit()
    session.refresh(review)
    return review


def list_review_events(session: Session, review_id: UUID) -> list[DecisionReviewEvent]:
    return list(
        session.scalars(
            select(DecisionReviewEvent)
            .where(DecisionReviewEvent.review_id == review_id)
            .order_by(DecisionReviewEvent.created_at)
        ).all()
    )
