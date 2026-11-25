"""Application profile provisioning and audited role management."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.models import Profile, Role, RoleChangeAudit

logger = get_logger("profiles")


def _default_full_name(email: str | None) -> str:
    if email and "@" in email:
        local = email.split("@", 1)[0].strip()
        if local:
            return local[:200]
    return "CivicFlow user"


def get_profile(session: Session, profile_id: uuid.UUID) -> Profile | None:
    return session.get(Profile, profile_id)


def provision_profile(
    session: Session,
    *,
    subject: uuid.UUID,
    email: str | None,
    full_name: str | None = None,
) -> tuple[Profile, bool]:
    """Create the caller's CITIZEN profile if absent. Never grants privileged roles."""
    existing = session.get(Profile, subject)
    if existing is not None:
        if not existing.is_active:
            raise AppError(
                "This account is inactive.",
                status_code=403,
                code="account_inactive",
            )
        return existing, False

    name = (full_name or "").strip() or _default_full_name(email)

    profile = Profile(
        id=subject,
        full_name=name[:200],
        role=Role.CITIZEN,
        is_active=True,
    )
    session.add(profile)
    try:
        session.commit()
    except IntegrityError:
        # Concurrent provisioning is idempotent: the unique auth UUID wins.
        session.rollback()
        existing = session.get(Profile, subject)
        if existing is None:
            raise
        if not existing.is_active:
            raise AppError(
                "This account is inactive.",
                status_code=403,
                code="account_inactive",
            )
        return existing, False

    session.refresh(profile)
    logger.info("Provisioned profile %s with role CITIZEN", profile.id)
    return profile, True


def update_own_profile(
    session: Session,
    profile: Profile,
    changes: dict[str, Any],
) -> Profile:
    """Update only non-privileged profile fields. Role is never accepted here."""
    allowed = {"full_name", "phone"}
    unexpected = set(changes) - allowed
    if unexpected:
        raise AppError(
            "Only full_name and phone may be updated.",
            status_code=422,
            code="invalid_profile_update",
            details=[{"field": name, "message": "Field is not editable"} for name in sorted(unexpected)],
        )

    if "full_name" in changes:
        name = (changes["full_name"] or "").strip()
        if not name:
            raise AppError(
                "full_name must not be blank.",
                status_code=422,
                code="invalid_profile_update",
            )
        profile.full_name = name[:200]
    if "phone" in changes:
        phone = changes["phone"]
        profile.phone = phone.strip() if isinstance(phone, str) and phone.strip() else None

    session.commit()
    session.refresh(profile)
    return profile


def change_profile_role(
    session: Session,
    *,
    actor: Profile,
    target_profile_id: uuid.UUID,
    new_role: Role,
    reason: str | None = None,
) -> Profile:
    """Admin-only role change with self-promotion guard, last-admin guard, audit."""
    if actor.id == target_profile_id:
        raise AppError(
            "Administrators cannot change their own role.",
            status_code=400,
            code="self_role_change_forbidden",
        )

    target = session.scalar(
        select(Profile)
        .where(Profile.id == target_profile_id)
        .with_for_update()
    )
    if target is None:
        raise AppError("Profile not found.", status_code=404, code="profile_not_found")
    if target.role is new_role:
        return target

    if target.role is Role.ADMIN and target.is_active and new_role is not Role.ADMIN:
        other_admins = session.scalar(
            select(func.count())
            .select_from(Profile)
            .where(
                Profile.role == Role.ADMIN,
                Profile.is_active.is_(True),
                Profile.id != target.id,
            )
        )
        if not other_admins:
            raise AppError(
                "The last active administrator cannot be demoted.",
                status_code=409,
                code="last_admin_protected",
            )

    old_role = target.role
    target.role = new_role
    session.add(
        RoleChangeAudit(
            actor_id=actor.id,
            target_profile_id=target.id,
            old_role=old_role,
            new_role=new_role,
            reason=(reason or "").strip() or None,
        )
    )
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise

    session.refresh(target)
    logger.info(
        "Role changed | actor=%s target=%s old=%s new=%s",
        actor.id,
        target.id,
        old_role.value,
        new_role.value,
    )
    return target
