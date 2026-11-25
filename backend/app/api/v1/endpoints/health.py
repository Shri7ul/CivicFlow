"""Version 1 health endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.core.config import get_settings
from app.db.health import check_database
from app.schemas.health import (
    DatabaseHealthResponse,
    DependencyHealthResponse,
    HealthResponse,
    ReadinessResponse,
)
from app.version import APP_VERSION

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


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Readiness (dependency-gated)",
    description=(
        "Returns 200 only when the required database dependency is reachable. "
        "A healthy process alone is not reported as ready."
    ),
    responses={
        status.HTTP_200_OK: {"description": "Ready to serve requests"},
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "A required dependency is unavailable"
        },
    },
)
def readiness(response: Response) -> ReadinessResponse:
    check = check_database()
    database = (
        "reachable" if check.reachable else "not_configured" if not check.configured else "unreachable"
    )
    ready = bool(check.configured and check.reachable)
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        status="ready" if ready else "not_ready",
        build_version=APP_VERSION,
        database=database,
        message=check.message if not ready else "Required dependencies are available.",
    )


@router.get(
    "/dependencies",
    response_model=DependencyHealthResponse,
    summary="Dependency status (non-sensitive)",
    description=(
        "Reports only availability booleans and generic statuses. Never "
        "returns credentials, endpoints, DSNs, stack traces or internal paths."
    ),
)
def dependencies(response: Response) -> DependencyHealthResponse:
    settings = get_settings()
    check = check_database()
    database = (
        "reachable" if check.reachable else "not_configured" if not check.configured else "unreachable"
    )
    auth_configured = bool(settings.supabase_url and settings.supabase_jwks_url)
    degraded = database != "reachable" or not auth_configured
    if degraded:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return DependencyHealthResponse(
        status="degraded" if degraded else "operational",
        build_version=APP_VERSION,
        database=database,
        auth_verification_configured=auth_configured,
        evidence_storage_configured=settings.supabase_storage_bucket is not None,
    )
