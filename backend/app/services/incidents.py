"""Incident reporting, visibility, lifecycle, and serialization."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from math import ceil
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.auth.dependencies import AuthenticatedUser
from app.core.exceptions import AppError
from app.models import (
    Department,
    Incident,
    IncidentCategory,
    IncidentEvidence,
    IncidentSeverity,
    IncidentStatus,
    IncidentStatusEvent,
    Role,
)
from app.schemas.incidents import (
    DepartmentResponse,
    DepartmentSummary,
    EvidenceResponse,
    IncidentListResponse,
    IncidentResponse,
    ProfileSummary,
    StatusEventResponse,
)

_POINT_RE = re.compile(
    r"POINT\s*\(\s*(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s*\)",
    re.IGNORECASE,
)

# Staff may move an incident forward, but not skip resolution/closure steps.
ALLOWED_TRANSITIONS: dict[IncidentStatus, frozenset[IncidentStatus]] = {
    IncidentStatus.OPEN: frozenset(
        {IncidentStatus.ACKNOWLEDGED, IncidentStatus.IN_PROGRESS}
    ),
    IncidentStatus.ACKNOWLEDGED: frozenset({IncidentStatus.IN_PROGRESS}),
    IncidentStatus.IN_PROGRESS: frozenset({IncidentStatus.RESOLVED}),
    IncidentStatus.RESOLVED: frozenset({IncidentStatus.CLOSED}),
    IncidentStatus.CLOSED: frozenset(),
}

_DEPARTMENT_REQUIRED = frozenset(
    {IncidentStatus.ACKNOWLEDGED, IncidentStatus.IN_PROGRESS}
)


def is_staff(user: AuthenticatedUser) -> bool:
    return user.profile.role in (Role.WORKER, Role.ADMIN)


def point_wkt(latitude: float, longitude: float) -> str:
    return f"POINT({longitude:.8f} {latitude:.8f})"


def parse_point(value: str) -> tuple[float, float]:
    match = _POINT_RE.search(value or "")
    if not match:
        raise AppError(
            "The stored incident location is invalid.",
            status_code=500,
            code="invalid_incident_location",
        )
    longitude, latitude = (float(part) for part in match.groups())
    return latitude, longitude


def _incident_query(*, with_history: bool = False):
    options = [
        joinedload(Incident.reporter),
        joinedload(Incident.assigned_department),
    ]
    if with_history:
        options.append(
            selectinload(Incident.status_events).joinedload(
                IncidentStatusEvent.actor
            )
        )
        options.append(
            selectinload(Incident.evidence).joinedload(
                IncidentEvidence.uploader
            )
        )
    return select(Incident).options(*options)


def _assert_visible(incident: Incident, user: AuthenticatedUser) -> None:
    if is_staff(user):
        return
    if incident.reporter_id != user.profile.id:
        # Do not reveal whether another citizen's incident exists.
        raise AppError(
            "Incident not found.",
            status_code=404,
            code="incident_not_found",
        )


def get_incident(
    session: Session,
    incident_id: uuid.UUID,
    user: AuthenticatedUser,
    *,
    with_history: bool = False,
) -> Incident:
    incident = session.scalar(
        _incident_query(with_history=with_history).where(Incident.id == incident_id)
    )
    if incident is None:
        raise AppError(
            "Incident not found.",
            status_code=404,
            code="incident_not_found",
        )
    _assert_visible(incident, user)
    return incident


def _reload_incident(
    session: Session, incident_id: uuid.UUID, user: AuthenticatedUser
) -> Incident:
    session.expire_all()
    return get_incident(session, incident_id, user, with_history=True)


def create_incident(
    session: Session,
    *,
    user: AuthenticatedUser,
    title: str,
    description: str,
    category: IncidentCategory,
    severity: IncidentSeverity,
    latitude: float,
    longitude: float,
    address: str | None,
) -> Incident:
    incident = Incident(
        title=title.strip(),
        description=description.strip(),
        category=category,
        severity=severity,
        status=IncidentStatus.OPEN,
        location=point_wkt(latitude, longitude),
        address=(address or "").strip() or None,
        reporter_id=user.profile.id,
    )
    session.add(incident)
    session.flush()
    session.add(
        IncidentStatusEvent(
            incident_id=incident.id,
            actor_id=user.profile.id,
            from_status=None,
            to_status=IncidentStatus.OPEN,
            note="Incident reported.",
            created_at=datetime.now(timezone.utc),
        )
    )
    session.commit()
    return _reload_incident(session, incident.id, user)


def update_incident(
    session: Session,
    *,
    user: AuthenticatedUser,
    incident_id: uuid.UUID,
    changes: dict[str, Any],
) -> Incident:
    if not changes:
        raise AppError(
            "Provide at least one field to update.",
            status_code=422,
            code="empty_update",
        )
    incident = get_incident(session, incident_id, user)
    staff = is_staff(user)
    if not staff:
        if incident.status is not IncidentStatus.OPEN:
            raise AppError(
                "Only OPEN incidents can be edited by their reporter.",
                status_code=409,
                code="incident_not_editable",
            )
    elif incident.status is IncidentStatus.CLOSED:
        raise AppError(
            "Closed incidents cannot be edited.",
            status_code=409,
            code="incident_not_editable",
        )

    if "latitude" in changes or "longitude" in changes:
        for coordinate in ("latitude", "longitude"):
            if coordinate in changes and changes[coordinate] is None:
                raise AppError(
                    "latitude and longitude must be numbers.",
                    status_code=422,
                    code="invalid_incident_update",
                )
        if ("latitude" in changes) != ("longitude" in changes):
            current_latitude, current_longitude = parse_point(incident.location)
            changes.setdefault("latitude", current_latitude)
            changes.setdefault("longitude", current_longitude)

    for field in ("title", "description"):
        if field in changes:
            value = changes[field]
            if value is None:
                raise AppError(
                    f"{field} cannot be null.",
                    status_code=422,
                    code="invalid_incident_update",
                )
            setattr(incident, field, value.strip())
    for field in ("category", "severity"):
        if field in changes and changes[field] is not None:
            setattr(incident, field, changes[field])
    if "address" in changes:
        value = changes["address"]
        incident.address = (value or "").strip() or None
    if "latitude" in changes:
        incident.location = point_wkt(
            float(changes["latitude"]), float(changes["longitude"])
        )

    session.commit()
    return _reload_incident(session, incident.id, user)


def transition_incident(
    session: Session,
    *,
    user: AuthenticatedUser,
    incident_id: uuid.UUID,
    target: IncidentStatus,
    department_id: uuid.UUID | None,
    note: str | None,
) -> Incident:
    incident = get_incident(session, incident_id, user)
    if target not in ALLOWED_TRANSITIONS[incident.status]:
        raise AppError(
            f"Cannot move an incident from {incident.status.value} to "
            f"{target.value}.",
            status_code=409,
            code="invalid_status_transition",
        )

    if department_id is not None:
        department = session.get(Department, department_id)
        if department is None or not department.is_active:
            raise AppError(
                "Department not found or inactive.",
                status_code=422,
                code="invalid_department",
            )
        incident.assigned_department_id = department.id

    if target in _DEPARTMENT_REQUIRED and incident.assigned_department_id is None:
        raise AppError(
            "Assign an active department before acknowledging or starting work.",
            status_code=422,
            code="department_required",
        )

    previous = incident.status
    incident.status = target
    if target is IncidentStatus.RESOLVED:
        incident.resolved_at = datetime.now(timezone.utc)
    session.add(
        IncidentStatusEvent(
            incident_id=incident.id,
            actor_id=user.profile.id,
            from_status=previous,
            to_status=target,
            note=note,
            created_at=datetime.now(timezone.utc),
        )
    )
    session.commit()
    return _reload_incident(session, incident.id, user)


def list_incidents(
    session: Session,
    *,
    user: AuthenticatedUser,
    page: int,
    page_size: int,
    status: IncidentStatus | None = None,
    category: IncidentCategory | None = None,
    severity: IncidentSeverity | None = None,
    department_id: uuid.UUID | None = None,
    query: str | None = None,
    min_latitude: float | None = None,
    min_longitude: float | None = None,
    max_latitude: float | None = None,
    max_longitude: float | None = None,
) -> IncidentListResponse:
    conditions = []
    if not is_staff(user):
        conditions.append(Incident.reporter_id == user.profile.id)
    if status is not None:
        conditions.append(Incident.status == status)
    if category is not None:
        conditions.append(Incident.category == category)
    if severity is not None:
        conditions.append(Incident.severity == severity)
    if department_id is not None:
        conditions.append(Incident.assigned_department_id == department_id)
    if query:
        pattern = f"%{query.strip()}%"
        conditions.append(
            or_(
                Incident.title.ilike(pattern),
                Incident.description.ilike(pattern),
                Incident.address.ilike(pattern),
            )
        )

    bounds = (min_latitude, min_longitude, max_latitude, max_longitude)
    if any(value is not None for value in bounds):
        if any(value is None for value in bounds):
            raise AppError(
                "Provide all four bounding-box coordinates or none.",
                status_code=422,
                code="invalid_bbox",
            )
        assert min_latitude is not None and min_longitude is not None
        assert max_latitude is not None and max_longitude is not None
        if min_latitude > max_latitude or min_longitude > max_longitude:
            raise AppError(
                "Bounding-box minimums must not exceed maximums.",
                status_code=422,
                code="invalid_bbox",
            )
        if session.get_bind().dialect.name != "postgresql":
            raise AppError(
                "Bounding-box filtering requires PostgreSQL/PostGIS.",
                status_code=400,
                code="spatial_filter_unsupported",
            )
        envelope = func.ST_GeogFromText(
            func.ST_AsText(
                func.ST_MakeEnvelope(
                    min_longitude,
                    min_latitude,
                    max_longitude,
                    max_latitude,
                    4326,
                )
            )
        )
        conditions.append(func.ST_Intersects(Incident.location, envelope))

    filters = tuple(conditions)
    total = (
        session.scalar(
            select(func.count()).select_from(Incident).where(*filters)
        )
        or 0
    )
    incidents = session.scalars(
        _incident_query()
        .where(*filters)
        .order_by(Incident.created_at.desc(), Incident.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return IncidentListResponse(
        items=[serialize_incident(incident) for incident in incidents],
        total=int(total),
        page=page,
        page_size=page_size,
        pages=ceil(total / page_size) if total else 0,
    )


def list_departments(session: Session) -> list[DepartmentResponse]:
    departments = session.scalars(
        select(Department)
        .where(Department.is_active.is_(True))
        .order_by(Department.name.asc())
    ).all()
    return [
        DepartmentResponse(
            id=department.id,
            name=department.name,
            description=department.description,
            is_active=department.is_active,
        )
        for department in departments
    ]


def _profile_summary(profile) -> ProfileSummary | None:
    if profile is None:
        return None
    return ProfileSummary(id=profile.id, full_name=profile.full_name)


def _department_summary(department) -> DepartmentSummary | None:
    if department is None:
        return None
    return DepartmentSummary(id=department.id, name=department.name)


def serialize_incident(
    incident: Incident, *, include_history: bool = False
) -> IncidentResponse:
    latitude, longitude = parse_point(incident.location)
    history = []
    if include_history:
        history = [
            StatusEventResponse(
                id=event.id,
                from_status=event.from_status,
                to_status=event.to_status,
                note=event.note,
                actor=_profile_summary(event.actor),
                created_at=event.created_at,
            )
            for event in incident.status_events
        ]
    return IncidentResponse(
        id=incident.id,
        title=incident.title,
        description=incident.description,
        category=incident.category,
        severity=incident.severity,
        status=incident.status,
        latitude=latitude,
        longitude=longitude,
        address=incident.address,
        reporter=_profile_summary(incident.reporter),  # type: ignore[arg-type]
        assigned_department=_department_summary(incident.assigned_department),
        resolved_at=incident.resolved_at,
        created_at=incident.created_at,
        updated_at=incident.updated_at,
        history=history,
        evidence=[
            EvidenceResponse(
                id=item.id,
                incident_id=item.incident_id,
                file_name=item.file_name,
                mime_type=item.mime_type,
                file_size=item.file_size,
                uploader=_profile_summary(item.uploader),  # type: ignore[arg-type]
                created_at=item.created_at,
            )
            for item in (incident.evidence if include_history else [])
        ],
    )
