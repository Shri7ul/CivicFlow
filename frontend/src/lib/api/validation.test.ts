import { describe, expect, it, vi } from "vitest";

import type { ApiRequester } from "@/lib/api/incidents";
import {
  getValidationExperiment,
  getValidationOverview,
  getValidationReport,
  runCorrelationValidation,
  runDecisionValidation,
  runRiskValidation,
} from "@/lib/api/validation";

describe("validation API helpers", () => {
  it("loads persisted overview, detail, and report paths", async () => {
    const request = vi.fn(async (path: string) => {
      if (path.endsWith("/overview")) {
        return { datasets: [], experiments: [], evidence_kinds: [], limitations: [] };
      }
      return { id: "experiment-1", path };
    }) as unknown as ApiRequester;

    await getValidationOverview(request);
    await getValidationExperiment(request, "experiment-1");
    await getValidationReport(request, "experiment-1");

    expect(request).toHaveBeenNthCalledWith(1, "/api/v1/validation/overview", {
      signal: undefined,
    });
    expect(request).toHaveBeenNthCalledWith(
      2,
      "/api/v1/validation/experiments/experiment-1",
    );
    expect(request).toHaveBeenNthCalledWith(
      3,
      "/api/v1/validation/experiments/experiment-1/report",
    );
  });

  it("posts bounded experiment runs with an extended timeout", async () => {
    const request = vi.fn(async () => ({ id: "experiment-1" })) as unknown as ApiRequester;

    await runRiskValidation(request, "dataset-1");
    await runCorrelationValidation(request);
    await runDecisionValidation(request);

    expect(request).toHaveBeenNthCalledWith(
      1,
      "/api/v1/validation/experiments/risk/dataset-1",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        timeoutMs: 180000,
      },
    );
    expect(request).toHaveBeenNthCalledWith(
      2,
      "/api/v1/validation/experiments/correlation",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        timeoutMs: 30000,
      },
    );
    expect(request).toHaveBeenNthCalledWith(
      3,
      "/api/v1/validation/experiments/decision",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        timeoutMs: 30000,
      },
    );
  });
});
