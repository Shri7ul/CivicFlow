"""Human field-observation workflow with explicit ground-truth promotion.

An observation is never ground truth merely because it was created, submitted
or even VERIFIED. Ground truth requires a separate, explicit human decision by
a reviewer who did not observe or verify the record. AI predictions are excluded
from this workflow entirely.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser
from app.evidence import ground_truth
from app.geo.contexts import (
    UNKNOWN_CONTEXT_KEY,
    require_context,
    resolve_context_from_point,
)
from app.governance.errors import GovernanceError
from app.models.enums import (
    FieldObservationStatus,
    GroundTruthSourceType,
    ProvenanceKind,
    Role,
)
from app.models.phase14 import FieldObservation, FieldObservationEvent
from app.models.pilot import Pilot

REVIEW_DECISIONS = {"VERIFIED", "REJECTED", "REQUIRES_REVISION"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fail(message: str, *, code: str, status_code: int = 400) -> None:
    raise GovernanceError(message, code=code, status_code=status_code)


def get_observation(session: Session, observation_id: uuid.UUID) -> FieldObservation:
    observation = session.get(FieldObservation, observation_id)
    if observation is None:
        _fail("Field observation not found", code="observation_not_found", status_code=404)
    return observation


def _event(
    session: Session,
    observation: FieldObservation,
    action: str,
    previous: FieldObservationStatus | None,
    actor: AuthenticatedUser,
    *,
    note: str | None = None,
    rationale: str | None = None,
) -> None:
    session.add(
        FieldObservationEvent(
            observation_id=observation.id,
            action=action,
            from_status=previous,
            to_status=observation.status,
            actor_id=actor.profile.id,
            actor_email=actor.email,
            note=note,
            rationale=rationale,
            evidence_sha256=observation.evidence_sha256,
            created_at=_now(),
        )
    )


def create_observation(
    session: Session, payload: Any, actor: AuthenticatedUser
) -> FieldObservation:
    """Create a DRAFT observation. Observer identity and geography are server-owned."""

    if actor.profile.role not in {Role.WORKER, Role.ADMIN}:
        _fail("Only staff observers can create field observations", code="observer_forbidden", status_code=403)
    context_key = resolve_context_from_point(payload.latitude, payload.longitude)
    if context_key == UNKNOWN_CONTEXT_KEY:
        _fail(
            "Observation location is outside every registered geographic context",
            code="unknown_geographic_context",
            status_code=422,
        )
    if payload.pilot_id is not None:
        pilot = session.get(Pilot, payload.pilot_id)
        if pilot is None:
            _fail("Pilot not found", code="pilot_not_found", status_code=404)
        if pilot.geographic_context_key not in {UNKNOWN_CONTEXT_KEY, context_key}:
            _fail("Pilot geography does not match the observation location", code="context_mismatch", status_code=422)
    if payload.source_reference:
        duplicate = session.scalar(
            select(FieldObservation.id).where(
                FieldObservation.observer_id == actor.profile.id,
                FieldObservation.source_reference == payload.source_reference,
            )
        )
        if duplicate is not None:
            _fail(
                "This observer already recorded this source reference",
                code="duplicate_observation",
                status_code=409,
            )

    observation = FieldObservation(
        observation_key=f"obs-{uuid.uuid4().hex}",
        pilot_id=payload.pilot_id,
        geographic_context_key=context_key,
        observer_id=actor.profile.id,
        observer_role_snapshot=actor.profile.role.value,
        source_reference=payload.source_reference,
        observed_at=payload.observed_at,
        latitude=payload.latitude,
        longitude=payload.longitude,
        location=f"POINT({payload.longitude} {payload.latitude})",
        category=payload.category,
        description=payload.description,
        evidence_refs=payload.evidence_refs or [],
        evidence_sha256=payload.evidence_sha256,
        provenance_kind=ProvenanceKind.OPERATIONAL,
        confidence=payload.confidence,
        status=FieldObservationStatus.DRAFT,
        created_by=actor.profile.id,
    )
    session.add(observation)
    session.flush()
    _event(
        session,
        observation,
        "CREATED",
        None,
        actor,
        note="Field observation created as DRAFT. No verification or ground truth asserted.",
    )
    session.commit()
    return observation


def submit_observation(
    session: Session, observation: FieldObservation, actor: AuthenticatedUser
) -> FieldObservation:
    session.refresh(observation, with_for_update=True)
    if observation.status != FieldObservationStatus.DRAFT:
        _fail("Only a DRAFT observation can be submitted", code="invalid_observation_transition", status_code=409)
    if actor.profile.id != observation.observer_id and actor.profile.role != Role.ADMIN:
        _fail("Only the observer or an administrator can submit this observation", code="submit_forbidden", status_code=403)
    if not observation.evidence_refs and not observation.evidence_sha256:
        _fail(
            "Submission requires an evidence reference or an evidence hash",
            code="evidence_required",
            status_code=422,
        )
    previous = observation.status
    observation.status = FieldObservationStatus.SUBMITTED
    observation.submitted_at = _now()
    _event(session, observation, "SUBMITTED", previous, actor)
    session.commit()
    return observation


def assign_reviewer(
    session: Session,
    observation: FieldObservation,
    reviewer_id: uuid.UUID,
    actor: AuthenticatedUser,
) -> FieldObservation:
    if actor.profile.role != Role.ADMIN:
        _fail("Only an administrator can assign a reviewer", code="reviewer_assignment_forbidden", status_code=403)
    session.refresh(observation, with_for_update=True)
    if observation.status != FieldObservationStatus.SUBMITTED:
        _fail("Only a SUBMITTED observation can be assigned for review", code="invalid_observation_transition", status_code=409)
    from app.models.profile import Profile

    reviewer = session.get(Profile, reviewer_id)
    if reviewer is None or not reviewer.is_active or reviewer.role not in {Role.WORKER, Role.ADMIN}:
        _fail("Reviewer must be an active staff profile", code="invalid_reviewer", status_code=422)
    if reviewer.id == observation.observer_id:
        _fail("The observer cannot review their own observation", code="separation_of_duties", status_code=403)
    previous = observation.status
    observation.status = FieldObservationStatus.PENDING_REVIEW
    observation.reviewer_id = reviewer.id
    _event(session, observation, "REVIEW_ASSIGNED", previous, actor, note=f"Assigned reviewer {reviewer.id}")
    session.commit()
    return observation


def review_observation(
    session: Session, observation: FieldObservation, payload: Any, actor: AuthenticatedUser
) -> FieldObservation:
    session.refresh(observation, with_for_update=True)
    if observation.status != FieldObservationStatus.PENDING_REVIEW:
        _fail("Only a PENDING_REVIEW observation can receive a decision", code="invalid_observation_transition", status_code=409)
    if actor.profile.id != observation.reviewer_id and actor.profile.role != Role.ADMIN:
        _fail("Only the assigned reviewer or an administrator can decide", code="review_forbidden", status_code=403)
    if actor.profile.id == observation.observer_id:
        _fail("The observer cannot verify their own observation", code="separation_of_duties", status_code=403)
    if observation.provenance_kind != ProvenanceKind.OPERATIONAL:
        _fail("Non-operational provenance cannot become verified field evidence", code="non_operational_provenance", status_code=422)

    decision = (payload.decision or "").upper()
    if decision not in REVIEW_DECISIONS:
        _fail("Unsupported review decision", code="invalid_decision", status_code=422)
    if decision == "VERIFIED" and not (observation.evidence_refs or observation.evidence_sha256):
        _fail("VERIFIED requires evidence references or an evidence hash", code="verification_evidence_required", status_code=422)
    if decision == "REJECTED" and len((payload.rejection_reason or "").strip()) < 10:
        _fail("A rejection reason of at least 10 characters is required", code="reason_required", status_code=422)
    if decision == "REQUIRES_REVISION" and len((payload.revision_notes or "").strip()) < 10:
        _fail("Revision notes of at least 10 characters are required", code="revision_notes_required", status_code=422)

    previous = observation.status
    observation.status = FieldObservationStatus(decision)
    observation.decision = decision
    observation.reviewed_at = _now()
    observation.reviewer_id = observation.reviewer_id or actor.profile.id
    if decision == "VERIFIED":
        observation.rejection_reason = None
        observation.revision_notes = None
    elif decision == "REJECTED":
        observation.rejection_reason = payload.rejection_reason.strip()
    else:
        observation.revision_notes = payload.revision_notes.strip()
        observation.revision += 1
    _event(
        session,
        observation,
        "REVIEW_DECISION",
        previous,
        actor,
        note=payload.note,
        rationale=payload.rejection_reason or payload.revision_notes or payload.note,
    )
    session.commit()
    return observation


def mark_duplicate(
    session: Session,
    observation: FieldObservation,
    duplicate_of_id: uuid.UUID,
    actor: AuthenticatedUser,
) -> FieldObservation:
    if actor.profile.role != Role.ADMIN:
        _fail("Only an administrator can mark duplicates", code="duplicate_forbidden", status_code=403)
    session.refresh(observation, with_for_update=True)
    if observation.id == duplicate_of_id:
        _fail("An observation cannot duplicate itself", code="invalid_duplicate", status_code=422)
    other = session.get(FieldObservation, duplicate_of_id)
    if other is None or other.geographic_context_key != observation.geographic_context_key:
        _fail("Duplicate target not found in the same geographic context", code="invalid_duplicate", status_code=422)
    previous = observation.status
    observation.duplicate_of_id = other.id
    observation.status = FieldObservationStatus.REJECTED
    observation.decision = "DUPLICATE"
    observation.rejection_reason = f"Duplicate of {other.observation_key}"
    observation.reviewed_at = _now()
    _event(session, observation, "DUPLICATE_MARKED", previous, actor, note=observation.rejection_reason)
    session.commit()
    return observation


def promote_to_ground_truth(
    session: Session, observation: FieldObservation, actor: AuthenticatedUser
) -> dict:
    """Explicitly create a GT record from a VERIFIED observation.

    This is the only path from field observation to ground truth. It is
    performed by a distinct administrator and is fully append-only.
    """

    if actor.profile.role != Role.ADMIN:
        _fail("Only an administrator can promote ground truth", code="promotion_forbidden", status_code=403)
    session.refresh(observation, with_for_update=True)
    if observation.status != FieldObservationStatus.VERIFIED:
        _fail("Only a VERIFIED observation can be promoted", code="observation_not_verified", status_code=409)
    if observation.ground_truth_record_id is not None:
        _fail("This observation was already promoted", code="already_promoted", status_code=409)
    if actor.profile.id in {observation.observer_id, observation.reviewer_id}:
        _fail("Promotion must be performed by a distinct administrator", code="separation_of_duties", status_code=403)
    if observation.duplicate_of_id is not None or observation.provenance_kind == ProvenanceKind.SYNTHETIC:
        _fail("Duplicate or synthetic observations cannot be ground truth", code="ineligible_ground_truth", status_code=422)

    reference = observation.source_reference or f"field-observation:{observation.observation_key}"
    payload = SimpleNamespace(
        source_type=GroundTruthSourceType.FIELD_OBSERVATION,
        source_name="Human field observation",
        source_reference=reference,
        incident_id=None,
        incident_type=observation.category.value,
        description=observation.description,
        uncertainty=None,
        latitude=observation.latitude,
        longitude=observation.longitude,
        sensitive=True,
        evidence_refs=list(observation.evidence_refs or []),
        notes=(
            f"Explicitly promoted from verified field observation "
            f"{observation.observation_key} by administrator {actor.email}."
        ),
    )
    record = ground_truth.create_record(session, payload, actor)
    previous = observation.status
    observation.ground_truth_record_id = record.id
    _event(
        session,
        observation,
        "PROMOTED_TO_GROUND_TRUTH",
        previous,
        actor,
        note=f"Ground-truth record {record.record_key} created by explicit decision.",
    )
    session.commit()
    return {"observation": observation, "ground_truth": record}


def events_for(session: Session, observation_id: uuid.UUID) -> list[FieldObservationEvent]:
    return list(
        session.scalars(
            select(FieldObservationEvent)
            .where(FieldObservationEvent.observation_id == observation_id)
            .order_by(FieldObservationEvent.created_at, FieldObservationEvent.id)
        ).all()
    )


def status_counts(session: Session, *, context_key: str | None = None) -> dict[str, int]:
    statement = select(FieldObservation.status, func.count(FieldObservation.id))
    if context_key:
        statement = statement.where(FieldObservation.geographic_context_key == context_key)
    rows = session.execute(statement.group_by(FieldObservation.status)).all()
    counts = {status.value: 0 for status in FieldObservationStatus}
    for status, count in rows:
        counts[status.value] = int(count)
    return counts


def verified_promoted_count(session: Session, *, context_key: str) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(FieldObservation)
            .where(
                FieldObservation.geographic_context_key == context_key,
                FieldObservation.status == FieldObservationStatus.VERIFIED,
                FieldObservation.ground_truth_record_id.is_not(None),
            )
        )
        or 0
    )


def distinct_verified_observers(session: Session, *, context_key: str) -> int:
    return int(
        session.scalar(
            select(func.count(func.distinct(FieldObservation.observer_id)))
            .select_from(FieldObservation)
            .where(
                FieldObservation.geographic_context_key == context_key,
                FieldObservation.status == FieldObservationStatus.VERIFIED,
            )
        )
        or 0
    )
