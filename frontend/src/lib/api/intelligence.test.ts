import { describe, expect, it, vi } from "vitest";

import {
  getIncidentIntelligence,
  listIncidentRelationships,
  listInfrastructureAssets,
  reviewIncidentRelationship,
} from "@/lib/api/intelligence";

describe("intelligence API helpers", () => {
  it("requests the incident intelligence endpoint with an abort signal", async () => {
    const request = vi.fn(async () => ({ incident_id: "incident-1" }));
    const controller = new AbortController();

    await getIncidentIntelligence(request as never, "incident-1", {
      signal: controller.signal,
    });

    expect(request).toHaveBeenCalledWith(
      "/api/v1/incidents/incident-1/intelligence",
      { signal: controller.signal },
    );
  });

  it("lists and reviews relationships with JSON review payloads", async () => {
    const request = vi.fn(async () => []);
    await listIncidentRelationships(request as never, "incident-1");
    await reviewIncidentRelationship(request as never, "incident-1", {
      other_incident_id: "incident-2",
      relationship_type: "DUPLICATE",
      status: "CONFIRMED",
      confidence: 0.82,
      signals: { source: "incident_intelligence" },
      note: "Same drain.",
    });

    const calls = request.mock.calls as unknown as Array<[string, RequestInit]>;
    const first = calls[0]!;
    const second = calls[1]!;
    expect(first[0]).toBe("/api/v1/incidents/incident-1/relationships");
    const [path, options] = second;
    expect(path).toBe("/api/v1/incidents/incident-1/relationships");
    expect(options.method).toBe("POST");
    expect(JSON.parse(String(options.body))).toMatchObject({
      other_incident_id: "incident-2",
      relationship_type: "DUPLICATE",
      status: "CONFIRMED",
    });
  });

  it("lists the bounded infrastructure reference set", async () => {
    const request = vi.fn(async () => []);
    await listInfrastructureAssets(request as never);
    expect(request).toHaveBeenCalledWith(
      "/api/v1/infrastructure/assets?limit=100",
    );
  });
});
