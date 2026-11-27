"""Grid caching and keyless fallback coverage for weather resilience."""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.core.config import Settings
from app.weather.cache import GridSnapshotCache, grid_key
from app.weather.chain import fetch_snapshot
from app.weather.errors import WeatherProviderError, rate_limited
from app.weather.provider import (
    MetNoProvider,
    MockProvider,
    WeatherSnapshot,
)


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "app_env": "testing",
        "weather_api_base_url": "https://example.invalid/forecast",
        "weather_fallback_base_url": "https://example.invalid/metno",
        "weather_max_retries": 1,
        "weather_retry_backoff_s": 0.0,
        "weather_forecast_hours": 3,
        "weather_cache_ttl_minutes": 30,
    }
    values.update(overrides)
    return Settings(**values)


class CountingProvider:
    def __init__(self, error: WeatherProviderError | None = None) -> None:
        self.name = "counting"
        self.calls = 0
        self._error = error

    def fetch(self, latitude: float, longitude: float) -> WeatherSnapshot:
        self.calls += 1
        if self._error is not None:
            raise self._error
        return MockProvider("clear").fetch(latitude, longitude)


def test_grid_key_rounds_to_a_shared_cell() -> None:
    assert grid_key(23.81031, 90.41252) == grid_key(23.81400, 90.41001)
    assert grid_key(23.81, 90.41) != grid_key(23.84, 90.41)


def test_cache_expires_and_can_be_cleared() -> None:
    cache = GridSnapshotCache()
    settings = _settings()
    snapshot = MockProvider().fetch(23.81, 90.41)

    cache.set(23.81, 90.41, snapshot)
    assert cache.get(23.81, 90.41, 1800) is snapshot
    assert cache.get(23.81, 90.41, 0) is None
    cache.clear()
    assert cache.get(23.81, 90.41, 1800) is None
    assert settings.weather_cache_ttl_minutes == 30


def test_fetch_snapshot_reuses_grid_cache_and_force_bypasses_it() -> None:
    cache = GridSnapshotCache()
    from app.weather import chain

    original = chain.grid_cache
    chain.grid_cache = cache
    try:
        provider = CountingProvider()
        settings = _settings()
        first = fetch_snapshot(provider, settings, 23.8103, 90.4125)
        second = fetch_snapshot(provider, settings, 23.8120, 90.4130)
        assert second is first
        assert provider.calls == 1

        fetch_snapshot(provider, settings, 23.8103, 90.4125, force=True)
        assert provider.calls == 2
    finally:
        chain.grid_cache = original


def test_fetch_snapshot_uses_fallback_on_primary_rate_limit() -> None:
    cache = GridSnapshotCache()
    from app.weather import chain

    original = chain.grid_cache
    chain.grid_cache = cache
    try:
        primary = CountingProvider(rate_limited())
        fallback = MockProvider("heavy_rain")
        snapshot = fetch_snapshot(
            primary, _settings(), 23.81, 90.41, fallback=fallback
        )
        assert snapshot.provider == "mock"
        assert snapshot.current.precipitation_mm == 18.0
    finally:
        chain.grid_cache = original


def test_fetch_snapshot_propagates_error_without_fallback() -> None:
    cache = GridSnapshotCache()
    from app.weather import chain

    original = chain.grid_cache
    chain.grid_cache = cache
    try:
        with pytest.raises(WeatherProviderError) as exc:
            fetch_snapshot(
                CountingProvider(rate_limited()), _settings(), 23.81, 90.41
            )
        assert exc.value.code == "provider_rate_limited"
    finally:
        chain.grid_cache = original


class FakeMetResponse:
    status_code = 200

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload


class FakeMetClient:
    calls = 0
    outcomes: list[object] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def __enter__(self) -> "FakeMetClient":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def get(
        self, url: str, params: dict[str, Any], headers: dict[str, str]
    ) -> FakeMetResponse:
        FakeMetClient.calls += 1
        assert "User-Agent" in headers
        outcome = FakeMetClient.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _met_payload() -> dict[str, Any]:
    entry = {
        "time": "2099-11-27T12:00:00Z",
        "data": {
            "instant": {
                "details": {
                    "air_temperature": 29.4,
                    "wind_speed": 7.2,
                    "wind_speed_of_gust": 12.0,
                }
            },
            "next_1_hours": {
                "summary": {"symbol_code": "heavyrain"},
                "details": {"precipitation_amount": 6.3},
            },
        },
    }
    return {"properties": {"timeseries": [entry]}}


def test_met_no_provider_parses_real_fields_without_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeMetClient.calls = 0
    FakeMetClient.outcomes = [FakeMetResponse(_met_payload())]
    monkeypatch.setattr("app.weather.provider.httpx.Client", FakeMetClient)

    snapshot = MetNoProvider(_settings()).fetch(23.81, 90.41)
    assert snapshot.provider == "met-no"
    assert snapshot.current.temperature_c == 29.4
    assert snapshot.current.precipitation_mm == 6.3
    assert snapshot.current.wind_speed_kmh == pytest.approx(25.9, abs=0.1)
    assert snapshot.current.weather_code == 65
    assert snapshot.current.observed_at is not None
    assert snapshot.data_quality == "OK"
    assert FakeMetClient.calls == 1


def test_met_no_provider_retries_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeMetClient.calls = 0
    FakeMetClient.outcomes = [
        _rate_limited_response(),
        FakeMetResponse(_met_payload()),
    ]
    monkeypatch.setattr("app.weather.provider.httpx.Client", FakeMetClient)
    snapshot = MetNoProvider(_settings()).fetch(23.81, 90.41)
    assert snapshot.current.temperature_c == 29.4
    assert FakeMetClient.calls == 2


def _rate_limited_response() -> FakeMetResponse:
    response = FakeMetResponse({})
    response.status_code = 429  # type: ignore[assignment]
    return response
