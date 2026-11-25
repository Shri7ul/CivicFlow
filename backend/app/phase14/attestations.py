"""Human attestations for prerequisites that cannot be derived from data."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser
from app.governance.errors import GovernanceError
from app.models.enums import AttestationStatus, Role
from app.models.phase14 import Phase14Attestation, Phase14AttestationEvent

CATEGORIES = {
    "production_infrastructure",
    "migration",
    "backup_restore",
    "security_review",
    "legal_review",
    "stakeholder_approval",
    "reviewer_training",
    "monitoring",
    "rollback_drill",
    "model_validation",
    "explicit_authorization",
    "data_source_access",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fail(message: str, *, code: str, status_code: int = 400) -> None:
    raise GovernanceError(message, code=code, status_code=status_code)


def record_attestation(
    session: Session, payload: Any, actor: AuthenticatedUser
) -> Phase14Attestation:
    if actor.profile.role != Role.ADMIN:
        _fail("Only an administrator can record an attestation", code="attestation_forbidden", status_code=403)
    category = (payload.category or "").strip()
    if category not in CATEGORIES:
        _fail("Unsupported attestation category", code="invalid_attestation_category", status_code=422)
    criterion_key = (payload.criterion_key or "").strip()
    if not criterion_key:
        _fail("criterion_key is required", code="criterion_required", status_code=422)
    existing = session.scalar(
        select(Phase14Attestation.id).where(
            Phase14Attestation.category == category,
            Phase14Attestation.criterion_key == criterion_key,
        )
    )
    if existing is not None:
        _fail("An attestation for this criterion already exists", code="attestation_conflict", status_code=409)

    previous_status = None
    row = Phase14Attestation(
        category=category,
        criterion_key=criterion_key,
        status=payload.status,
        evidence=payload.evidence,
        evidence_refs=payload.evidence_refs,
        blocking=payload.blocking,
        assessed_by=actor.profile.id,
        assessed_at=_now(),
    )
    session.add(row)
    session.flush()
    session.add(
        Phase14AttestationEvent(
            attestation_id=row.id,
            from_status=previous_status,
            to_status=row.status,
            actor_id=actor.profile.id,
            actor_email=actor.email,
            note=f"Attestation recorded for {category}/{criterion_key}.",
            created_at=_now(),
        )
    )
    session.commit()
    return row


def find(
    session: Session, category: str, criterion_key: str | None = None
) -> list[Phase14Attestation]:
    statement = select(Phase14Attestation).where(Phase14Attestation.category == category)
    if criterion_key:
        statement = statement.where(Phase14Attestation.criterion_key == criterion_key)
    return list(session.scalars(statement.order_by(Phase14Attestation.created_at)).all())


def best_status(session: Session, category: str) -> AttestationStatus:
    """Return the strongest recorded status, defaulting to NOT_ASSESSED."""

    rows = find(session, category)
    if not rows:
        return AttestationStatus.NOT_ASSESSED
    for wanted in (AttestationStatus.FAIL, AttestationStatus.BLOCKED):
        if any(row.status == wanted and row.blocking for row in rows):
            return wanted
    if any(row.status == AttestationStatus.PASS for row in rows):
        return AttestationStatus.PASS
    return AttestationStatus.IN_PROGRESS
