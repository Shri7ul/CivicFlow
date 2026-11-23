"""Minimal ADMIN role-management endpoints. No admin UI is built in Phase 1."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser, require_admin
from app.db.session import get_db_session
from app.models import Profile
from app.schemas.auth import ProfileResponse, RoleUpdateRequest
from app.services.profiles import change_profile_role

router = APIRouter()


@router.patch(
    "/profiles/{profile_id}/role",
    response_model=ProfileResponse,
    summary="Change an application role (ADMIN only)",
)
def update_profile_role(
    profile_id: uuid.UUID,
    payload: RoleUpdateRequest,
    actor: Annotated[AuthenticatedUser, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> Profile:
    return change_profile_role(
        session,
        actor=actor.profile,
        target_profile_id=profile_id,
        new_role=payload.role,
        reason=payload.reason,
    )
