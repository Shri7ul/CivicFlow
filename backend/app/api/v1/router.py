"""Version 1 API router."""

from fastapi import APIRouter

from app.api.v1.endpoints import admin, auth, departments, health, incidents

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(incidents.router, prefix="/incidents", tags=["incidents"])
api_router.include_router(departments.router, prefix="/departments", tags=["departments"])
