"""Pluggable ingestion adapters.

Live municipal feeds are not configured in this repository. The manual adapter
accepts an explicit, staff-supplied batch; external adapters must implement the
same interface and are rejected until credentials/access are intentionally
configured by a deployment.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any


class AdapterUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class SourceRecord:
    external_id: str
    payload: dict[str, Any]
    observed_at: datetime | None = None
    provenance: dict[str, Any] | None = None


class IngestionAdapter(ABC):
    """A cursor-based, resumable source adapter."""

    @abstractmethod
    def fetch(
        self, *, cursor: str | None = None, limit: int = 100
    ) -> tuple[list[SourceRecord], str | None]:
        raise NotImplementedError


class ManualAdapter(IngestionAdapter):
    """No network access; records arrive in the authorized API request."""

    def fetch(
        self, *, cursor: str | None = None, limit: int = 100
    ) -> tuple[list[SourceRecord], str | None]:
        del cursor, limit
        return [], None


class ConfiguredExternalAdapter(IngestionAdapter):
    """Placeholder for a future licensed feed; never silently returns data."""

    def fetch(
        self, *, cursor: str | None = None, limit: int = 100
    ) -> tuple[list[SourceRecord], str | None]:
        del cursor, limit
        raise AdapterUnavailable("External source adapter is not configured.")


ADAPTERS: dict[str, type[IngestionAdapter]] = {
    "manual": ManualAdapter,
    "external": ConfiguredExternalAdapter,
}


def get_adapter(name: str) -> IngestionAdapter:
    adapter_cls = ADAPTERS.get(name)
    if adapter_cls is None:
        raise AdapterUnavailable(f"Unknown ingestion adapter: {name}")
    return adapter_cls()
