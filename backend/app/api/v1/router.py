"""Version 1 API router."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    ai,
    admin,
    auth,
    decisions,
    departments,
    governance,
    health,
    incidents,
    infrastructure,
    intelligence,
    operations,
    phase10,
    phase11,
    phase12,
    phase14,
    reviews,
    risk,
    validation,
    weather,
    workforce,
)

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(ai.router, prefix="/ai", tags=["civic-ai"])
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
api_router.include_router(
    decisions.router, prefix="/decisions", tags=["decisions"]
)
api_router.include_router(
    reviews.router, prefix="/decisions", tags=["decision-reviews"]
)
api_router.include_router(
    governance.router, prefix="/governance", tags=["governance"]
)
api_router.include_router(
    phase10.router, prefix="/governance", tags=["phase10-governance"]
)
api_router.include_router(
    phase11.router, prefix="/governance", tags=["phase11-evidence"]
)
api_router.include_router(
    phase12.router, prefix="/governance", tags=["phase12-geography"]
)
api_router.include_router(
    operations.router, prefix="/operations", tags=["operations"]
)
api_router.include_router(
    validation.router, prefix="/validation", tags=["validation"]
)
api_router.include_router(
    phase14.router, prefix="/governance/phase14", tags=["phase14-pilot-controls"]
)
api_router.include_router(departments.router, prefix="/departments", tags=["departments"])
api_router.include_router(workforce.router, prefix="/workforce", tags=["workforce"])
api_router.include_router(weather.router, prefix="/weather", tags=["weather-intelligence"])
