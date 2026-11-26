"""Append-only workforce audit events.

Only ``emit`` writes to this table. There is no update or delete API, and
metadata is restricted to non-sensitive identifiers and state values.
"""

from __future__ import annotations

import uuid
from typing import Any, Mapping

from sqlalchemy.orm import Session

from app.models import WorkforceEvent

_SENSITIVE_KEYS = frozenset(
    {
        "password",
        "token",
        "secret",
        "authorization",
        "signed_url",
        "storage_path",
        "credentials",
        "access_key",
    }
)


def _safe_metadata(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    if not metadata:
        return {}
    safe: dict[str, Any] = {}
    for key, value in metadata.items():
        lowered = key.lower()
        if any(fragment in lowered for fragment in _SENSITIVE_KEYS):
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            safe[key] = value
        elif isinstance(value, uuid.UUID):
            safe[key] = str(value)
    return safe


def emit(
    session: Session,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    previous_state: str | None = None,
    new_state: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> WorkforceEvent:
    event = WorkforceEvent(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        previous_state=previous_state,
        new_state=new_state,
        detail=_safe_metadata(metadata),
    )
    session.add(event)
    return event
