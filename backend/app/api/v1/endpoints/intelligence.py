"""Incident intelligence and relationship review endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser, require_active_user, require_worker
from app.db.session import get_db_session
from app.schemas.intelligence import (
    IncidentIntelligenceResponse,
    RelationshipResponse,
    RelationshipReviewRequest,
)
from app.services.intelligence import (
    build_intelligence,
    list_relationships,
    review_relationship,
)

router = APIRouter()


@router.get(
    "/{incident_id}/intelligence",
    response_model=IncidentIntelligenceResponse,
    summary="Explainable related incidents, infrastructure, and impact context",
)
def incident_intelligence(
    incident_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_active_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> IncidentIntelligenceResponse:
    return build_intelligence(session, user=user, incident_id=incident_id)


@router.get(
    "/{incident_id}/relationships",
    response_model=list[RelationshipResponse],
    summary="Reviewable persisted relationships for a visible incident",
)
def incident_relationships(
    incident_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_active_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> list[RelationshipResponse]:
    return list_relationships(session, user=user, incident_id=incident_id)


@router.post(
    "/{incident_id}/relationships",
    response_model=RelationshipResponse,
    summary="Confirm or dismiss an incident relationship (WORKER/ADMIN)",
)
def review_incident_relationship(
    incident_id: uuid.UUID,
    payload: RelationshipReviewRequest,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> RelationshipResponse:
    return review_relationship(
        session,
        user=user,
        incident_id=incident_id,
        other_incident_id=payload.other_incident_id,
        relationship_type=payload.relationship_type,
        status=payload.status,
        confidence=payload.confidence,
        signals=payload.signals,
        note=payload.note,
    )
