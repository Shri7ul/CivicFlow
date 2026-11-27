"""Direct in-app lifecycle notifications.

External email/push delivery is not configured in this repository. All events
are persisted as readable in-app notifications; no credentials, private
evidence URLs or signed links are ever stored in the body.

Reads degrade gracefully when a deployment has not yet applied the Alembic
revision that creates ``workforce_notifications``. A missing table returns an
empty inbox instead of turning a dashboard request into a 500.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import WorkforceNotification

logger = get_logger("workforce.notifications")

LIFECYCLE_KINDS = frozenset(
    {
        "worker_application_submitted",
        "worker_application_approved",
        "worker_application_rejected",
        "worker_application_additional_information",
        "worker_suspended",
        "worker_reactivated",
        "incident_assigned",
        "assignment_reassigned",
        "assignment_accepted",
        "assignment_declined",
        "assignment_cancelled",
        "work_started",
        "completion_submitted",
        "completion_rejected",
        "completion_verified",
        "incident_resolved",
    }
)


def _missing_table(exc: SQLAlchemyError) -> bool:
    """Identify an absent-table error without leaking driver details to users."""
    original = getattr(exc, "orig", None)
    message = str(original if original is not None else exc).lower()
    return (
        "does not exist" in message
        or "no such table" in message
        or "undefined table" in message
    )


def notify(
    session: Session,
    *,
    recipient_id: uuid.UUID,
    kind: str,
    title: str,
    body: str,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
) -> WorkforceNotification:
    if kind not in LIFECYCLE_KINDS:
        raise ValueError(f"Unsupported notification kind: {kind}")
    notification = WorkforceNotification(
        recipient_id=recipient_id,
        kind=kind,
        title=title[:200],
        body=body,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    session.add(notification)
    return notification


def list_for_recipient(
    session: Session, recipient_id: uuid.UUID, *, limit: int = 100
) -> list[WorkforceNotification]:
    """Return the caller's inbox; treat an unmigrated table as an empty inbox."""
    try:
        return list(
            session.scalars(
                select(WorkforceNotification)
                .where(WorkforceNotification.recipient_id == recipient_id)
                .order_by(WorkforceNotification.created_at.desc())
                .limit(limit)
            ).all()
        )
    except SQLAlchemyError as exc:
        session.rollback()
        if not _missing_table(exc):
            raise
        logger.warning(
            "Notification table unavailable; returning empty inbox | error=%s",
            type(exc).__name__,
        )
        return []


def get_for_recipient(
    session: Session, notification_id: uuid.UUID, recipient_id: uuid.UUID
) -> WorkforceNotification | None:
    """Fetch one notification, returning None for a missing row or table."""
    try:
        notification = session.get(WorkforceNotification, notification_id)
    except SQLAlchemyError as exc:
        session.rollback()
        if not _missing_table(exc):
            raise
        logger.warning(
            "Notification table unavailable; treating notification as missing | error=%s",
            type(exc).__name__,
        )
        return None
    if notification is None or notification.recipient_id != recipient_id:
        return None
    return notification
