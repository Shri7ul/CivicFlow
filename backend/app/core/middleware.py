"""Request logging, correlation, and baseline security middleware."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.request_context import (
    REQUEST_ID_HEADER,
    normalize_request_id,
    reset_request_id,
    set_request_id,
)

logger = get_logger("request")

_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect")
_HEALTH_PATHS = ("/health",)


class _FixedWindowLimiter:
    """Small in-process per-client limiter for mutating requests.

    This is a single-instance safety control, not a distributed quota. A
    horizontally scaled deployment must enforce limits at the edge as well.
    """

    def __init__(self, limit: int, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, now: float) -> bool:
        with self._lock:
            bucket = self._hits[key]
            cutoff = now - self.window_seconds
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return False
            bucket.append(now)
            return True


_limiter: _FixedWindowLimiter | None = None


def _get_limiter() -> _FixedWindowLimiter:
    global _limiter  # noqa: PLW0603 - process-wide singleton by design
    if _limiter is None:
        settings = get_settings()
        _limiter = _FixedWindowLimiter(settings.rate_limit_requests_per_minute)
    return _limiter


def reset_limiter() -> None:
    """Reset limiter state (used by tests and configuration changes)."""
    global _limiter  # noqa: PLW0603
    _limiter = None


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Add request ids, baseline security headers and bounded request logging.

    Query strings and request bodies are intentionally not logged. The client
    identifier used for rate limiting is the socket peer, never a spoofable
    proxy header.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        settings = get_settings()
        started = time.perf_counter()
        method = request.method
        path = request.url.path

        request_id = normalize_request_id(request.headers.get(REQUEST_ID_HEADER, ""))
        request.state.request_id = request_id
        token = set_request_id(request_id)

        rejected = False
        try:
            if (
                settings.rate_limiting_active
                and method in _MUTATING_METHODS
                and not path.startswith(_HEALTH_PATHS)
                and not path.startswith(_DOCS_PATHS)
            ):
                peer = request.client.host if request.client else "unknown"
                if not _get_limiter().allow(peer, started):
                    rejected = True
                    response = Response(
                        content='{"error":{"code":"rate_limited","message":'
                        '"Too many requests. Try again later."}}',
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        media_type="application/json",
                        headers={"Retry-After": "60"},
                    )
            else:
                response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - started) * 1000
            logger.exception(
                "Request failed | %s %s | %.2fms", method, path, duration_ms
            )
            reset_request_id(token)
            raise

        duration_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "Request | %s %s | %s | %.2fms%s",
            method,
            path,
            response.status_code,
            duration_ms,
            " | throttled" if rejected else "",
        )

        response.headers[REQUEST_ID_HEADER] = request_id
        if settings.security_headers_enabled:
            _apply_security_headers(response, path, request)
        reset_request_id(token)
        return response


def _apply_security_headers(response: Response, path: str, request: Request) -> None:
    """Apply non-sensitive baseline headers; never leak stack traces or secrets."""
    headers = response.headers
    headers.setdefault("X-Content-Type-Options", "nosniff")
    headers.setdefault("X-Frame-Options", "DENY")
    headers.setdefault("Referrer-Policy", "no-referrer")
    headers.setdefault(
        "Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()"
    )
    headers.setdefault("Cache-Control", "no-store")
    if not path.startswith(_DOCS_PATHS):
        headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; "
            "form-action 'none'",
        )
    forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip()
    if request.url.scheme == "https" or forwarded_proto.lower() == "https":
        headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
