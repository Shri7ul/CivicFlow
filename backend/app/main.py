"""CivicFlow API application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestLoggingMiddleware

APP_VERSION = "0.5.0"
logger = get_logger("app")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logger.info(
        "Starting %s v%s | env=%s | debug=%s",
        settings.service_name,
        APP_VERSION,
        settings.app_env,
        settings.debug,
    )
    logger.info("API prefix: %s", settings.api_v1_prefix)
    logger.info(
        "CORS origins: %s",
        ", ".join(settings.cors_origins) if settings.cors_origins else "none",
    )
    logger.info(
        "Database configuration: %s",
        "present" if settings.database_url_value else "not configured",
    )
    try:
        yield
    finally:
        logger.info("Shutting down %s", settings.service_name)


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings: Settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.service_name,
        version=APP_VERSION,
        description=(
            "Urban Impact & Response Intelligence API. "
            "Phase 5 adds a versioned H3 urban risk engine with explainable "
            "factor contributions, temporal trends, infrastructure exposure, "
            "and staff snapshots on top of incident operations, spatial "
            "exploration, private evidence, and reviewable intelligence."
        ),
        lifespan=lifespan,
    )

    # CORS is configured centrally from validated settings.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
