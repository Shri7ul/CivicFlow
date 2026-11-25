"""Phase 10 controlled-pilot, review, readiness and traceability APIs.

All routes are staff-only. Reads require WORKER; most mutating governance
routes require ADMIN, with review-case creation, review decisions and
correlation-review decisions available to WORKER by design. Reads never change
a model, score, review decision, or operational resource.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser, require_admin, require_worker
from app.core.exceptions import AppError
from app.db.session import get_db_session
from app.governance.correlation import (
    candidates_payload,
    create_candidate,
    get_candidate,
    metrics_for_universe,
    review_candidate,
    review_filter,
    reviews_by_candidate,
)
from app.governance.errors import GovernanceError
from app.governance.infrastructure import (
    coverage as infrastructure_coverage,
)
from app.governance.infrastructure import (
    create_source,
    decide_validation,
    events_for as source_events,
    get_source,
)
from app.governance.pilots import (
    add_reviewer,
    create_pilot,
    get_pilot,
    history,
    pilot_summary,
    reviewer_payload,
    transition,
)
from app.governance.readiness import assess_readiness
from app.governance.reviews import (
    create_case,
    decide,
    events_for as review_events,
    get_case,
)
from app.governance.serialization import (
    iso,
    serialize_correlation_candidate,
    serialize_evidence,
    serialize_pilot,
    serialize_review_case,
    serialize_source,
)
from app.governance.simulation import build_simulation_audit
from app.governance.traceability import build_trace, get_run, list_runs
from app.models.enums import (
    CorrelationDecision,
    InfrastructureValidationStatus,
    PilotStatus,
    ReadinessStatus,
    RiskReviewStatus,
)
from app.models.incident import Incident
from app.models.pilot import (
    CorrelationCandidate,
    InfrastructureSource,
    Pilot,
    PilotReviewer,
    ReadinessEvidence,
    RiskReviewCase,
    RiskReviewEvent,
)
from app.models.risk import RiskCellSnapshot, RiskModelRun
from app.schemas.pilot import (
    CorrelationCandidateCreate,
    CorrelationReviewCreate,
    InfrastructureSourceCreate,
    InfrastructureValidationRequest,
    PilotCreate,
    PilotReviewerCreate,
    PilotTransitionRequest,
    ReadinessEvidenceCreate,
    RiskReviewCaseCreate,
    RiskReviewDecision,
)

router = APIRouter()


def _fail(error: GovernanceError) -> None:
    raise AppError(error.message, status_code=error.status_code, code=error.code)


def _pilot_or_404(session: Session, pilot_id: uuid.UUID) -> Pilot:
    try:
        return get_pilot(session, pilot_id)
    except GovernanceError as error:
        _fail(error)


def _review_or_404(session: Session, case_id: uuid.UUID) -> RiskReviewCase:
    try:
        return get_case(session, case_id)
    except GovernanceError as error:
        _fail(error)


def _source_or_404(session: Session, source_id: uuid.UUID) -> InfrastructureSource:
    try:
        return get_source(session, source_id)
    except GovernanceError as error:
        _fail(error)


@router.get("/pilots")
def list_pilots(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
    status: PilotStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> dict:
    del user
    statement = select(Pilot).order_by(Pilot.created_at.desc())
    count_statement = select(func.count()).select_from(Pilot)
    if status is not None:
        statement = statement.where(Pilot.status == status)
        count_statement = count_statement.where(Pilot.status == status)
    total = int(session.scalar(count_statement) or 0)
    pilots = session.scalars(statement.limit(limit).offset(offset)).all()
    reviewer_counts = dict(
        session.execute(
            select(PilotReviewer.pilot_id, func.count(PilotReviewer.id))
            .where(PilotReviewer.pilot_id.in_([item.id for item in pilots]))
            .group_by(PilotReviewer.pilot_id)
        ).all()
    ) if pilots else {}
    return {
        "items": [
            {
                **serialize_pilot(pilot),
                "reviewer_count": int(reviewer_counts.get(pilot.id, 0)),
            }
            for pilot in pilots
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
        "disclaimer": (
            "A pilot is a controlled evaluation plan, never an operational order."
        ),
    }


@router.post("/pilots", status_code=201)
def create(
    payload: PilotCreate,
    user: Annotated[AuthenticatedUser, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    try:
        pilot = create_pilot(session, payload, user)
    except GovernanceError as error:
        _fail(error)
    return pilot_summary(session, pilot)


@router.get("/pilots/{pilot_id}")
def get(
    pilot_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    del user
    pilot = _pilot_or_404(session, pilot_id)
    return pilot_summary(session, pilot)


@router.post("/pilots/{pilot_id}/reviewers", status_code=201)
def add_pilot_reviewer(
    pilot_id: uuid.UUID,
    payload: PilotReviewerCreate,
    user: Annotated[AuthenticatedUser, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    pilot = _pilot_or_404(session, pilot_id)
    try:
        add_reviewer(session, pilot, payload.profile_id, payload.role, user)
    except GovernanceError as error:
        _fail(error)
    return {"items": reviewer_payload(session, pilot.id)}


@router.post("/pilots/{pilot_id}/transition")
def transition_pilot(
    pilot_id: uuid.UUID,
    payload: PilotTransitionRequest,
    user: Annotated[AuthenticatedUser, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    pilot = _pilot_or_404(session, pilot_id)
    try:
        pilot = transition(session, pilot, payload.action, user, payload.note)
    except GovernanceError as error:
        _fail(error)
    return pilot_summary(session, pilot)


@router.get("/pilots/{pilot_id}/history")
def pilot_history(
    pilot_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    del user
    pilot = _pilot_or_404(session, pilot_id)
    return {"pilot_id": str(pilot.id), "items": history(session, pilot.id)}


@router.get("/pilots/{pilot_id}/readiness")
def pilot_readiness(
    pilot_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    del user
    pilot = _pilot_or_404(session, pilot_id)
    return assess_readiness(session, pilot)


@router.get("/readiness")
def readiness(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    del user
    return assess_readiness(session)


@router.get("/readiness/evidence")
def list_readiness_evidence(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
    category: str | None = None,
) -> dict:
    del user
    statement = select(ReadinessEvidence).order_by(
        ReadinessEvidence.assessed_at.desc()
    )
    if category:
        statement = statement.where(ReadinessEvidence.category == category)
    rows = session.scalars(statement.limit(100)).all()
    return {"items": [serialize_evidence(row) for row in rows]}


@router.post("/readiness/evidence", status_code=201)
def create_readiness_evidence(
    payload: ReadinessEvidenceCreate,
    user: Annotated[AuthenticatedUser, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    from app.models.pilot import ReadinessEvidenceEvent

    existing = session.scalar(
        select(ReadinessEvidence).where(
            ReadinessEvidence.category == payload.category,
            ReadinessEvidence.criterion_key == payload.criterion_key,
        )
    )
    from_status = existing.status if existing else None
    if existing is None:
        existing = ReadinessEvidence(
            category=payload.category,
            criterion_key=payload.criterion_key,
            status=payload.status,
            evidence=payload.evidence.strip(),
            evidence_refs=payload.evidence_refs,
            blocking=payload.blocking,
            owner_id=payload.owner_id,
            assessed_by=user.profile.id,
        )
        session.add(existing)
        session.flush()
    else:
        existing.status = payload.status
        existing.evidence = payload.evidence.strip()
        existing.evidence_refs = payload.evidence_refs
        existing.blocking = payload.blocking
        existing.owner_id = payload.owner_id
        existing.assessed_by = user.profile.id
        from datetime import datetime, timezone

        existing.assessed_at = datetime.now(timezone.utc)
    session.add(
        ReadinessEvidenceEvent(
            evidence_id=existing.id,
            from_status=from_status,
            to_status=payload.status,
            actor_id=user.profile.id,
            actor_email=user.email,
            note=payload.note,
        )
    )
    session.commit()
    return serialize_evidence(existing)


@router.get("/reviews")
def list_reviews(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
    status: RiskReviewStatus | None = None,
    pilot_id: uuid.UUID | None = None,
    run_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> dict:
    del user
    statement = select(RiskReviewCase).order_by(RiskReviewCase.updated_at.desc())
    count_statement = select(func.count()).select_from(RiskReviewCase)
    for clause in (
        RiskReviewCase.status == status if status is not None else None,
        RiskReviewCase.pilot_id == pilot_id if pilot_id is not None else None,
        RiskReviewCase.run_id == run_id if run_id is not None else None,
    ):
        if clause is not None:
            statement = statement.where(clause)
            count_statement = count_statement.where(clause)
    total = int(session.scalar(count_statement) or 0)
    cases = session.scalars(statement.limit(limit).offset(offset)).all()
    return {
        "items": _case_payloads(session, cases),
        "total": total,
        "limit": limit,
        "offset": offset,
        "disclaimer": (
            "Review status is a human judgment about a model output; it is not "
            "a verified hazard and does not change the risk score."
        ),
    }


def _case_payloads(session: Session, cases: list[RiskReviewCase]) -> list[dict]:
    if not cases:
        return []
    run_ids = {case.run_id for case in cases}
    cell_ids = {case.cell_id for case in cases}
    pilot_ids = {case.pilot_id for case in cases if case.pilot_id}
    runs = {
        item.id: item
        for item in session.scalars(
            select(RiskModelRun).where(RiskModelRun.id.in_(run_ids))
        ).all()
    }
    cells = {
        item.id: item
        for item in session.scalars(
            select(RiskCellSnapshot).where(RiskCellSnapshot.id.in_(cell_ids))
        ).all()
    }
    pilots = {
        item.id: item
        for item in session.scalars(
            select(Pilot).where(Pilot.id.in_(pilot_ids))
        ).all()
    } if pilot_ids else {}
    events: dict[uuid.UUID, list[RiskReviewEvent]] = {}
    for event in session.scalars(
        select(RiskReviewEvent)
        .where(RiskReviewEvent.case_id.in_([case.id for case in cases]))
        .order_by(RiskReviewEvent.created_at)
    ).all():
        events.setdefault(event.case_id, []).append(event)
    return [
        serialize_review_case(
            case,
            run=runs.get(case.run_id),
            cell=cells.get(case.cell_id),
            pilot=pilots.get(case.pilot_id) if case.pilot_id else None,
            events=events.get(case.id, []),
        )
        for case in cases
    ]


@router.post("/reviews", status_code=201)
def create_review_case(
    payload: RiskReviewCaseCreate,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    try:
        case = create_case(
            session,
            payload.run_id,
            payload.cell_id,
            payload.pilot_id,
            payload.assigned_reviewer_id,
            user,
        )
    except GovernanceError as error:
        _fail(error)
    return _case_payloads(session, [case])[0]


@router.get("/reviews/{case_id}")
def get_review(
    case_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    del user
    case = _review_or_404(session, case_id)
    return _case_payloads(session, [case])[0]


@router.get("/reviews/{case_id}/events")
def get_review_events(
    case_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    del user
    case = _review_or_404(session, case_id)
    return {
        "case_id": str(case.id),
        "items": [
            {
                "id": str(event.id),
                "from_status": event.from_status.value if event.from_status else None,
                "to_status": event.to_status.value,
                "actor_id": str(event.actor_id) if event.actor_id else None,
                "actor_email": event.actor_email,
                "note": event.note,
                "requested_evidence": event.requested_evidence,
                "created_at": iso(event.created_at),
            }
            for event in review_events(session, case.id)
        ],
    }


@router.post("/reviews/{case_id}/decisions")
def review_decision(
    case_id: uuid.UUID,
    payload: RiskReviewDecision,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    case = _review_or_404(session, case_id)
    try:
        case = decide(
            session,
            case,
            payload.status,
            payload.note,
            payload.requested_evidence,
            user,
        )
    except GovernanceError as error:
        _fail(error)
    return _case_payloads(session, [case])[0]


@router.get("/correlation/candidates")
def list_candidates(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
    universe_key: str | None = None,
    reviewed: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> dict:
    del user
    statement = select(CorrelationCandidate).order_by(
        CorrelationCandidate.created_at.desc()
    )
    count_statement = select(func.count()).select_from(CorrelationCandidate)
    if universe_key:
        statement = statement.where(CorrelationCandidate.universe_key == universe_key)
        count_statement = count_statement.where(
            CorrelationCandidate.universe_key == universe_key
        )
    if reviewed is not None:
        statement = statement.where(review_filter(reviewed))
        count_statement = count_statement.where(review_filter(reviewed))
    total = int(session.scalar(count_statement) or 0)
    candidates = session.scalars(statement.limit(limit).offset(offset)).all()
    incident_ids = set()
    for candidate in candidates:
        incident_ids.add(candidate.source_incident_id)
        incident_ids.add(candidate.target_incident_id)
    incidents = {
        item.id: item
        for item in session.scalars(
            select(Incident).where(Incident.id.in_(incident_ids))
        ).all()
    } if incident_ids else {}
    grouped = reviews_by_candidate(session, [item.id for item in candidates])
    return {
        "items": candidates_payload(session, candidates, incidents, grouped),
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/correlation/candidates", status_code=201)
def create_correlation_candidate(
    payload: CorrelationCandidateCreate,
    user: Annotated[AuthenticatedUser, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    try:
        candidate = create_candidate(
            session,
            payload.source_incident_id,
            payload.target_incident_id,
            payload.similarity_score,
            payload.method,
            payload.method_version,
            payload.universe_key,
            payload.universe_reference_complete,
            payload.reference_universe_size,
            payload.reference_note,
            payload.synthetic_fixture,
            payload.generated_at,
            user,
        )
    except GovernanceError as error:
        _fail(error)
    incident_ids = {candidate.source_incident_id, candidate.target_incident_id}
    incidents = {
        item.id: item
        for item in session.scalars(
            select(Incident).where(Incident.id.in_(incident_ids))
        ).all()
    }
    return serialize_correlation_candidate(
        candidate,
        source=incidents.get(candidate.source_incident_id),
        target=incidents.get(candidate.target_incident_id),
        reviews=[],
    )


@router.post("/correlation/candidates/{candidate_id}/reviews", status_code=201)
def add_correlation_review(
    candidate_id: uuid.UUID,
    payload: CorrelationReviewCreate,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    try:
        candidate = get_candidate(session, candidate_id)
        review = review_candidate(
            session,
            candidate,
            payload.decision,
            payload.note,
            payload.explanation,
            user,
        )
    except GovernanceError as error:
        _fail(error)
    return {
        "id": str(review.id),
        "candidate_id": str(candidate.id),
        "decision": review.decision.value,
        "reviewer_id": str(review.reviewer_id) if review.reviewer_id else None,
        "reviewer_email": review.reviewer_email,
        "created_at": iso(review.created_at),
        "disclaimer": "This label is a human judgment, not confirmed ground truth.",
    }


@router.get("/correlation/metrics")
def correlation_metrics(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
    universe_key: str = Query(min_length=2, max_length=80),
) -> dict:
    del user
    return metrics_for_universe(session, universe_key)


@router.get("/correlation/summary")
def correlation_summary(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    del user
    rows = session.execute(
        select(
            CorrelationCandidate.universe_key,
            func.count(CorrelationCandidate.id),
            func.count(func.distinct(CorrelationCandidate.source_incident_id)),
        ).group_by(CorrelationCandidate.universe_key)
    ).all()
    universes = []
    for key, total, _ in rows:
        reviewed = int(
            session.scalar(
                select(func.count(func.distinct(CorrelationCandidate.id))).where(
                    CorrelationCandidate.universe_key == key,
                    review_filter(True),
                )
            )
            or 0
        )
        universes.append(
            {"universe_key": key, "candidates": int(total), "reviewed": reviewed}
        )
    return {
        "universes": universes,
        "total_candidates": sum(item["candidates"] for item in universes),
        "total_reviewed": sum(item["reviewed"] for item in universes),
        "metrics_endpoint": "/api/v1/governance/correlation/metrics",
        "recall_policy": (
            "Recall is null unless a complete external reference universe and "
            "true-duplicate count are attested."
        ),
    }


@router.get("/infrastructure/sources")
def list_infrastructure_sources(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
    category: str | None = None,
    validation_status: InfrastructureValidationStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> dict:
    del user
    statement = select(InfrastructureSource).order_by(
        InfrastructureSource.created_at.desc()
    )
    count_statement = select(func.count()).select_from(InfrastructureSource)
    for clause in (
        InfrastructureSource.category == category if category else None,
        InfrastructureSource.validation_status == validation_status
        if validation_status
        else None,
    ):
        if clause is not None:
            statement = statement.where(clause)
            count_statement = count_statement.where(clause)
    total = int(session.scalar(count_statement) or 0)
    sources = session.scalars(statement.limit(limit).offset(offset)).all()
    return {
        "items": [serialize_source(source) for source in sources],
        "total": total,
        "limit": limit,
        "offset": offset,
        "disclaimer": (
            "Registry metadata only. No infrastructure assets were fetched or "
            "ingested, and verification is not an operational availability claim."
        ),
    }


@router.post("/infrastructure/sources", status_code=201)
def register_infrastructure_source(
    payload: InfrastructureSourceCreate,
    user: Annotated[AuthenticatedUser, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    try:
        source = create_source(session, payload, user)
    except GovernanceError as error:
        _fail(error)
    return serialize_source(source, source_events(session, source.id))


@router.get("/infrastructure/sources/{source_id}")
def get_infrastructure_source(
    source_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    del user
    source = _source_or_404(session, source_id)
    return serialize_source(source, source_events(session, source.id))


@router.post("/infrastructure/sources/{source_id}/validation")
def validate_infrastructure_source(
    source_id: uuid.UUID,
    payload: InfrastructureValidationRequest,
    user: Annotated[AuthenticatedUser, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    source = _source_or_404(session, source_id)
    try:
        source = decide_validation(session, source, payload.status, payload.note, user)
    except GovernanceError as error:
        _fail(error)
    return serialize_source(source, source_events(session, source.id))


@router.get("/infrastructure/coverage")
def get_infrastructure_coverage(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    del user
    return infrastructure_coverage(session)


@router.get("/simulation/audit")
def simulation_audit(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    del user
    return build_simulation_audit(session)


@router.get("/traceability/runs")
def trace_runs(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> dict:
    del user
    return {"items": list_runs(session, limit)}


@router.get("/traceability/runs/{run_id}")
def trace_run(
    run_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
    cell_id: uuid.UUID | None = None,
    cell_limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> dict:
    del user
    try:
        return build_trace(
            session, run_id, cell_id=cell_id, cell_limit=cell_limit
        )
    except GovernanceError as error:
        _fail(error)


@router.get("/traceability/runs/{run_id}/export")
def export_trace(
    run_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
    cell_id: uuid.UUID | None = None,
    cell_limit: Annotated[int, Query(ge=1, le=500)] = 500,
) -> Response:
    del user
    import json

    try:
        payload = build_trace(
            session, run_id, cell_id=cell_id, cell_limit=cell_limit
        )
    except GovernanceError as error:
        _fail(error)
    body = json.dumps(payload, indent=2, sort_keys=True, default=str)
    return Response(
        content=body,
        media_type="application/json",
        headers={
            "Content-Disposition": (
                f'attachment; filename="civicflow-risk-trace-{run_id}.json"'
            ),
            "X-Content-Type-Options": "nosniff",
        },
    )
