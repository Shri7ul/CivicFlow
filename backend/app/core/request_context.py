"""Per-request correlation context.

The request identifier is generated at the edge of the application and carried
in a ``ContextVar`` so every log record emitted during a request can be
correlated without passing it through every function signature.

Only an identifier matching a conservative allow-list is accepted from an
incoming header. Anything else is replaced with a freshly generated identifier
so that untrusted input cannot inject control characters into logs.
"""

from __future__ import annotations

import re
import uuid
from contextvars import ContextVar

REQUEST_ID_HEADER = "X-Request-ID"
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")

_request_id: ContextVar[str] = ContextVar("civicflow_request_id", default="-")


def normalize_request_id(value: str | None) -> str:
    """Return a safe request id, generating one when the input is unusable."""
    if value and _SAFE_REQUEST_ID.fullmatch(value.strip()):
        return value.strip()
    return uuid.uuid4().hex


def set_request_id(value: str) -> object:
    """Set the current request id and return a token for ``reset_request_id``."""
    return _request_id.set(normalize_request_id(value))


def reset_request_id(token: object) -> None:
    """Reset the request id using a token from ``set_request_id``."""
    _request_id.reset(token)  # type: ignore[arg-type]


def get_request_id() -> str:
    """Return the current request id, or ``-`` outside a request."""
    return _request_id.get()
