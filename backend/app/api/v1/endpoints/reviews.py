"""Planning review and approval APIs. Approval never authorizes execution."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser, require_admin, require_worker
from app.core.exceptions import AppError
from app.db.session import get_db_session
from app.models import DecisionReview, DecisionReviewStatus
from app.operations.reviews import (
    ReviewError,
    decide_review,
    list_review_events,
    serialize_event,
    serialize_review,
    submit_review,
)
from app.schemas.operations import ReviewCreate, ReviewDecision, ReviewResponse

router = APIRouter()


def _review_or_404(
    session: Session, review_id: uuid.UUID, *, lock: bool = False
) -> DecisionReview:
    review = session.get(DecisionReview, review_id, with_for_update=lock)
    if review is None:
        raise AppError("Review not found.", status_code=404, code="review_not_found")
    return review


@router.post(
    "/scenarios/{scenario_id}/reviews",
    response_model=ReviewResponse,
    status_code=201,
)
def submit(
    scenario_id: uuid.UUID,
    payload: ReviewCreate,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    try:
        review = submit_review(
            session,
            scenario_id=scenario_id,
            simulation_id=payload.simulation_id,
            title=payload.title,
            actor_id=user.profile.id,
            comment=payload.comment,
        )
    except ReviewError as error:
        raise AppError(str(error), status_code=409, code=error.code) from error
    return serialize_review(session, review)


@router.get(
    "/scenarios/{scenario_id}/reviews",
    response_model=list[ReviewResponse],
)
def list_scenario_reviews(
    scenario_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> list[dict]:
    del user
    reviews = session.scalars(
        select(DecisionReview)
        .where(DecisionReview.scenario_id == scenario_id)
        .order_by(DecisionReview.created_at.desc())
    ).all()
    return [serialize_review(session, review) for review in reviews]


@router.get("/reviews/pending")
def pending_reviews(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> list[dict]:
    del user
    reviews = session.scalars(
        select(DecisionReview)
        .where(
            DecisionReview.status.in_(
                [DecisionReviewStatus.SUBMITTED, DecisionReviewStatus.REVISION_REQUESTED]
            )
        )
        .order_by(DecisionReview.submitted_at.asc())
    ).all()
    return [serialize_review(session, review) for review in reviews]


@router.get("/reviews/{review_id}")
def get_review(
    review_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    del user
    review = _review_or_404(session, review_id)
    return {
        "review": serialize_review(session, review),
        "events": [serialize_event(event) for event in list_review_events(session, review.id)],
        "execution_authorized": False,
        "dispatch_performed": False,
        "reservations_created": False,
        "limitations": [
            "Approval records a human planning decision only.",
            "No dispatch, assignment, reservation, or incident mutation occurs.",
        ],
    }


@router.post("/reviews/{review_id}/decision", response_model=ReviewResponse)
def decide(
    review_id: uuid.UUID,
    payload: ReviewDecision,
    user: Annotated[AuthenticatedUser, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    review = _review_or_404(session, review_id, lock=True)
    try:
        review = decide_review(
            session,
            review,
            decision=payload.decision,
            actor=user.profile,
            comment=payload.comment,
        )
    except ReviewError as error:
        status = 403 if error.code == "forbidden" else 409
        raise AppError(str(error), status_code=status, code=error.code) from error
    return serialize_review(session, review)
