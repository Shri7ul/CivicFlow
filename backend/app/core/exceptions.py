"""Consistent API error handling."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger
from app.schemas.errors import ErrorBody, ErrorResponse

logger = get_logger("errors")

_STATUS_CODES: dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: "bad_request",
    status.HTTP_401_UNAUTHORIZED: "unauthorized",
    status.HTTP_403_FORBIDDEN: "forbidden",
    status.HTTP_404_NOT_FOUND: "not_found",
    status.HTTP_405_METHOD_NOT_ALLOWED: "method_not_allowed",
    status.HTTP_409_CONFLICT: "conflict",
    413: "payload_too_large",
    422: "validation_error",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "internal_server_error",
    status.HTTP_503_SERVICE_UNAVAILABLE: "service_unavailable",
}


class AppError(Exception):
    """Base exception for expected application errors."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        code: str | None = None,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code or _STATUS_CODES.get(status_code, "application_error")
        self.details = details


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    payload = ErrorResponse(
        error=ErrorBody(code=code, message=message, details=details)
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(exclude_none=True),
        headers=headers,
    )


async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return _error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
    )


async def http_exception_handler(
    _request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict):
        message = str(detail.get("message", "Request failed"))
        code = str(detail.get("code", _STATUS_CODES.get(exc.status_code, "http_error")))
        details = detail.get("details")
    else:
        message = str(detail) if detail else "Request failed"
        code = _STATUS_CODES.get(exc.status_code, "http_error")
        details = None

    return _error_response(
        status_code=exc.status_code,
        code=code,
        message=message,
        details=details if isinstance(details, list) else None,
        headers=exc.headers,
    )


async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    details: list[dict[str, Any]] = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", ()))
        details.append(
            {
                "field": location or "request",
                "message": str(error.get("msg", "Invalid value")),
                "type": str(error.get("type", "value_error")),
            }
        )
    return _error_response(
        status_code=422,
        code="validation_error",
        message="Request validation failed.",
        details=details,
    )


async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    logger.exception(
        "Unhandled exception | %s %s", request.method, request.url.path, exc_info=exc
    )
    return _error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="internal_server_error",
        message="An unexpected error occurred.",
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register the shared exception handlers on the application."""
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
