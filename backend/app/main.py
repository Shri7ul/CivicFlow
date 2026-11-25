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
from app.core.middleware import RequestLoggingMiddleware, reset_limiter
from app.db.session import clear_engine_cache
from app.version import APP_VERSION

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
        # Release pooled connections and limiter state on graceful shutdown.
        clear_engine_cache()
        reset_limiter()
        logger.info("Shutting down %s", settings.service_name)


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings: Settings = get_settings()
    configure_logging(settings.log_level)

    docs_url = "/docs" if settings.docs_effective_enabled else None
    redoc_url = "/redoc" if settings.docs_effective_enabled else None
    openapi_url = "/openapi.json" if settings.docs_effective_enabled else None

    app = FastAPI(
        title=settings.service_name,
        version=APP_VERSION,
        description=(
            "CivicFlow urban civic intelligence decision-support API. "
            "NYC datasets are historical research; Dhaka data is preparation "
            "only. No model, pilot or civic action is activated by this API."
        ),
        lifespan=lifespan,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
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
