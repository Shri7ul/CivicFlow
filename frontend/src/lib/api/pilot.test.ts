import { describe, expect, it, vi } from "vitest";

import type { ApiRequester } from "@/lib/api/incidents";
import {
  decideRiskReview,
  getCorrelationMetrics,
  getPilotReadiness,
  getReadiness,
  getRiskReviews,
  getTraceRuns,
  reviewCorrelationCandidate,
  transitionPilot,
  validateInfrastructureSource,
} from "@/lib/api/pilot";

describe("Phase 10 API helpers", () => {
  it("reads readiness and bounded review queues", async () => {
    const request = vi.fn(async (path: string) => ({ path })) as unknown as ApiRequester;

    await getReadiness(request);
    await getPilotReadiness(request, "pilot-1");
    await getRiskReviews(request, { status: "UNREVIEWED", limit: 10, offset: 20 });
    await getTraceRuns(request);

    expect(request).toHaveBeenNthCalledWith(
      1,
      "/api/v1/governance/readiness",
      { signal: undefined },
    );
    expect(request).toHaveBeenNthCalledWith(
      2,
      "/api/v1/governance/pilots/pilot-1/readiness",
    );
    expect(request).toHaveBeenNthCalledWith(
      3,
      "/api/v1/governance/reviews?limit=10&offset=20&status=UNREVIEWED",
      { signal: undefined },
    );
    expect(request).toHaveBeenNthCalledWith(
      4,
      "/api/v1/governance/traceability/runs?limit=25",
      { signal: undefined },
    );
  });

  it("posts explicit lifecycle and reviewer decisions", async () => {
    const request = vi.fn(async () => ({ id: "record-1" })) as unknown as ApiRequester;

    await transitionPilot(request, "pilot-1", "APPROVE", "Independent review");
    await decideRiskReview(request, "case-1", {
      status: "ACCEPTED",
      note: "Checked against source incidents.",
    });
    await reviewCorrelationCandidate(request, "candidate-1", {
      decision: "DUPLICATE",
      explanation: "Same address and incident description.",
    });
    await validateInfrastructureSource(request, "source-1", {
      status: "VERIFIED",
      note: "License and checksum checked.",
    });

    expect(request).toHaveBeenNthCalledWith(
      1,
      "/api/v1/governance/pilots/pilot-1/transition",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "APPROVE",
          note: "Independent review",
        }),
      },
    );
    expect(request).toHaveBeenNthCalledWith(
      2,
      "/api/v1/governance/reviews/case-1/decisions",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          status: "ACCEPTED",
          note: "Checked against source incidents.",
        }),
      },
    );
    expect(request).toHaveBeenNthCalledWith(
      3,
      "/api/v1/governance/correlation/candidates/candidate-1/reviews",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          decision: "DUPLICATE",
          explanation: "Same address and incident description.",
        }),
      },
    );
    expect(request).toHaveBeenNthCalledWith(
      4,
      "/api/v1/governance/infrastructure/sources/source-1/validation",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          status: "VERIFIED",
          note: "License and checksum checked.",
        }),
      },
    );
  });

  it("encodes the correlation universe in the metrics query", async () => {
    const request = vi.fn(async () => ({ metrics: {} })) as unknown as ApiRequester;

    await getCorrelationMetrics(request, "nyc 311/universe");

    expect(request).toHaveBeenCalledWith(
      "/api/v1/governance/correlation/metrics?universe_key=nyc%20311%2Funiverse",
    );
  });
});
