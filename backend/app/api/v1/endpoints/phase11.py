"""Phase 11 evidence acquisition, ground-truth and correlation-universe APIs.

Staff-only. No endpoint accepts an arbitrary URL, raw snapshot bytes, actor
identity, status, hash or verification timestamp from the client.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser, require_admin, require_worker
from app.core.exceptions import AppError
from app.db.session import get_db_session
from app.evidence.acquisition import AcquisitionError, acquire_infrastructure_source
from app.evidence.ground_truth import (
    create_record,
    events_for,
    get_record,
    review_record,
    serialize_event,
    serialize_record,
    submit_for_review,
)
from app.evidence.snapshots import get_snapshot, serialize_snapshot, verify_snapshot
from app.evidence.universes import (
    create_universe,
    get_universe,
    serialize_universe,
)
from app.evidence.workspace import build_workspace
from app.governance.errors import GovernanceError
from app.models.enums import (
    EvidenceSnapshotKind,
    EvidenceSnapshotStatus,
    GroundTruthSourceType,
    GroundTruthStatus,
)
from app.models.evidence import (
    CorrelationUniverse,
    EvidenceSnapshot,
    GroundTruthRecord,
)
from app.schemas.evidence import (
    AcquireRequest,
    CorrelationUniverseCreate,
    GroundTruthCreate,
    GroundTruthReview,
    GroundTruthSubmit,
)

router = APIRouter()


def _fail(error: GovernanceError) -> None:
    raise AppError(error.message, status_code=error.status_code, code=error.code)


def _snapshot_or_404(session: Session, snapshot_id: uuid.UUID) -> EvidenceSnapshot:
    try:
        return get_snapshot(session, snapshot_id)
    except GovernanceError as error:
        _fail(error)


def _gt_or_404(session: Session, record_id: uuid.UUID) -> GroundTruthRecord:
    try:
        return get_record(session, record_id)
    except GovernanceError as error:
        _fail(error)


@router.get("/evidence/workspace")
def evidence_workspace(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
    include_context: bool = True,
) -> dict:
    del user
    return build_workspace(session, include_context=include_context)


@router.get("/evidence/snapshots")
def list_snapshots(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
    kind: EvidenceSnapshotKind | None = None,
    status: EvidenceSnapshotStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> dict:
    del user
    statement = select(EvidenceSnapshot).order_by(EvidenceSnapshot.retrieved_at.desc())
    count_statement = select(func.count()).select_from(EvidenceSnapshot)
    if kind is not None:
        statement = statement.where(EvidenceSnapshot.kind == kind)
        count_statement = count_statement.where(EvidenceSnapshot.kind == kind)
    if status is not None:
        statement = statement.where(EvidenceSnapshot.status == status)
        count_statement = count_statement.where(EvidenceSnapshot.status == status)
    total = int(session.scalar(count_statement) or 0)
    rows = session.scalars(statement.limit(limit).offset(offset)).all()
    return {
        "items": [serialize_snapshot(row) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
        "disclaimer": (
            "Snapshots retain acquired bytes and normalized records. Raw bytes are "
            "never returned by the API."
        ),
    }


@router.get("/evidence/snapshots/{snapshot_id}")
def snapshot_detail(
    snapshot_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    del user
    return serialize_snapshot(_snapshot_or_404(session, snapshot_id), detail=True)


@router.post("/evidence/acquire", status_code=201)
def acquire(
    payload: AcquireRequest,
    user: Annotated[AuthenticatedUser, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    try:
        snapshot, created = acquire_infrastructure_source(
            session, payload.source_key, user
        )
    except GovernanceError as error:
        _fail(error)
    except AcquisitionError as error:
        raise AppError(
            error.message, status_code=502, code=error.code
        ) from error
    return {
        "created": created,
        "snapshot": serialize_snapshot(snapshot, detail=True),
        "disclaimer": (
            "Acquisition proves data availability and integrity, not physical "
            "condition, human validation, model activation or dispatch readiness."
        ),
    }


@router.post("/evidence/snapshots/{snapshot_id}/verify")
def verify(
    snapshot_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    snapshot = _snapshot_or_404(session, snapshot_id)
    try:
        verified, created = verify_snapshot(session, snapshot, user)
    except GovernanceError as error:
        _fail(error)
    return {
        "created": created,
        "snapshot": serialize_snapshot(verified, detail=True),
        "disclaimer": (
            "Automated recomputation verifies byte/hash/count integrity. It is not "
            "human review and does not validate physical ground truth."
        ),
    }


@router.get("/evidence/ground-truth")
def list_ground_truth(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
    status: GroundTruthStatus | None = None,
    source_type: GroundTruthSourceType | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> dict:
    del user
    statement = select(GroundTruthRecord).order_by(GroundTruthRecord.created_at.desc())
    count_statement = select(func.count()).select_from(GroundTruthRecord)
    if status is not None:
        statement = statement.where(GroundTruthRecord.status == status)
        count_statement = count_statement.where(GroundTruthRecord.status == status)
    if source_type is not None:
        statement = statement.where(GroundTruthRecord.source_type == source_type)
        count_statement = count_statement.where(
            GroundTruthRecord.source_type == source_type
        )
    total = int(session.scalar(count_statement) or 0)
    rows = session.scalars(statement.limit(limit).offset(offset)).all()
    return {
        "items": [serialize_record(row) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
        "disclaimer": (
            "Includes sensitive assertions. Staff-only. UNVERIFIED and AI_PREDICTION "
            "rows are not physical incidents."
        ),
    }


@router.post("/evidence/ground-truth", status_code=201)
def create_ground_truth(
    payload: GroundTruthCreate,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    try:
        record = create_record(session, payload, user)
    except GovernanceError as error:
        _fail(error)
    return serialize_record(record, detail=True)


@router.get("/evidence/ground-truth/{record_id}")
def ground_truth_detail(
    record_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    del user
    record = _gt_or_404(session, record_id)
    return {
        "record": serialize_record(record, detail=True),
        "events": [serialize_event(item) for item in events_for(session, record.id)],
    }


@router.post("/evidence/ground-truth/{record_id}/submit")
def submit_ground_truth(
    record_id: uuid.UUID,
    payload: GroundTruthSubmit,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    record = _gt_or_404(session, record_id)
    try:
        record = submit_for_review(session, record, payload, user)
    except GovernanceError as error:
        _fail(error)
    return serialize_record(record, detail=True)


@router.post("/evidence/ground-truth/{record_id}/review")
def review_ground_truth(
    record_id: uuid.UUID,
    payload: GroundTruthReview,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    record = _gt_or_404(session, record_id)
    try:
        record = review_record(session, record, payload, user)
    except GovernanceError as error:
        _fail(error)
    return serialize_record(record, detail=True)


@router.get("/evidence/ground-truth/{record_id}/events")
def ground_truth_events(
    record_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    del user
    record = _gt_or_404(session, record_id)
    items = events_for(session, record.id)
    return {
        "items": [serialize_event(item) for item in items],
        "total": len(items),
    }


@router.get("/evidence/correlation/universes")
def list_universes(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> dict:
    del user
    total = int(
        session.scalar(
            select(func.count()).select_from(CorrelationUniverse)
        )
        or 0
    )
    rows = session.scalars(
        select(CorrelationUniverse)
        .order_by(CorrelationUniverse.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return {
        "items": [serialize_universe(row) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/evidence/correlation/universes", status_code=201)
def create_correlation_universe(
    payload: CorrelationUniverseCreate,
    user: Annotated[AuthenticatedUser, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    try:
        universe = create_universe(session, payload, user)
    except GovernanceError as error:
        _fail(error)
    return serialize_universe(universe)


@router.get("/evidence/correlation/universes/{universe_id}")
def correlation_universe_detail(
    universe_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    del user
    try:
        universe = get_universe(session, universe_id)
    except GovernanceError as error:
        _fail(error)
    return serialize_universe(universe)
