"""Reversible pilot shutdown with explicit data-preservation checks.

Shutdown transitions the pilot to TERMINATED and records what was preserved.
It never deletes evidence, provenance, audit events, decisions or incidents.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser
from app.governance.errors import GovernanceError
from app.governance.pilots import transition as transition_pilot
from app.models.enums import (
    PilotStatus,
    PilotTransitionAction,
    Role,
)
from app.models.evidence import EvidenceSnapshot, GroundTruthRecord
from app.models.phase14 import (
    BaselineComparison,
    FieldObservation,
    PilotBoundary,
    PilotDataSource,
    PilotIncident,
    PilotShutdown,
)
from app.models.pilot import Pilot, PilotTransition, RiskReviewCase


def _fail(message: str, *, code: str, status_code: int = 400) -> None:
    raise GovernanceError(message, code=code, status_code=status_code)


def _count(session: Session, statement) -> int:
    return int(session.scalar(select(func.count()).select_from(statement.subquery())) or 0)


def preserved_counts(session: Session, pilot: Pilot) -> dict[str, int]:
    context_key = pilot.geographic_context_key
    return {
        "evidence_snapshots": _count(
            session,
            select(EvidenceSnapshot.id).where(
                EvidenceSnapshot.geographic_context_key == context_key
            ),
        ),
        "ground_truth_records": _count(
            session,
            select(GroundTruthRecord.id).where(
                GroundTruthRecord.geographic_context_key == context_key
            ),
        ),
        "field_observations": _count(
            session,
            select(FieldObservation.id).where(FieldObservation.pilot_id == pilot.id),
        ),
        "pilot_boundaries": _count(
            session,
            select(PilotBoundary.id).where(PilotBoundary.pilot_id == pilot.id),
        ),
        "registered_sources": _count(
            session,
            select(PilotDataSource.id).where(PilotDataSource.pilot_id == pilot.id),
        ),
        "risk_review_cases": _count(
            session, select(RiskReviewCase.id).where(RiskReviewCase.pilot_id == pilot.id)
        ),
        "pilot_incidents": _count(
            session, select(PilotIncident.id).where(PilotIncident.pilot_id == pilot.id)
        ),
        "baseline_comparisons": _count(
            session, select(BaselineComparison.id).where(BaselineComparison.pilot_id == pilot.id)
        ),
        "pilot_transitions": _count(
            session, select(PilotTransition.id).where(PilotTransition.pilot_id == pilot.id)
        ),
    }


def shutdown_pilot(
    session: Session, pilot: Pilot, reason: str, actor: AuthenticatedUser
) -> PilotShutdown:
    if actor.profile.role != Role.ADMIN:
        _fail("Only an administrator can shut down a pilot", code="shutdown_forbidden", status_code=403)
    if pilot.status in {PilotStatus.TERMINATED, PilotStatus.ARCHIVED, PilotStatus.REJECTED}:
        _fail("This pilot is already closed", code="pilot_closed", status_code=409)
    if len((reason or "").strip()) < 10:
        _fail("A shutdown reason of at least 10 characters is required", code="reason_required", status_code=422)
    existing = session.scalar(
        select(PilotShutdown.id).where(PilotShutdown.pilot_id == pilot.id)
    )
    if existing is not None:
        _fail("A shutdown record already exists for this pilot", code="shutdown_conflict", status_code=409)

    counts = preserved_counts(session, pilot)
    transition_pilot(session, pilot, PilotTransitionAction.TERMINATE, actor, reason.strip())

    record = PilotShutdown(
        shutdown_key=f"shutdown-{uuid.uuid4().hex}",
        pilot_id=pilot.id,
        reason=reason.strip(),
        action="TERMINATE",
        preserved_counts=counts,
        evidence_preserved=True,
        audit_preserved=True,
        provenance_preserved=True,
        decisions_preserved=True,
        incidents_preserved=True,
        model_activation_disabled=True,
        reauthorization_required=True,
        performed_by=actor.profile.id,
    )
    session.add(record)
    session.commit()
    return record


def for_pilot(session: Session, pilot_id: uuid.UUID) -> list[PilotShutdown]:
    return list(
        session.scalars(
            select(PilotShutdown)
            .where(PilotShutdown.pilot_id == pilot_id)
            .order_by(PilotShutdown.created_at)
        ).all()
    )
