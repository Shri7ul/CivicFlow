import { describe, expect, it, vi } from "vitest";

import {
  compareDecisionStrategies,
  getDecisionConfig,
  simulateDecisionScenario,
} from "@/lib/api/decisions";
import type { ApiRequester } from "@/lib/api/incidents";

describe("decision API helpers", () => {
  it("loads configuration and posts a simulation", async () => {
    const request = vi.fn(async (path: string) => {
      if (path.endsWith("/config")) return { model_version: "decision-v1" };
      return { simulation_id: "sim-1" };
    }) as unknown as ApiRequester;
    await getDecisionConfig(request);
    await simulateDecisionScenario(request, "scenario-1", "BALANCED");
    expect(request).toHaveBeenNthCalledWith(1, "/api/v1/decisions/config");
    expect(request).toHaveBeenNthCalledWith(
      2,
      "/api/v1/decisions/scenarios/scenario-1/simulate",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("posts a strategy comparison list", async () => {
    const request = vi.fn(async () => ({
      comparison: { winner: "BALANCED" },
    })) as unknown as ApiRequester;
    await compareDecisionStrategies(request, "scenario-1", [
      "PRIORITY",
      "BALANCED",
    ]);
    const mock = request as unknown as {
      mock: { calls: [string, { body: string }][] };
    };
    const options = mock.mock.calls[0]![1];
    expect(JSON.parse(options.body)).toEqual({
      strategies: ["PRIORITY", "BALANCED"],
    });
  });
});
