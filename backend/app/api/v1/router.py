"""Version 1 API router."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    auth,
    departments,
    health,
    incidents,
    infrastructure,
    intelligence,
    risk,
)

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(incidents.router, prefix="/incidents", tags=["incidents"])
api_router.include_router(
    intelligence.router, prefix="/incidents", tags=["intelligence"]
)
api_router.include_router(
    infrastructure.router, prefix="/infrastructure", tags=["infrastructure"]
)
api_router.include_router(risk.router, prefix="/risk", tags=["risk"])
api_router.include_router(departments.router, prefix="/departments", tags=["departments"])
