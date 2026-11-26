"""Deterministic weather-impact rule engine tests (A02)."""

from __future__ import annotations

from types import SimpleNamespace

from app.core.config import Settings
from app.weather import rules
from app.weather.provider import CurrentConditions, ForecastHour, MockProvider, WeatherSnapshot


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {"_env_file": None, "app_env": "testing"}
    values.update(overrides)
    return Settings(**values)


def _incident(category: str, title: str, description: str) -> SimpleNamespace:
    return SimpleNamespace(category=category, title=title, description=description)


def test_rule_engine_is_versioned_and_never_invents_a_score() -> None:
    result = rules.assess(
        _incident("DRAINAGE", "Blocked drain", "Water pooling on the road"),
        MockProvider("heavy_rain").fetch(23.81, 90.41),
        _settings(),
    )
    assert result["rule_engine_version"] == rules.RULE_ENGINE_VERSION
    assert result["rule_engine_version"] == "weather-impact-v1"
    assert "risk_score" not in result
    assert "score" not in result
    assert result["decision_note"]
    assert "not causation" in result["uncertainty"]


def test_observed_heavy_rain_aggravates_drainage_incident() -> None:
    result = rules.assess(
        _incident("DRAINAGE", "Blocked storm drain", "Water pooling after rain"),
        MockProvider("heavy_rain").fetch(23.81, 90.41),
        _settings(),
    )
    signals = {item["rule_id"]: item for item in result["signals"]}
    assert "R-RAIN-DRAINAGE" in signals
    signal = signals["R-RAIN-DRAINAGE"]
    assert signal["kind"] == "AGGRAVATION"
    assert signal["relevance"] == "LIKELY"
    assert signal["evidence"]["basis"] == "observed"
    assert signal["evidence"]["observed_precipitation_mm"] == 18.0
    assert signal["evidence"]["heavy_rain_threshold_mm"] == 5.0
    assert result["potential_aggravation"] == [signal["explanation"]]


def test_forecast_only_rain_is_possible_not_likely() -> None:
    now_hour = ForecastHour(
        time=MockProvider().fetch(0, 0).forecast[0].time,
        temperature_c=26.0,
        precipitation_mm=9.0,
        precipitation_probability_pct=85,
    )
    snapshot = WeatherSnapshot(
        provider="mock",
        latitude=23.81,
        longitude=90.41,
        retrieved_at=MockProvider().fetch(0, 0).retrieved_at,
        current=CurrentConditions(None, 26.0, 0.0, 8.0, 12.0, 0),
        forecast=(now_hour,),
        data_quality="MOCK",
    )
    result = rules.assess(
        _incident("DRAINAGE", "Slow drain", "Water pooling"),
        snapshot,
        _settings(),
    )
    signal = result["signals"][0]
    assert signal["relevance"] == "POSSIBLE"
    assert signal["evidence"]["basis"] == "forecast"


def test_context_keywords_drive_secondary_hazard_rules() -> None:
    result = rules.assess(
        _incident(
            "UTILITIES",
            "Damaged wiring after storm",
            "Fallen tree near exposed electrical cable",
        ),
        MockProvider("strong_wind").fetch(23.81, 90.41),
        _settings(),
    )
    assert set(result["context_tags"]).issuperset({"tree", "electrical"})
    ids = result["rule_ids"]
    assert "R-WIND-TREE" in ids
    assert "R-RAIN-ELECTRICAL" not in ids  # no rain in this scenario
    hazards = result["potential_secondary_hazards"]
    assert hazards and all("not confirmed" in h or "may" in h for h in hazards)


def test_thresholds_are_configurable_and_change_outcome() -> None:
    incident = _incident("DRAINAGE", "Blocked drain", "Standing water")
    snapshot = MockProvider("heavy_rain").fetch(23.81, 90.41)
    permissive = rules.assess(
        incident,
        snapshot,
        _settings(
            weather_rule_heavy_rain_mm=50.0,
            weather_rule_rain_probability_pct=100,
        ),
    )
    strict = rules.assess(incident, snapshot, _settings(weather_rule_heavy_rain_mm=1.0))
    assert permissive["signals"] == []
    assert strict["signals"][0]["rule_id"] == "R-RAIN-DRAINAGE"


def test_no_matching_rule_returns_explicit_empty_assessment() -> None:
    result = rules.assess(
        _incident("OTHER", "General enquiry", "No weather-sensitive context"),
        MockProvider("clear").fetch(23.81, 90.41),
        _settings(),
    )
    assert result["signals"] == []
    assert result["potential_aggravation"] == []
    assert result["potential_secondary_hazards"] == []
    assert result["uncertainty"]
    assert result["status"] == "OK"


def test_conflicting_conditions_produce_stable_unique_signals() -> None:
    incident = _incident("ROADS", "Fallen tree and exposed wiring", "Debris blocks road")
    snapshot = MockProvider("heavy_rain").fetch(23.81, 90.41)
    snapshot = WeatherSnapshot(
        provider=snapshot.provider,
        latitude=snapshot.latitude,
        longitude=snapshot.longitude,
        retrieved_at=snapshot.retrieved_at,
        current=CurrentConditions(
            observed_at=snapshot.current.observed_at,
            temperature_c=41.0,
            precipitation_mm=18.0,
            wind_speed_kmh=52.0,
            wind_gusts_kmh=68.0,
            weather_code=95,
        ),
        forecast=snapshot.forecast,
        data_quality=snapshot.data_quality,
    )
    settings = _settings(weather_rule_high_temperature_c=35.0)
    first = rules.assess(incident, snapshot, settings)
    second = rules.assess(incident, snapshot, settings)
    assert first == second
    assert len(first["rule_ids"]) == len(set(first["rule_ids"]))
    assert {"R-RAIN-ROADS", "R-WIND-TREE", "R-RAIN-ELECTRICAL"}.issubset(
        set(first["rule_ids"])
    )
