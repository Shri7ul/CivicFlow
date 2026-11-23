"""Authenticated profile endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    AuthenticatedUser,
    get_current_user,
    get_token_claims,
)
from app.auth.jwt import VerifiedToken
from app.db.session import get_db_session
from app.models import Profile
from app.schemas.auth import (
    ProfileResponse,
    ProfileUpdateRequest,
    ProvisionRequest,
)
from app.services.profiles import provision_profile, update_own_profile

router = APIRouter()


@router.get("/me", response_model=ProfileResponse, summary="Current profile")
def me(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> Profile:
    return user.profile


@router.post(
    "/provision",
    response_model=ProfileResponse,
    summary="Provision the caller's CITIZEN profile",
    description=(
        "Idempotently creates a profile for the authenticated Supabase identity. "
        "The role is always CITIZEN; privileged roles require an ADMIN role change."
    ),
)
def provision(
    verified: Annotated[VerifiedToken, Depends(get_token_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    payload: ProvisionRequest | None = None,
) -> Profile:
    profile, _created = provision_profile(
        session,
        subject=verified.subject,
        email=verified.email,
        full_name=payload.full_name if payload else None,
    )
    return profile


@router.patch(
    "/me",
    response_model=ProfileResponse,
    summary="Update own non-privileged profile fields",
)
def update_me(
    payload: ProfileUpdateRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> Profile:
    changes = payload.model_dump(exclude_unset=True)
    return update_own_profile(session, user.profile, changes)
