"""Weather provider parsing, timeout, retry and malformed-data tests (A06)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from app.core.config import Settings
from app.weather.errors import WeatherProviderError
from app.weather.provider import MockProvider, OpenMeteoProvider


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "app_env": "testing",
        "weather_api_base_url": "https://example.invalid/forecast",
        "weather_max_retries": 2,
        "weather_retry_backoff_s": 0.0,
        "weather_forecast_hours": 3,
    }
    values.update(overrides)
    return Settings(**values)


def _payload() -> dict[str, Any]:
    return {
        "latitude": 23.81,
        "longitude": 90.41,
        "timezone": "UTC",
        "current": {
            "time": "2026-11-27T12:00",
            "temperature_2m": 30.5,
            "precipitation": 4.2,
            "wind_speed_10m": 22.0,
            "wind_gusts_10m": 35.0,
            "weather_code": 61,
        },
        "hourly": {
            "time": ["2026-11-27T13:00", "2026-11-27T14:00", "2026-11-27T15:00"],
            "temperature_2m": [31.0, 31.5, 30.0],
            "precipitation": [5.0, 6.0, 0.0],
            "precipitation_probability": [70, 80, 10],
        },
    }


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any] | None = None, raw: str | None = None) -> None:
        self.status_code = status_code
        self._payload = payload
        self._raw = raw

    def json(self) -> dict[str, Any]:
        if self._raw is not None:
            return json.loads(self._raw)
        return self._payload or {}


class FakeClient:
    calls = 0
    outcomes: list[object] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def get(self, url: str, params: dict[str, Any]) -> FakeResponse:
        FakeClient.calls += 1
        outcome = FakeClient.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture
def fake_client(monkeypatch: pytest.MonkeyPatch):
    FakeClient.calls = 0
    FakeClient.outcomes = []
    monkeypatch.setattr("app.weather.provider.httpx.Client", FakeClient)
    return FakeClient


def test_provider_parses_only_declared_fields_and_limits_forecast(fake_client) -> None:
    FakeClient.outcomes = [FakeResponse(200, _payload())]
    snapshot = OpenMeteoProvider(_settings()).fetch(23.81, 90.41)
    assert snapshot.provider == "open-meteo"
    assert snapshot.current.temperature_c == 30.5
    assert snapshot.current.precipitation_mm == 4.2
    assert snapshot.current.weather_code == 61
    assert len(snapshot.forecast) <= 3
    assert snapshot.forecast[0].precipitation_probability_pct == 70
    assert snapshot.as_dict()["current"]["observed_at"].endswith("+00:00")
    assert snapshot.data_quality == "OK"
    assert fake_client.calls == 1


def test_provider_retries_rate_limit_then_succeeds(fake_client) -> None:
    FakeClient.outcomes = [
        FakeResponse(429),
        FakeResponse(503),
        FakeResponse(200, _payload()),
    ]
    snapshot = OpenMeteoProvider(_settings()).fetch(23.81, 90.41)
    assert snapshot.current.temperature_c == 30.5
    assert fake_client.calls == 3


def test_provider_gives_up_after_bounded_retries(fake_client) -> None:
    FakeClient.outcomes = [FakeResponse(429), FakeResponse(429), FakeResponse(429)]
    with pytest.raises(WeatherProviderError) as exc:
        OpenMeteoProvider(_settings()).fetch(23.81, 90.41)
    assert exc.value.code == "provider_rate_limited"
    assert fake_client.calls == 3


def test_timeout_maps_to_stable_error_code(fake_client) -> None:
    FakeClient.outcomes = [httpx.TimeoutException("slow")]
    with pytest.raises(WeatherProviderError) as exc:
        OpenMeteoProvider(_settings()).fetch(23.81, 90.41)
    assert exc.value.code == "provider_timeout"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"current": {}, "hourly": {}},
        {"current": {}, "hourly": {"time": ["2026-11-27T13:00"], "precipitation": [1, 2]}},
    ],
)
def test_malformed_payloads_are_rejected(fake_client, payload: dict[str, Any]) -> None:
    FakeClient.outcomes = [FakeResponse(200, payload)]
    with pytest.raises(WeatherProviderError) as exc:
        OpenMeteoProvider(_settings(weather_max_retries=0)).fetch(23.81, 90.41)
    assert exc.value.code == "malformed_response"


def test_non_json_response_is_rejected(fake_client) -> None:
    FakeClient.outcomes = [FakeResponse(200, raw="<html>not json</html>")]
    with pytest.raises(WeatherProviderError) as exc:
        OpenMeteoProvider(_settings(weather_max_retries=0)).fetch(23.81, 90.41)
    assert exc.value.code == "malformed_response"


def test_mock_provider_is_labelled_and_never_claimed_as_observed() -> None:
    snapshot = MockProvider("heavy_rain").fetch(23.81, 90.41)
    assert snapshot.data_quality == "MOCK"
    assert snapshot.provider == "mock"
    assert snapshot.current.precipitation_mm == 18.0
