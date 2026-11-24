"""Human ground-truth workflow.

Citizen reports, AI predictions and observations start UNVERIFIED. Only a staff
reviewer distinct from the creator can record VERIFIED, REJECTED or
INSUFFICIENT_EVIDENCE. Every transition is append-only. This module never writes
risk scores, model weights, incident reports or dispatch state.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser
from app.governance.errors import GovernanceError
from app.models.enums import GroundTruthStatus, ProvenanceKind
from app.models.evidence import GroundTruthEvent, GroundTruthRecord
from app.models.incident import Incident


def get_record(session: Session, record_id: uuid.UUID) -> GroundTruthRecord:
    record = session.get(GroundTruthRecord, record_id)
    if record is None:
        raise GovernanceError(
            "Ground-truth record not found",
            status_code=404,
            code="ground_truth_not_found",
        )
    return record


def _event(
    session: Session,
    record: GroundTruthRecord,
    action: str,
    previous: GroundTruthStatus | None,
    actor: AuthenticatedUser,
    note: str | None,
    evidence_refs: list[str] | None = None,
) -> None:
    session.add(
        GroundTruthEvent(
            record_id=record.id,
            action=action,
            from_status=previous,
            to_status=record.status,
            actor_id=actor.profile.id,
            actor_email=actor.email,
            note=note,
            evidence_refs=evidence_refs or [],
            created_at=datetime.now(timezone.utc),
        )
    )


def create_record(
    session: Session, payload: Any, actor: AuthenticatedUser
) -> GroundTruthRecord:
    if payload.source_reference:
        existing = session.scalar(
            select(GroundTruthRecord.id).where(
                GroundTruthRecord.source_type == payload.source_type,
                GroundTruthRecord.source_reference == payload.source_reference,
            )
        )
        if existing is not None:
            raise GovernanceError(
                "A ground-truth record already exists for this source reference",
                status_code=409,
                code="ground_truth_reference_conflict",
            )
    if payload.incident_id is not None and session.get(Incident, payload.incident_id) is None:
        raise GovernanceError(
            "Incident not found",
            status_code=404,
            code="incident_not_found",
        )
    location = None
    if payload.latitude is not None and payload.longitude is not None:
        location = f"POINT({payload.longitude} {payload.latitude})"
    record = GroundTruthRecord(
        record_key=f"gt-{uuid.uuid4().hex}",
        incident_id=payload.incident_id,
        source_type=payload.source_type,
        provenance_kind=ProvenanceKind.OPERATIONAL,
        source_name=payload.source_name,
        source_reference=payload.source_reference,
        incident_type=payload.incident_type,
        description=payload.description,
        uncertainty=payload.uncertainty,
        location=location,
        sensitive=payload.sensitive,
        status=GroundTruthStatus.UNVERIFIED,
        evidence_refs=payload.evidence_refs,
        notes=payload.notes,
        created_by=actor.profile.id,
    )
    session.add(record)
    session.flush()
    _event(
        session,
        record,
        "CREATED",
        None,
        actor,
        "Evidence assertion recorded as UNVERIFIED; no verification asserted.",
    )
    session.commit()
    return record


def submit_for_review(
    session: Session, record: GroundTruthRecord, payload: Any, actor: AuthenticatedUser
) -> GroundTruthRecord:
    session.refresh(record, with_for_update=True)
    if record.status != GroundTruthStatus.UNVERIFIED:
        raise GovernanceError(
            "Only an UNVERIFIED record can be submitted for review",
            status_code=409,
            code="ground_truth_invalid_transition",
        )
    previous = record.status
    record.status = GroundTruthStatus.IN_REVIEW
    _event(
        session,
        record,
        "SUBMITTED_FOR_REVIEW",
        previous,
        actor,
        payload.note or "Submitted for independent staff review.",
        payload.evidence_refs,
    )
    session.commit()
    return record


def review_record(
    session: Session, record: GroundTruthRecord, payload: Any, actor: AuthenticatedUser
) -> GroundTruthRecord:
    session.refresh(record, with_for_update=True)
    if record.status != GroundTruthStatus.IN_REVIEW:
        raise GovernanceError(
            "Only an IN_REVIEW record can receive a verification decision",
            status_code=409,
            code="ground_truth_invalid_transition",
        )
    if record.created_by is not None and record.created_by == actor.profile.id:
        raise GovernanceError(
            "The creator cannot verify their own ground-truth assertion",
            status_code=403,
            code="separation_of_duties",
        )
    if payload.decision == "VERIFIED" and not payload.evidence_refs:
        raise GovernanceError(
            "VERIFIED requires at least one verification evidence reference",
            status_code=422,
            code="verification_evidence_required",
        )
    previous = record.status
    record.status = GroundTruthStatus(payload.decision)
    record.verification_method = payload.verification_method
    record.verified_by = actor.profile.id
    record.verified_at = datetime.now(timezone.utc)
    record.verification_note = payload.note
    record.verification_evidence_refs = payload.evidence_refs
    _event(
        session,
        record,
        "VERIFICATION_DECISION",
        previous,
        actor,
        payload.note,
        payload.evidence_refs,
    )
    session.commit()
    return record


def events_for(session: Session, record_id: uuid.UUID) -> list[GroundTruthEvent]:
    return list(
        session.scalars(
            select(GroundTruthEvent)
            .where(GroundTruthEvent.record_id == record_id)
            .order_by(GroundTruthEvent.created_at, GroundTruthEvent.id)
        ).all()
    )


def serialize_record(record: GroundTruthRecord, *, detail: bool = False) -> dict:
    payload = {
        "id": str(record.id),
        "record_key": record.record_key,
        "incident_id": str(record.incident_id) if record.incident_id else None,
        "source_type": record.source_type.value,
        "provenance_kind": record.provenance_kind.value,
        "source_name": record.source_name,
        "source_reference": record.source_reference,
        "incident_type": record.incident_type,
        "description": record.description,
        "uncertainty": float(record.uncertainty) if record.uncertainty is not None else None,
        "location": record.location,
        "sensitive": record.sensitive,
        "status": record.status.value,
        "verification_method": record.verification_method,
        "verified_by": str(record.verified_by) if record.verified_by else None,
        "verified_at": record.verified_at.isoformat() if record.verified_at else None,
        "evidence_refs": record.evidence_refs or [],
        "verification_evidence_refs": record.verification_evidence_refs or [],
        "verification_note": record.verification_note,
        "notes": record.notes,
        "created_by": str(record.created_by) if record.created_by else None,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
        "disclaimer": (
            "UNVERIFIED and AI_PREDICTION records are assertions, not physical "
            "incidents. Verification is a staff judgement and does not retrain or "
            "re-score any model."
        ),
    }
    if detail:
        if record.status == GroundTruthStatus.VERIFIED:
            payload["review_status"] = "HUMAN_VERIFIED"
        elif record.status in (
            GroundTruthStatus.REJECTED,
            GroundTruthStatus.INSUFFICIENT_EVIDENCE,
        ):
            payload["review_status"] = "REVIEWED_NOT_VERIFIED"
        else:
            payload["review_status"] = "AWAITING_HUMAN_VERIFICATION"
    return payload


def serialize_event(event: GroundTruthEvent) -> dict:
    return {
        "id": str(event.id),
        "action": event.action,
        "from_status": event.from_status.value if event.from_status else None,
        "to_status": event.to_status.value,
        "actor_id": str(event.actor_id) if event.actor_id else None,
        "note": event.note,
        "evidence_refs": event.evidence_refs or [],
        "created_at": event.created_at.isoformat(),
    }


def status_counts(session: Session) -> dict[str, int]:
    rows = session.execute(
        select(GroundTruthRecord.status, func.count(GroundTruthRecord.id)).group_by(
            GroundTruthRecord.status
        )
    ).all()
    counts = {status.value: 0 for status in GroundTruthStatus}
    for status, count in rows:
        counts[status.value] = int(count)
    return counts
