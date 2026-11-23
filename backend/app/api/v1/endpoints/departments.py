"""Department reference data for incident assignment."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser, require_active_user
from app.db.session import get_db_session
from app.schemas.incidents import DepartmentResponse
from app.services.incidents import list_departments

router = APIRouter()


@router.get(
    "",
    response_model=list[DepartmentResponse],
    summary="List active municipal departments",
)
def departments(
    _user: Annotated[AuthenticatedUser, Depends(require_active_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> list[DepartmentResponse]:
    return list_departments(session)
