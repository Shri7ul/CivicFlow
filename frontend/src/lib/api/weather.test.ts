import { describe, expect, it, vi } from "vitest";

import type { ApiRequester } from "@/lib/api/incidents";
import {
  getWeatherAssessment,
  getWeatherConfig,
  refreshWeatherAssessment,
} from "@/lib/api/weather";

type Call = [string, { method?: string; body?: string } | undefined];

function recorder() {
  const request = vi.fn(async () => ({})) as unknown as ApiRequester;
  const calls = (request as unknown as { mock: { calls: Call[] } }).mock.calls;
  return { request, at: (index: number): Call => calls[index]! };
}

describe("weather API contract", () => {
  it("reads an assessment for the exact incident", async () => {
    const { request, at } = recorder();
    await getWeatherAssessment(request, "incident-1");
    expect(at(0)[0]).toBe(
      "/api/v1/weather/incidents/incident-1/assessment",
    );
  });

  it("forces a refresh with an optional reason", async () => {
    const { request, at } = recorder();
    await refreshWeatherAssessment(request, "incident-1", "routine review");
    await refreshWeatherAssessment(request, "incident-2");
    expect(at(0)[0]).toBe(
      "/api/v1/weather/incidents/incident-1/assessment/refresh",
    );
    expect(at(0)[1]?.method).toBe("POST");
    expect(JSON.parse(at(0)[1]!.body!)).toEqual({ reason: "routine review" });
    expect(JSON.parse(at(1)[1]!.body!)).toEqual({});
  });

  it("reads non-sensitive configuration", async () => {
    const { request, at } = recorder();
    await getWeatherConfig(request);
    expect(at(0)[0]).toBe("/api/v1/weather/config");
  });
});
