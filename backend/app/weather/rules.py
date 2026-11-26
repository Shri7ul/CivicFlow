"""Explainable, deterministic weather-impact rules (A02).

The rule engine is deliberately not a language model. Every signal cites the
structured weather values and the threshold that produced it. It reports
*potential* relevance and secondary hazards, never confirmed impact or cause.
"""

from __future__ import annotations

from typing import Any

from app.weather.provider import WeatherSnapshot

RULE_ENGINE_VERSION = "weather-impact-v1"

UNCERTAINTY = (
    "Weather values are model estimates for a grid cell near the incident. "
    "They describe possible contextual relevance, not causation or confirmed "
    "impact. No incident priority or status is changed automatically."
)
DECISION_NOTE = (
    "This assessment is advisory input for authorized staff review only."
)

_CONTEXT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "waterlogging": ("waterlogging", "water logging", "standing water", "flooded", "pooling"),
    "drain": ("drain", "culvert", "sewer", "gully"),
    "tree": ("fallen tree", "tree branch", "uprooted", "branch down"),
    "electrical": ("electric", "wiring", "transformer", "power line", "cable"),
    "debris": ("debris", "rubble", "construction waste"),
    "road_damage": ("pothole", "road damage", "broken road", "cracked road"),
}


def context_tags(title: str, description: str) -> list[str]:
    text = f"{title} {description}".lower()
    return [tag for tag, keywords in _CONTEXT_KEYWORDS.items() if any(k in text for k in keywords)]


def _signal(
    rule_id: str,
    kind: str,
    relevance: str,
    explanation: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "kind": kind,
        "relevance": relevance,
        "explanation": explanation,
        "evidence": evidence,
    }


def assess(incident: Any, snapshot: WeatherSnapshot, thresholds: Any) -> dict[str, Any]:
    """Produce a structured, explainable assessment.

    ``thresholds`` is the application Settings object (or any object exposing
    the ``weather_rule_*`` fields), which keeps rules configurable without
    coupling the engine to Pydantic settings.
    """
    category = str(getattr(incident, "category", "OTHER"))
    if hasattr(category, "value"):
        category = str(category.value)
    tags = context_tags(str(getattr(incident, "title", "")), str(getattr(incident, "description", "")))

    observed_rain = snapshot.current.precipitation_mm
    forecast_rain = [hour.precipitation_mm for hour in snapshot.forecast if hour.precipitation_mm is not None]
    forecast_probability = [
        hour.precipitation_probability_pct
        for hour in snapshot.forecast
        if hour.precipitation_probability_pct is not None
    ]
    max_forecast_rain = max(forecast_rain) if forecast_rain else None
    max_probability = max(forecast_probability) if forecast_probability else None

    rain_observed = observed_rain is not None and observed_rain >= thresholds.weather_rule_heavy_rain_mm
    rain_forecast = (
        max_forecast_rain is not None and max_forecast_rain >= thresholds.weather_rule_heavy_rain_mm
    ) or (
        max_probability is not None
        and max_probability >= thresholds.weather_rule_rain_probability_pct
    )
    rain_any = rain_observed or rain_forecast
    rain_evidence = {
        "observed_precipitation_mm": observed_rain,
        "max_forecast_precipitation_mm": max_forecast_rain,
        "max_forecast_probability_pct": max_probability,
        "heavy_rain_threshold_mm": thresholds.weather_rule_heavy_rain_mm,
        "probability_threshold_pct": thresholds.weather_rule_rain_probability_pct,
        "basis": "observed" if rain_observed else "forecast" if rain_forecast else "none",
    }

    wind = snapshot.current.wind_speed_kmh
    gust = snapshot.current.wind_gusts_kmh
    wind_observed = (wind is not None and wind >= thresholds.weather_rule_strong_wind_kmh) or (
        gust is not None and gust >= thresholds.weather_rule_strong_gust_kmh
    )
    wind_evidence = {
        "observed_wind_kmh": wind,
        "observed_gust_kmh": gust,
        "wind_threshold_kmh": thresholds.weather_rule_strong_wind_kmh,
        "gust_threshold_kmh": thresholds.weather_rule_strong_gust_kmh,
    }

    temperature = snapshot.current.temperature_c
    hot = temperature is not None and temperature >= thresholds.weather_rule_high_temperature_c
    heat_evidence = {
        "observed_temperature_c": temperature,
        "high_temperature_threshold_c": thresholds.weather_rule_high_temperature_c,
    }

    signals: list[dict[str, Any]] = []

    if rain_any:
        rain_relevance = "LIKELY" if rain_observed else "POSSIBLE"
        if category in {"DRAINAGE", "SANITATION"} or "drain" in tags or "waterlogging" in tags:
            signals.append(
                _signal(
                    "R-RAIN-DRAINAGE",
                    "AGGRAVATION",
                    rain_relevance,
                    "Ongoing or forecast precipitation may worsen water accumulation "
                    "or overflow where drainage is already impaired.",
                    rain_evidence,
                )
            )
        if category == "ROADS" or "road_damage" in tags:
            signals.append(
                _signal(
                    "R-RAIN-ROADS",
                    "AGGRAVATION",
                    "POSSIBLE",
                    "Precipitation may further deteriorate the road surface or reduce visibility.",
                    rain_evidence,
                )
            )
        if "electrical" in tags or category == "UTILITIES":
            signals.append(
                _signal(
                    "R-RAIN-ELECTRICAL",
                    "SECONDARY_HAZARD",
                    "POSSIBLE",
                    "If exposed conductors are present, precipitation may create an "
                    "electrical safety concern. This is not confirmed by weather data.",
                    rain_evidence,
                )
            )
        if "debris" in tags and category == "ENVIRONMENT":
            signals.append(
                _signal(
                    "R-RAIN-DEBRIS_RUNOFF",
                    "SECONDARY_HAZARD",
                    "POSSIBLE",
                    "Rain may move loose debris into nearby drains or waterways.",
                    rain_evidence,
                )
            )

    if wind_observed:
        if "tree" in tags:
            signals.append(
                _signal(
                    "R-WIND-TREE",
                    "SECONDARY_HAZARD",
                    "POSSIBLE",
                    "Strong wind or gusts may worsen an existing tree obstruction "
                    "or cause further breakage.",
                    wind_evidence,
                )
            )
        if category == "ROADS":
            signals.append(
                _signal(
                    "R-WIND-ROADS",
                    "SECONDARY_HAZARD",
                    "POSSIBLE",
                    "Strong wind may move debris onto the affected road area.",
                    wind_evidence,
                )
            )

    if hot and category in {"HEALTH", "PUBLIC_SAFETY"}:
        signals.append(
            _signal(
                "R-HEAT-EXPOSURE",
                "CONTEXT",
                "POSSIBLE",
                "Unusually high temperature may increase heat exposure for people "
                "at or near this incident.",
                heat_evidence,
            )
        )

    return {
        "rule_engine_version": RULE_ENGINE_VERSION,
        "status": "OK",
        "category": category,
        "context_tags": tags,
        "weather_summary": {
            "current": snapshot.current.as_dict(),
            "forecast_hours": len(snapshot.forecast),
            "forecast_from": snapshot.forecast[0].as_dict()["time"] if snapshot.forecast else None,
            "forecast_to": snapshot.forecast[-1].as_dict()["time"] if snapshot.forecast else None,
            "data_quality": snapshot.data_quality,
        },
        "signals": signals,
        "potential_aggravation": [
            item["explanation"] for item in signals if item["kind"] == "AGGRAVATION"
        ],
        "potential_secondary_hazards": [
            item["explanation"] for item in signals if item["kind"] == "SECONDARY_HAZARD"
        ],
        "context_notes": [item["explanation"] for item in signals if item["kind"] == "CONTEXT"],
        "uncertainty": UNCERTAINTY,
        "decision_note": DECISION_NOTE,
        "rule_ids": [item["rule_id"] for item in signals],
    }
