"""Domain errors for Phase 10 governance operations."""

from __future__ import annotations


class GovernanceError(Exception):
    """A validated governance rule rejected the operation."""

    def __init__(
        self, message: str, *, status_code: int = 400, code: str = "governance_error"
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
