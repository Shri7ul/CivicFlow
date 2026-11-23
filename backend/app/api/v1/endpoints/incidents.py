"""Incident reporting, listing, detail, editing, and lifecycle endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    AuthenticatedUser,
    require_active_user,
    require_worker,
)
from app.db.session import get_db_session
from app.models import (
    IncidentCategory,
    IncidentSeverity,
    IncidentStatus,
)
from app.schemas.incidents import (
    EvidenceResponse,
    EvidenceUrlResponse,
    IncidentCreate,
    IncidentListResponse,
    IncidentResponse,
    IncidentStatusUpdate,
    IncidentUpdate,
)
from app.services.evidence import (
    evidence_signed_url,
    list_evidence,
    upload_evidence,
)
from app.services.storage import StorageService, get_storage_service
from app.services.incidents import (
    create_incident,
    get_incident,
    list_incidents,
    serialize_incident,
    transition_incident,
    update_incident,
)

router = APIRouter()


@router.post(
    "",
    response_model=IncidentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Report an incident",
)
def report_incident(
    payload: IncidentCreate,
    user: Annotated[AuthenticatedUser, Depends(require_active_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> IncidentResponse:
    incident = create_incident(
        session,
        user=user,
        title=payload.title,
        description=payload.description,
        category=payload.category,
        severity=payload.severity,
        latitude=payload.latitude,
        longitude=payload.longitude,
        address=payload.address,
    )
    return serialize_incident(incident, include_history=True)


@router.get(
    "",
    response_model=IncidentListResponse,
    summary="List incidents visible to the caller",
)
def list_visible_incidents(
    user: Annotated[AuthenticatedUser, Depends(require_active_user)],
    session: Annotated[Session, Depends(get_db_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status_filter: Annotated[
        IncidentStatus | None, Query(alias="status")
    ] = None,
    category: IncidentCategory | None = None,
    severity: IncidentSeverity | None = None,
    department_id: uuid.UUID | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    min_latitude: Annotated[float | None, Query(ge=-90, le=90)] = None,
    min_longitude: Annotated[float | None, Query(ge=-180, le=180)] = None,
    max_latitude: Annotated[float | None, Query(ge=-90, le=90)] = None,
    max_longitude: Annotated[float | None, Query(ge=-180, le=180)] = None,
) -> IncidentListResponse:
    return list_incidents(
        session,
        user=user,
        page=page,
        page_size=page_size,
        status=status_filter,
        category=category,
        severity=severity,
        department_id=department_id,
        query=q,
        min_latitude=min_latitude,
        min_longitude=min_longitude,
        max_latitude=max_latitude,
        max_longitude=max_longitude,
    )


@router.get(
    "/{incident_id}",
    response_model=IncidentResponse,
    summary="Get an incident and its lifecycle history",
)
def incident_detail(
    incident_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_active_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> IncidentResponse:
    incident = get_incident(session, incident_id, user, with_history=True)
    return serialize_incident(incident, include_history=True)


@router.patch(
    "/{incident_id}",
    response_model=IncidentResponse,
    summary="Edit incident content",
)
def edit_incident(
    incident_id: uuid.UUID,
    payload: IncidentUpdate,
    user: Annotated[AuthenticatedUser, Depends(require_active_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> IncidentResponse:
    incident = update_incident(
        session,
        user=user,
        incident_id=incident_id,
        changes=payload.model_dump(exclude_unset=True),
    )
    return serialize_incident(incident, include_history=True)


@router.get(
    "/{incident_id}/evidence",
    response_model=list[EvidenceResponse],
    summary="List evidence metadata for a visible incident",
)
def incident_evidence(
    incident_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_active_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> list[EvidenceResponse]:
    return list_evidence(session, user=user, incident_id=incident_id)


@router.post(
    "/{incident_id}/evidence",
    response_model=list[EvidenceResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Upload evidence to a visible incident",
)
def upload_incident_evidence(
    incident_id: uuid.UUID,
    files: Annotated[list[UploadFile], File(description="1-5 image files")],
    user: Annotated[AuthenticatedUser, Depends(require_active_user)],
    session: Annotated[Session, Depends(get_db_session)],
    storage: Annotated[StorageService, Depends(get_storage_service)],
) -> list[EvidenceResponse]:
    return upload_evidence(
        session,
        user=user,
        incident_id=incident_id,
        files=files,
        storage=storage,
    )


@router.get(
    "/{incident_id}/evidence/{evidence_id}/url",
    response_model=EvidenceUrlResponse,
    summary="Create a short-lived signed evidence URL",
)
def evidence_url(
    incident_id: uuid.UUID,
    evidence_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_active_user)],
    session: Annotated[Session, Depends(get_db_session)],
    storage: Annotated[StorageService, Depends(get_storage_service)],
) -> EvidenceUrlResponse:
    return evidence_signed_url(
        session,
        user=user,
        incident_id=incident_id,
        evidence_id=evidence_id,
        storage=storage,
    )


@router.post(
    "/{incident_id}/status",
    response_model=IncidentResponse,
    summary="Advance incident lifecycle (WORKER or ADMIN)",
)
def change_incident_status(
    incident_id: uuid.UUID,
    payload: IncidentStatusUpdate,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> IncidentResponse:
    incident = transition_incident(
        session,
        user=user,
        incident_id=incident_id,
        target=payload.status,
        department_id=payload.department_id,
        note=payload.note,
    )
    return serialize_incident(incident, include_history=True)
