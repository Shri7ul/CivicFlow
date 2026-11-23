"""Request logging middleware."""

from __future__ import annotations

import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.logging import get_logger

logger = get_logger("request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log method, path, status code, and duration for every request.

    Query strings and request bodies are intentionally not logged to avoid
    leaking sensitive values.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        started = time.perf_counter()
        method = request.method
        path = request.url.path

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - started) * 1000
            logger.exception(
                "Request failed | %s %s | %.2fms", method, path, duration_ms
            )
            raise

        duration_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "Request | %s %s | %s | %.2fms",
            method,
            path,
            response.status_code,
            duration_ms,
        )
        return response
