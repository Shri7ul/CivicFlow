import { describe, expect, it } from "vitest";

import {
  getDhakaReadiness,
  getGeographicContexts,
  getPilotAreaCandidates,
  getScopedWorkspace,
} from "./geo";
import type { ApiRequester } from "./incidents";

function recordingRequester(): { request: ApiRequester; calls: string[] } {
  const calls: string[] = [];
  const request = (async (path: string) => {
    calls.push(path);
    return {};
  }) as ApiRequester;
  return { request, calls };
}

describe("geography API client", () => {
  it("uses the staff geography endpoints", async () => {
    const { request, calls } = recordingRequester();
    await getGeographicContexts(request);
    await getDhakaReadiness(request);
    await getPilotAreaCandidates(request);
    expect(calls).toEqual([
      "/api/v1/governance/geography/contexts",
      "/api/v1/governance/geography/readiness/dhaka",
      "/api/v1/governance/geography/pilot-areas",
    ]);
  });

  it("passes the geographic context as a server-side query filter", async () => {
    const { request, calls } = recordingRequester();
    await getScopedWorkspace(request, "BD-DHAKA");
    expect(calls[0]).toBe(
      "/api/v1/governance/evidence/workspace?geographic_context=BD-DHAKA",
    );
  });
});
