"""Provider chain: grid cache -> primary -> keyless fallback."""

from __future__ import annotations

from app.core.config import Settings
from app.weather.cache import grid_cache
from app.weather.errors import WeatherProviderError
from app.weather.provider import WeatherProvider, WeatherSnapshot


def fetch_snapshot(
    primary: WeatherProvider,
    settings: Settings,
    latitude: float,
    longitude: float,
    *,
    fallback: WeatherProvider | None = None,
    force: bool = False,
) -> WeatherSnapshot:
    """Return a real snapshot, reusing a recent grid result when possible.

    A forced admin refresh bypasses the in-memory cache (the database row is
    still respected by the service layer). If the primary provider fails, a
    configured fallback is tried before surfacing an error to the UI.
    """
    ttl_seconds = settings.weather_cache_ttl_minutes * 60
    if not force:
        cached = grid_cache.get(latitude, longitude, ttl_seconds)
        if cached is not None:
            return cached

    try:
        snapshot = primary.fetch(latitude, longitude)
    except WeatherProviderError:
        if fallback is None:
            raise
        snapshot = fallback.fetch(latitude, longitude)

    if ttl_seconds > 0:
        grid_cache.set(latitude, longitude, snapshot)
    return snapshot
