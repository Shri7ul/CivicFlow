"""Version 1 health endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.core.config import get_settings
from app.db.health import check_database
from app.schemas.health import DatabaseHealthResponse, HealthResponse

router = APIRouter()


@router.get(
    "",
    response_model=HealthResponse,
    summary="Application health",
    description=(
        "Returns application liveness only. Database connectivity is reported "
        "separately by /health/database."
    ),
)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        service=settings.service_name,
        environment=settings.app_env,
        version="v1",
    )


@router.get(
    "/database",
    response_model=DatabaseHealthResponse,
    summary="Database health",
    description=(
        "Performs a real SELECT 1 connectivity check when a database is "
        "configured. Returns 503 when the database is not configured or "
        "unreachable."
    ),
    responses={
        status.HTTP_200_OK: {"description": "Database is reachable"},
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Database is not configured or unreachable"
        },
    },
)
def database_health(response: Response) -> DatabaseHealthResponse:
    check = check_database()

    if not check.configured:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return DatabaseHealthResponse(
            status="not_configured",
            database="not_configured",
            message=check.message,
        )

    if not check.reachable:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return DatabaseHealthResponse(
            status="unhealthy",
            database="unreachable",
            message=check.message,
        )

    return DatabaseHealthResponse(
        status="healthy",
        database="reachable",
        message=check.message,
    )
