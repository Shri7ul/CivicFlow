"""Short-lived in-memory weather cache keyed by a rounded lat/lng grid.

A single provider response is useful for every incident in the same ~1 km cell,
so caching by grid (instead of by incident) prevents repeated provider calls
from exhausting the free-tier quota. Entries are real provider snapshots with
their own retrieval timestamp; no value is ever synthesized here.
"""

from __future__ import annotations

import threading
import time
from app.weather.provider import WeatherSnapshot

GRID_DECIMALS = 2


def grid_key(latitude: float, longitude: float) -> tuple[float, float]:
    return round(latitude, GRID_DECIMALS), round(longitude, GRID_DECIMALS)


class GridSnapshotCache:
    """Thread-safe TTL cache. ``clear()`` exists for test isolation."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: dict[tuple[float, float], tuple[float, WeatherSnapshot]] = {}

    def get(
        self, latitude: float, longitude: float, ttl_seconds: float
    ) -> WeatherSnapshot | None:
        if ttl_seconds <= 0:
            return None
        key = grid_key(latitude, longitude)
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            stored_at, snapshot = entry
            if time.monotonic() - stored_at >= ttl_seconds:
                del self._entries[key]
                return None
            return snapshot

    def set(
        self, latitude: float, longitude: float, snapshot: WeatherSnapshot
    ) -> None:
        with self._lock:
            self._entries[grid_key(latitude, longitude)] = (
                time.monotonic(),
                snapshot,
            )

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


grid_cache = GridSnapshotCache()
