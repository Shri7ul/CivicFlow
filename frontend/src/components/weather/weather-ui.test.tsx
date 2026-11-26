import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import {
  WeatherAssessmentCard,
  metric,
  timestamp,
} from "./weather-ui";
import type { WeatherAssessment } from "@/types/weather";

function assessment(overrides: Partial<WeatherAssessment> = {}): WeatherAssessment {
  return {
    id: "assessment-1",
    incident_id: "incident-1",
    status: "OK",
    provider: "open-meteo",
    retrieved_at: "2026-11-26T20:15:00+00:00",
    observed_at: "2026-11-26T20:00:00+00:00",
    forecast_from: "2026-11-26T20:00:00+00:00",
    forecast_to: "2026-11-27T08:00:00+00:00",
    weather_snapshot: {
      provider: "open-meteo",
      latitude: 23.81,
      longitude: 90.41,
      retrieved_at: "2026-11-26T20:15:00+00:00",
      data_quality: "OK",
      current: {
        observed_at: "2026-11-26T20:00:00+00:00",
        temperature_c: 29.5,
        precipitation_mm: 12.4,
        wind_speed_kmh: 22.0,
        wind_gusts_kmh: 36.0,
        weather_code: 63,
      },
      forecast: [
        {
          time: "2026-11-26T21:00:00+00:00",
          temperature_c: 28.0,
          precipitation_mm: 9.0,
          precipitation_probability_pct: 85,
        },
      ],
    },
    assessment: {
      status: "OK",
      rule_engine_version: "weather-impact-v1",
      category: "DRAINAGE",
      context_tags: ["drain"],
      weather_summary: {
        current: {
          observed_at: "2026-11-26T20:00:00+00:00",
          temperature_c: 29.5,
          precipitation_mm: 12.4,
          wind_speed_kmh: 22.0,
          wind_gusts_kmh: 36.0,
          weather_code: 63,
        },
        forecast_hours: 1,
        forecast_from: "2026-11-26T20:00:00+00:00",
        forecast_to: "2026-11-27T08:00:00+00:00",
        data_quality: "OK",
      },
      signals: [
        {
          rule_id: "R-RAIN-DRAINAGE",
          kind: "AGGRAVATION",
          relevance: "LIKELY",
          explanation: "Precipitation may worsen water accumulation.",
          evidence: { observed_precipitation_mm: 12.4 },
        },
      ],
      potential_aggravation: ["Precipitation may worsen water accumulation."],
      potential_secondary_hazards: [],
      context_notes: [],
      uncertainty: "Model estimates; correlation does not establish causation.",
      decision_note: "Advisory input for authorized staff review only.",
      rule_ids: ["R-RAIN-DRAINAGE"],
    },
    rule_engine_version: "weather-impact-v1",
    error_code: null,
    refresh_count: 1,
    last_attempt_at: "2026-11-26T20:15:00+00:00",
    stale: false,
    source_attribution: "Weather data by Open-Meteo.com (CC BY 4.0)",
    created_at: "2026-11-26T20:15:00+00:00",
    updated_at: "2026-11-26T20:15:00+00:00",
    ...overrides,
  };
}

describe("weather assessment presentation", () => {
  it("shows observed, forecast, relevance, provenance and limitations to admins", () => {
    const onRefresh = vi.fn();
    const markup = renderToStaticMarkup(
      <WeatherAssessmentCard assessment={assessment()} variant="admin" onRefresh={onRefresh} />,
    );
    expect(markup).toContain("Weather impact context");
    expect(markup).toContain("29.5°C");
    expect(markup).toContain("12.4 mm");
    expect(markup).toContain("85% chance");
    expect(markup).toContain("Precipitation may worsen water accumulation.");
    expect(markup).toContain("R-RAIN-DRAINAGE");
    expect(markup).toContain("Why this was flagged");
    expect(markup).toContain("Open-Meteo.com");
    expect(markup).toContain("causation");
    expect(markup).toContain("Reassess weather");
  });

  it("keeps the citizen view concise and hides internal rule identifiers", () => {
    const markup = renderToStaticMarkup(
      <WeatherAssessmentCard assessment={assessment()} variant="citizen" />,
    );
    expect(markup).toContain("Weather impact context");
    expect(markup).toContain("12.4 mm");
    expect(markup).toContain("causation");
    expect(markup).not.toContain("R-RAIN-DRAINAGE");
    expect(markup).not.toContain("Why this was flagged");
    expect(markup).not.toContain("Reassess weather");
  });

  it("labels stale data without presenting it as current", () => {
    const stale = assessment({
      status: "STALE",
      stale: true,
      assessment: {
        ...assessment().assessment,
        status: "STALE",
        stale_reason: "provider_timeout",
      },
    });
    const markup = renderToStaticMarkup(
      <WeatherAssessmentCard assessment={stale} variant="worker" />,
    );
    expect(markup).toContain("stale");
    expect(markup).toContain("last known conditions");
    expect(markup).toContain("could not be retrieved");
  });

  it("renders explicit unavailable and disabled states without fake numbers", () => {
    const failed = renderToStaticMarkup(
      <WeatherAssessmentCard
        assessment={assessment({
          status: "ERROR",
          weather_snapshot: {} as never,
          assessment: {
            ...assessment().assessment,
            status: "ERROR",
            explanation: "No weather data was retrieved.",
            signals: [],
          },
        })}
        variant="citizen"
      />,
    );
    expect(failed).toContain("Unavailable");
    expect(failed).toContain("No weather data was retrieved.");
    expect(failed).not.toContain("29.5°C");

    const disabled = renderToStaticMarkup(
      <WeatherAssessmentCard
        assessment={assessment({ status: "DISABLED" })}
        variant="citizen"
      />,
    );
    expect(disabled).toContain("Not enabled");
  });

  it("renders loading, error and empty states", () => {
    const loading = renderToStaticMarkup(
      <WeatherAssessmentCard assessment={null} variant="admin" loading />,
    );
    expect(loading).toContain("Loading weather context");
    const error = renderToStaticMarkup(
      <WeatherAssessmentCard
        assessment={null}
        variant="admin"
        error="Provider unavailable"
        onRetry={() => undefined}
      />,
    );
    expect(error).toContain("Provider unavailable");
    expect(error).toContain("Retry weather context");
    const empty = renderToStaticMarkup(
      <WeatherAssessmentCard assessment={null} variant="admin" />,
    );
    expect(empty).toContain("No weather assessment is available");
  });

  it("shows unknown values as a dash rather than zero", () => {
    expect(metric(null, " mm")).toBe("—");
    expect(metric(undefined, "°C")).toBe("—");
    expect(metric(0, " mm")).toBe("0 mm");
    expect(timestamp(null)).toBe("—");
  });
});
