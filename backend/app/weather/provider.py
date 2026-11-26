"""Weather provider abstraction.

Only the providers module knows the external API shape. The rest of CivicFlow
works with the immutable :class:`WeatherSnapshot` value object, so a provider
can be replaced without touching the rule engine, service or API.

The default provider is Open-Meteo's free non-commercial forecast API, which
requires no key. Data is CC BY 4.0; the UI must attribute "Open-Meteo.com".
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

import httpx

from app.core.config import Settings
from app.weather.errors import (
    WeatherProviderError,
    malformed_response,
    provider_timeout,
    provider_unavailable,
    rate_limited,
)

CURRENT_FIELDS = (
    "temperature_2m",
    "precipitation",
    "wind_speed_10m",
    "wind_gusts_10m",
    "weather_code",
)
HOURLY_FIELDS = (
    "precipitation",
    "precipitation_probability",
    "temperature_2m",
)


@dataclass(frozen=True)
class CurrentConditions:
    observed_at: datetime | None
    temperature_c: float | None
    precipitation_mm: float | None
    wind_speed_kmh: float | None
    wind_gusts_kmh: float | None
    weather_code: int | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "observed_at": _iso(self.observed_at),
            "temperature_c": self.temperature_c,
            "precipitation_mm": self.precipitation_mm,
            "wind_speed_kmh": self.wind_speed_kmh,
            "wind_gusts_kmh": self.wind_gusts_kmh,
            "weather_code": self.weather_code,
        }


@dataclass(frozen=True)
class ForecastHour:
    time: datetime
    temperature_c: float | None
    precipitation_mm: float | None
    precipitation_probability_pct: int | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "time": _iso(self.time),
            "temperature_c": self.temperature_c,
            "precipitation_mm": self.precipitation_mm,
            "precipitation_probability_pct": self.precipitation_probability_pct,
        }


@dataclass(frozen=True)
class WeatherSnapshot:
    provider: str
    latitude: float
    longitude: float
    retrieved_at: datetime
    current: CurrentConditions
    forecast: tuple[ForecastHour, ...]
    data_quality: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "retrieved_at": _iso(self.retrieved_at),
            "data_quality": self.data_quality,
            "current": self.current.as_dict(),
            "forecast": [hour.as_dict() for hour in self.forecast],
        }


class WeatherProvider(Protocol):
    name: str

    def fetch(self, latitude: float, longitude: float) -> WeatherSnapshot: ...


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat()


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _integer(value: Any) -> int | None:
    number = _number(value)
    return int(number) if number is not None else None


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class OpenMeteoProvider:
    """Open-Meteo forecast API with timeouts, bounded retries and strict parsing."""

    name = "open-meteo"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._base_url = settings.weather_api_base_url
        self._timeout = httpx.Timeout(settings.weather_timeout_s)
        self._max_retries = settings.weather_max_retries
        self._backoff = settings.weather_retry_backoff_s

    def fetch(self, latitude: float, longitude: float) -> WeatherSnapshot:
        payload = self._request(latitude, longitude)
        return self._parse(payload, latitude, longitude)

    def _request(self, latitude: float, longitude: float) -> dict[str, Any]:
        params: dict[str, Any] = {
            "latitude": latitude,
            "longitude": longitude,
            "current": ",".join(CURRENT_FIELDS),
            "hourly": ",".join(HOURLY_FIELDS),
            "timezone": "UTC",
            "forecast_days": 2,
        }
        if self._settings.weather_api_key is not None:
            params["apikey"] = self._settings.weather_api_key.get_secret_value()

        attempt = 0
        while True:
            attempt += 1
            try:
                with httpx.Client(timeout=self._timeout, follow_redirects=False) as client:
                    response = client.get(self._base_url, params=params)
            except httpx.TimeoutException as exc:
                raise provider_timeout() from exc
            except httpx.HTTPError as exc:
                raise provider_unavailable(type(exc).__name__) from exc

            if response.status_code == 429:
                if attempt <= self._max_retries:
                    time.sleep(self._backoff * attempt)
                    continue
                raise rate_limited()
            if response.status_code >= 500:
                if attempt <= self._max_retries:
                    time.sleep(self._backoff * attempt)
                    continue
                raise provider_unavailable(f"HTTP {response.status_code}")
            if response.status_code >= 400:
                raise provider_unavailable(f"HTTP {response.status_code}")
            try:
                payload = response.json()
            except ValueError as exc:
                raise malformed_response() from exc
            if not isinstance(payload, dict):
                raise malformed_response()
            return payload

    def _parse(
        self, payload: dict[str, Any], latitude: float, longitude: float
    ) -> WeatherSnapshot:
        current_raw = payload.get("current")
        hourly_raw = payload.get("hourly")
        if not isinstance(current_raw, dict) or not isinstance(hourly_raw, dict):
            raise malformed_response()
        times = hourly_raw.get("time")
        if not isinstance(times, list):
            raise malformed_response()
        for key in HOURLY_FIELDS:
            values = hourly_raw.get(key)
            if values is not None and (not isinstance(values, list) or len(values) != len(times)):
                raise malformed_response()

        current = CurrentConditions(
            observed_at=_parse_time(current_raw.get("time")),
            temperature_c=_number(current_raw.get("temperature_2m")),
            precipitation_mm=_number(current_raw.get("precipitation")),
            wind_speed_kmh=_number(current_raw.get("wind_speed_10m")),
            wind_gusts_kmh=_number(current_raw.get("wind_gusts_10m")),
            weather_code=_integer(current_raw.get("weather_code")),
        )

        forecast: list[ForecastHour] = []
        now = datetime.now(timezone.utc)
        for index, raw_time in enumerate(times):
            parsed = _parse_time(raw_time)
            if parsed is None or parsed < now.replace(minute=0, second=0, microsecond=0):
                continue
            forecast.append(
                ForecastHour(
                    time=parsed,
                    temperature_c=_number((hourly_raw.get("temperature_2m") or [None] * len(times))[index]),
                    precipitation_mm=_number((hourly_raw.get("precipitation") or [None] * len(times))[index]),
                    precipitation_probability_pct=_integer(
                        (hourly_raw.get("precipitation_probability") or [None] * len(times))[index]
                    ),
                )
            )
        forecast = forecast[: self._settings.weather_forecast_hours]
        if not forecast:
            raise malformed_response()

        completeness = sum(
            1
            for value in (
                current.temperature_c,
                current.precipitation_mm,
                current.wind_speed_kmh,
                current.weather_code,
            )
            if value is not None
        )
        quality = "OK" if completeness >= 3 else "PARTIAL"
        return WeatherSnapshot(
            provider=self.name,
            latitude=latitude,
            longitude=longitude,
            retrieved_at=datetime.now(timezone.utc),
            current=current,
            forecast=tuple(forecast),
            data_quality=quality,
        )


class MockProvider:
    """Deterministic provider for tests and local UI work.

    It is never used in production unless explicitly configured. Its snapshots
    are labelled ``data_quality='MOCK'`` so no mock value can be mistaken for
    observed weather.
    """

    name = "mock"

    def __init__(self, scenario: str = "clear") -> None:
        if scenario not in {"clear", "heavy_rain", "strong_wind", "heat", "partial"}:
            raise ValueError(f"Unknown mock scenario: {scenario}")
        self._scenario = scenario

    def fetch(self, latitude: float, longitude: float) -> WeatherSnapshot:
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        scenarios = {
            "clear": (0.0, 5, 12.0, 10.0, 0),
            "heavy_rain": (18.0, 95, 24.0, 28.0, 63),
            "strong_wind": (0.0, 10, 52.0, 68.0, 95),
            "heat": (0.0, 2, 41.0, 12.0, 0),
            "partial": (None, None, None, None, None),
        }
        rain, probability, temp, wind, code = scenarios[self._scenario]
        forecast = tuple(
            ForecastHour(
                time=datetime.fromtimestamp(
                    now.timestamp() + hour * 3600, tz=timezone.utc
                ),
                temperature_c=temp,
                precipitation_mm=rain,
                precipitation_probability_pct=probability,
            )
            for hour in range(1, 7)
        )
        return WeatherSnapshot(
            provider=self.name,
            latitude=latitude,
            longitude=longitude,
            retrieved_at=datetime.now(timezone.utc),
            current=CurrentConditions(
                observed_at=datetime.now(timezone.utc),
                temperature_c=temp,
                precipitation_mm=rain,
                wind_speed_kmh=wind,
                wind_gusts_kmh=wind + 8 if wind is not None else None,
                weather_code=code,
            ),
            forecast=forecast,
            data_quality="PARTIAL" if self._scenario == "partial" else "MOCK",
        )


class FailingMockProvider:
    """Test double that raises a provider error on demand."""

    def __init__(self, error: WeatherProviderError) -> None:
        self.name = "failing-mock"
        self._error = error
        self.calls = 0

    def fetch(self, latitude: float, longitude: float) -> WeatherSnapshot:
        self.calls += 1
        raise self._error


def build_provider(settings: Settings) -> WeatherProvider:
    if settings.weather_provider == "mock":
        return MockProvider()
    return OpenMeteoProvider(settings)
