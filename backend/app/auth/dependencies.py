"""Reusable FastAPI authentication and role-authorization dependencies."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.jwt import (
    SupabaseTokenVerifier,
    TokenVerificationError,
    VerifiedToken,
    get_token_verifier,
)
from app.core.logging import get_logger
from app.db.session import get_db_session
from app.models import Profile, Role

logger = get_logger("auth")


@dataclass(frozen=True)
class AuthenticatedUser:
    subject: uuid.UUID
    email: str | None
    profile: Profile


def _unauthorized(message: str = "Authentication required.") -> StarletteHTTPException:
    return StarletteHTTPException(
        status_code=401,
        detail={"code": "authentication_failed", "message": message},
        headers={"WWW-Authenticate": "Bearer"},
    )


def _forbidden(code: str, message: str) -> StarletteHTTPException:
    return StarletteHTTPException(
        status_code=403,
        detail={"code": code, "message": message},
    )


def get_bearer_token(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    if not authorization:
        raise _unauthorized()
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1]:
        raise _unauthorized("Malformed Authorization header.")
    return parts[1]


def verify_access_token(
    token: Annotated[str, Depends(get_bearer_token)],
    verifier: Annotated[SupabaseTokenVerifier, Depends(get_token_verifier)],
) -> VerifiedToken:
    try:
        return verifier.verify(token)
    except TokenVerificationError as exc:
        # Log only the classification, never token contents.
        logger.warning("JWT verification rejected | reason=%s", exc.reason)
        raise _unauthorized("Invalid or expired access token.") from exc


def get_token_claims(
    verified: Annotated[VerifiedToken, Depends(verify_access_token)],
) -> VerifiedToken:
    return verified


def get_current_profile(
    verified: Annotated[VerifiedToken, Depends(get_token_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> Profile:
    profile = session.scalar(
        select(Profile).where(Profile.id == verified.subject)
    )
    if profile is None:
        raise _forbidden(
            "profile_required",
            "No CivicFlow profile exists for this identity. Call POST /api/v1/auth/provision.",
        )
    if not profile.is_active:
        raise _forbidden("account_inactive", "This account is inactive.")
    return profile


def get_current_user(
    verified: Annotated[VerifiedToken, Depends(get_token_claims)],
    profile: Annotated[Profile, Depends(get_current_profile)],
) -> AuthenticatedUser:
    return AuthenticatedUser(
        subject=verified.subject,
        email=verified.email,
        profile=profile,
    )


def require_active_user(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> AuthenticatedUser:
    """Explicit semantic alias for endpoints that require an active profile."""
    return user


def require_role(*allowed_roles: Role) -> Callable[..., AuthenticatedUser]:
    """Build a centralized role dependency."""
    allowed = frozenset(allowed_roles)

    def dependency(
        user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    ) -> AuthenticatedUser:
        if user.profile.role not in allowed:
            raise _forbidden(
                "insufficient_role",
                "You do not have permission to perform this action.",
            )
        return user

    return dependency


require_admin = require_role(Role.ADMIN)
require_worker = require_role(Role.WORKER, Role.ADMIN)
