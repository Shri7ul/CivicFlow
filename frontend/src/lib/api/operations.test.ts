import { describe, expect, it, vi } from "vitest";

import {
  decideReview,
  evaluateAlerts,
  getOperationsDashboard,
  submitScenarioReview,
} from "@/lib/api/operations";
import type { ApiRequester } from "@/lib/api/incidents";

describe("operations API helpers", () => {
  it("loads dashboard data and evaluates alert rules", async () => {
    const request = vi.fn(async (path: string) => {
      if (path.endsWith("/dashboard")) return { health: { database: true } };
      return [];
    }) as unknown as ApiRequester;
    await getOperationsDashboard(request);
    await evaluateAlerts(request);
    expect(request).toHaveBeenNthCalledWith(1, "/api/v1/operations/dashboard");
    expect(request).toHaveBeenNthCalledWith(
      2,
      "/api/v1/operations/alerts/evaluate",
      { method: "POST" },
    );
  });

  it("submits and decides a plan review", async () => {
    const request = vi.fn(async () => ({
      id: "review-1",
      execution_authorized: false,
    })) as unknown as ApiRequester;
    await submitScenarioReview(request, "scenario-1", "sim-1", "review");
    await decideReview(request, "review-1", "APPROVED", "approved");
    const mock = request as unknown as {
      mock: { calls: [string, { body: string }][] };
    };
    expect(JSON.parse(mock.mock.calls[0]![1].body)).toEqual({
      simulation_id: "sim-1",
      title: "Plan review",
      comment: "review",
    });
    expect(JSON.parse(mock.mock.calls[1]![1].body)).toEqual({
      decision: "APPROVED",
      comment: "approved",
    });
  });
});
