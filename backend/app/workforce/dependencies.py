"""Workforce-specific authorization dependencies.

Role is resolved from the authenticated database profile, never from a request
body. Approval alone is insufficient: an active WorkerProfile is also required,
so suspended workers lose operational access immediately.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.db.session import get_db_session
from app.models import Profile, Role, WorkerProfile, WorkerStatus


@dataclass(frozen=True)
class ActiveWorker:
    user: AuthenticatedUser
    worker: WorkerProfile

    @property
    def profile(self) -> Profile:
        return self.user.profile


def _forbidden(code: str, message: str) -> StarletteHTTPException:
    return StarletteHTTPException(
        status_code=403, detail={"code": code, "message": message}
    )


def require_active_worker(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> ActiveWorker:
    if user.profile.role is not Role.WORKER:
        raise _forbidden(
            "insufficient_role", "Worker authorization is required."
        )
    worker = session.scalar(
        select(WorkerProfile).where(WorkerProfile.profile_id == user.profile.id)
    )
    if worker is None:
        raise _forbidden(
            "worker_profile_required",
            "An approved worker profile is required for this action.",
        )
    if worker.status is not WorkerStatus.ACTIVE:
        raise _forbidden(
            "worker_suspended", "This worker profile is not active."
        )
    return ActiveWorker(user=user, worker=worker)
