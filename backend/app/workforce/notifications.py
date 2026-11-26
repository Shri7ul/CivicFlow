"""Direct in-app lifecycle notifications.

External email/push delivery is not configured in this repository. All events
are persisted as readable in-app notifications; no credentials, private
evidence URLs or signed links are ever stored in the body.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models import WorkforceNotification

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
