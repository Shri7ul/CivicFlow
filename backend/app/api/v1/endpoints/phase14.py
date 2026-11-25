"""Phase 14 controlled-pilot governance APIs.

All routes are staff-only. Mutating routes are ADMIN-only except field
observation creation/submission and incident creation, which are available to
workers. Reads never change a model, score, review decision or resource.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser, require_admin, require_worker
from app.core.exceptions import AppError
from app.db.session import get_db_session
from app.governance.errors import GovernanceError
from app.models.phase14 import (
    BaselineComparison,
    PilotBoundary,
    PilotDataSource,
    PilotIncident,
    Phase14Attestation,
)
from app.models.pilot import Pilot
from app.phase14 import (
    attestations,
    baselines,
    boundaries,
    datasources,
    incidents,
    observations,
    serialization,
    shutdown,
)
from app.phase14.readiness import assess_phase14_readiness
from app.schemas.phase14 import (
    AttestationCreate,
    BaselineCreate,
    BoundaryCreate,
    BoundaryTransition,
    DataSourceAuthorize,
    DataSourceCreate,
    DataSourceRevoke,
    ObservationCreate,
    ObservationDuplicate,
    ObservationReview,
    ObservationReviewerAssign,
    ObservationSubmit,
    PilotIncidentCreate,
    PilotIncidentResume,
    PilotIncidentTransition,
    ShutdownRequest,
)

router = APIRouter()


def _fail(error: GovernanceError) -> None:
    raise AppError(error.message, status_code=error.status_code, code=error.code)


def _pilot_or_404(session: Session, pilot_id: uuid.UUID) -> Pilot:
    pilot = session.get(Pilot, pilot_id)
    if pilot is None:
        _fail(GovernanceError("Pilot not found", status_code=404, code="pilot_not_found"))
    return pilot


def _boundary_or_404(session: Session, boundary_id: uuid.UUID) -> PilotBoundary:
    row = session.get(PilotBoundary, boundary_id)
    if row is None:
        _fail(GovernanceError("Boundary not found", status_code=404, code="boundary_not_found"))
    return row


def _observation_or_404(session: Session, observation_id: uuid.UUID):
    try:
        return observations.get_observation(session, observation_id)
    except GovernanceError as error:
        _fail(error)


def _source_or_404(session: Session, source_id: uuid.UUID) -> PilotDataSource:
    row = session.get(PilotDataSource, source_id)
    if row is None:
        _fail(GovernanceError("Data source not found", status_code=404, code="source_not_found"))
    return row


def _incident_or_404(session: Session, incident_id: uuid.UUID) -> PilotIncident:
    try:
        return incidents.get_incident(session, incident_id)
    except GovernanceError as error:
        _fail(error)


# ---------------------------------------------------------------------------
# Boundary workflow
# ---------------------------------------------------------------------------


@router.get("/boundaries")
def list_boundaries(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
    geographic_context_key: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    del user
    statement = select(PilotBoundary).order_by(PilotBoundary.created_at.desc())
    if geographic_context_key:
        statement = statement.where(
            PilotBoundary.geographic_context_key == geographic_context_key
        )
    rows = session.scalars(statement.limit(limit)).all()
    return {
        "items": [serialization.serialize_boundary(row) for row in rows],
        "approval_note": "A screening bbox is never an approved pilot boundary.",
    }


@router.post("/boundaries", status_code=201)
def register_boundary(
    payload: BoundaryCreate,
    user: Annotated[AuthenticatedUser, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    try:
        row = boundaries.register_boundary(session, payload, user)
    except GovernanceError as error:
        _fail(error)
    return serialization.serialize_boundary(row, events=boundaries.events_for(session, row.id))


@router.get("/boundaries/{boundary_id}")
def get_boundary(
    boundary_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    del user
    row = _boundary_or_404(session, boundary_id)
    return serialization.serialize_boundary(row, events=boundaries.events_for(session, row.id))


@router.post("/boundaries/{boundary_id}/transition")
def transition_boundary(
    boundary_id: uuid.UUID,
    payload: BoundaryTransition,
    user: Annotated[AuthenticatedUser, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    row = _boundary_or_404(session, boundary_id)
    try:
        row = boundaries.transition_boundary(session, row, payload.action, payload, user)
    except GovernanceError as error:
        _fail(error)
    return serialization.serialize_boundary(row, events=boundaries.events_for(session, row.id))


# ---------------------------------------------------------------------------
# Field observation workflow
# ---------------------------------------------------------------------------


@router.get("/observations")
def list_observations(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
    geographic_context_key: str | None = None,
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    del user
    statement = select(observations.FieldObservation).order_by(
        observations.FieldObservation.created_at.desc()
    )
    if geographic_context_key:
        statement = statement.where(
            observations.FieldObservation.geographic_context_key == geographic_context_key
        )
    if status:
        statement = statement.where(observations.FieldObservation.status == status)
    rows = session.scalars(statement.limit(limit)).all()
    return {
        "items": [serialization.serialize_observation(row) for row in rows],
        "status_counts": observations.status_counts(
            session, context_key=geographic_context_key
        ),
    }


@router.post("/observations", status_code=201)
def create_observation(
    payload: ObservationCreate,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    try:
        row = observations.create_observation(session, payload, user)
    except GovernanceError as error:
        _fail(error)
    return serialization.serialize_observation(row, events=observations.events_for(session, row.id))


@router.get("/observations/{observation_id}")
def get_observation(
    observation_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    del user
    row = _observation_or_404(session, observation_id)
    return serialization.serialize_observation(row, events=observations.events_for(session, row.id))


@router.post("/observations/{observation_id}/submit")
def submit_observation(
    observation_id: uuid.UUID,
    payload: ObservationSubmit,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    row = _observation_or_404(session, observation_id)
    del payload
    try:
        row = observations.submit_observation(session, row, user)
    except GovernanceError as error:
        _fail(error)
    return serialization.serialize_observation(row, events=observations.events_for(session, row.id))


@router.post("/observations/{observation_id}/assign-reviewer")
def assign_reviewer(
    observation_id: uuid.UUID,
    payload: ObservationReviewerAssign,
    user: Annotated[AuthenticatedUser, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    row = _observation_or_404(session, observation_id)
    try:
        row = observations.assign_reviewer(session, row, payload.reviewer_id, user)
    except GovernanceError as error:
        _fail(error)
    return serialization.serialize_observation(row, events=observations.events_for(session, row.id))


@router.post("/observations/{observation_id}/review")
def review_observation(
    observation_id: uuid.UUID,
    payload: ObservationReview,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    row = _observation_or_404(session, observation_id)
    try:
        row = observations.review_observation(session, row, payload, user)
    except GovernanceError as error:
        _fail(error)
    return serialization.serialize_observation(row, events=observations.events_for(session, row.id))


@router.post("/observations/{observation_id}/duplicate")
def mark_duplicate(
    observation_id: uuid.UUID,
    payload: ObservationDuplicate,
    user: Annotated[AuthenticatedUser, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    row = _observation_or_404(session, observation_id)
    try:
        row = observations.mark_duplicate(session, row, payload.duplicate_of_id, user)
    except GovernanceError as error:
        _fail(error)
    return serialization.serialize_observation(row, events=observations.events_for(session, row.id))


@router.post("/observations/{observation_id}/promote-ground-truth")
def promote_ground_truth(
    observation_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    row = _observation_or_404(session, observation_id)
    try:
        result = observations.promote_to_ground_truth(session, row, user)
    except GovernanceError as error:
        _fail(error)
    return {
        "observation": serialization.serialize_observation(
            result["observation"], events=observations.events_for(session, row.id)
        ),
        "ground_truth_record_key": result["ground_truth"].record_key,
        "promotion_note": "An explicit human decision created this ground-truth record.",
    }


# ---------------------------------------------------------------------------
# Data source registration and authorization
# ---------------------------------------------------------------------------


@router.get("/data-sources")
def list_data_sources(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
    geographic_context_key: str | None = None,
) -> dict:
    del user
    statement = select(PilotDataSource).order_by(PilotDataSource.created_at.desc())
    if geographic_context_key:
        statement = statement.where(
            PilotDataSource.geographic_context_key == geographic_context_key
        )
    rows = session.scalars(statement.limit(200)).all()
    return {"items": [serialization.serialize_data_source(row) for row in rows]}


@router.post("/data-sources", status_code=201)
def register_data_source(
    payload: DataSourceCreate,
    user: Annotated[AuthenticatedUser, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    try:
        row = datasources.register_source(session, payload, user)
    except GovernanceError as error:
        _fail(error)
    return serialization.serialize_data_source(row)


@router.post("/data-sources/{source_id}/authorize")
def authorize_data_source(
    source_id: uuid.UUID,
    payload: DataSourceAuthorize,
    user: Annotated[AuthenticatedUser, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    row = _source_or_404(session, source_id)
    try:
        row = datasources.authorize_source(session, row, payload, user)
    except GovernanceError as error:
        _fail(error)
    return serialization.serialize_data_source(row)


@router.post("/data-sources/{source_id}/revoke")
def revoke_data_source(
    source_id: uuid.UUID,
    payload: DataSourceRevoke,
    user: Annotated[AuthenticatedUser, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    row = _source_or_404(session, source_id)
    try:
        row = datasources.revoke_source(session, row, payload.reason, user)
    except GovernanceError as error:
        _fail(error)
    return serialization.serialize_data_source(row)


# ---------------------------------------------------------------------------
# Pilot incidents and processing interlock
# ---------------------------------------------------------------------------


@router.get("/incidents/pilot/{pilot_id}/processing")
def pilot_processing(
    pilot_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    del user
    return incidents.processing_allowed(session, pilot_id)


@router.get("/incidents")
def list_incidents(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
    pilot_id: uuid.UUID | None = None,
) -> dict:
    del user
    statement = select(PilotIncident).order_by(PilotIncident.created_at.desc())
    if pilot_id:
        statement = statement.where(PilotIncident.pilot_id == pilot_id)
    rows = session.scalars(statement.limit(200)).all()
    return {"items": [serialization.serialize_incident(row) for row in rows]}


@router.post("/incidents", status_code=201)
def open_incident(
    payload: PilotIncidentCreate,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    try:
        row = incidents.open_incident(session, payload, user)
    except GovernanceError as error:
        _fail(error)
    return serialization.serialize_incident(row, events=incidents.events_for(session, row.id))


@router.get("/incidents/{incident_id}")
def get_incident(
    incident_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    del user
    row = _incident_or_404(session, incident_id)
    return serialization.serialize_incident(row, events=incidents.events_for(session, row.id))


@router.post("/incidents/{incident_id}/transition")
def transition_incident(
    incident_id: uuid.UUID,
    payload: PilotIncidentTransition,
    user: Annotated[AuthenticatedUser, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    row = _incident_or_404(session, incident_id)
    try:
        row = incidents.transition_incident(session, row, payload, user)
    except GovernanceError as error:
        _fail(error)
    return serialization.serialize_incident(row, events=incidents.events_for(session, row.id))


@router.post("/incidents/{incident_id}/resume-processing")
def resume_incident_processing(
    incident_id: uuid.UUID,
    payload: PilotIncidentResume,
    user: Annotated[AuthenticatedUser, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    row = _incident_or_404(session, incident_id)
    try:
        row = incidents.resume_processing(session, row, payload.note, user)
    except GovernanceError as error:
        _fail(error)
    return serialization.serialize_incident(row, events=incidents.events_for(session, row.id))


# ---------------------------------------------------------------------------
# Baselines, attestations, shutdown and final gate
# ---------------------------------------------------------------------------


@router.get("/baselines")
def list_baselines(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
    geographic_context_key: str | None = None,
) -> dict:
    del user
    statement = select(BaselineComparison).order_by(BaselineComparison.created_at.desc())
    if geographic_context_key:
        statement = statement.where(
            BaselineComparison.geographic_context_key == geographic_context_key
        )
    return {
        "items": [serialization.serialize_baseline(row) for row in session.scalars(statement.limit(200)).all()]
    }


@router.post("/baselines", status_code=201)
def record_baseline(
    payload: BaselineCreate,
    user: Annotated[AuthenticatedUser, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    try:
        row = baselines.record_comparison(session, payload, user)
    except GovernanceError as error:
        _fail(error)
    return serialization.serialize_baseline(row)


@router.get("/attestations")
def list_attestations(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
    category: str | None = None,
) -> dict:
    del user
    statement = select(Phase14Attestation).order_by(Phase14Attestation.created_at.desc())
    if category:
        statement = statement.where(Phase14Attestation.category == category)
    return {
        "items": [serialization.serialize_attestation(row) for row in session.scalars(statement.limit(200)).all()]
    }


@router.post("/attestations", status_code=201)
def create_attestation(
    payload: AttestationCreate,
    user: Annotated[AuthenticatedUser, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    try:
        row = attestations.record_attestation(session, payload, user)
    except GovernanceError as error:
        _fail(error)
    return serialization.serialize_attestation(row)


@router.post("/pilots/{pilot_id}/shutdown")
def shutdown_pilot(
    pilot_id: uuid.UUID,
    payload: ShutdownRequest,
    user: Annotated[AuthenticatedUser, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    pilot = _pilot_or_404(session, pilot_id)
    try:
        row = shutdown.shutdown_pilot(session, pilot, payload.reason, user)
    except GovernanceError as error:
        _fail(error)
    return serialization.serialize_shutdown(row)


@router.get("/pilots/{pilot_id}/shutdown")
def pilot_shutdowns(
    pilot_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    del user
    _pilot_or_404(session, pilot_id)
    return {
        "items": [serialization.serialize_shutdown(row) for row in shutdown.for_pilot(session, pilot_id)]
    }


@router.get("/readiness")
def phase14_readiness(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
    pilot_id: uuid.UUID | None = Query(default=None),
) -> dict:
    del user
    pilot = _pilot_or_404(session, pilot_id) if pilot_id else None
    return assess_phase14_readiness(session, pilot)


@router.get("/model-status")
def dhaka_model_status(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    del user, session
    from app.models.phase14 import DHAKA_MODEL_READINESS_LEVEL

    return {
        "geographic_context_key": "BD-DHAKA",
        "readiness_level": DHAKA_MODEL_READINESS_LEVEL,
        "operationally_available": False,
        "note": (
            "Descriptive classification only. No endpoint in this API promotes "
            "a model, activates a model version or authorizes civic action."
        ),
    }
