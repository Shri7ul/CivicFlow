import { describe, expect, it, vi } from "vitest";

import {
  getEvidenceSnapshot,
  getEvidenceSnapshots,
  getEvidenceWorkspace,
  getEvidenceUrl,
  listIncidentEvidence,
  uploadIncidentEvidence,
} from "@/lib/api/evidence";

describe("evidence API helpers", () => {
  it("appends every file to multipart form data", async () => {
    const request = vi.fn(async () => []);
    const first = new File(["a"], "../../a.png", { type: "image/png" });
    const second = new File(["b"], "b.jpg", { type: "image/jpeg" });

    await uploadIncidentEvidence(
      request as never,
      "incident-1",
      [first, second],
      () => undefined,
    );

    expect(request).toHaveBeenCalledTimes(1);
    const [path, body] = request.mock.calls[0] as unknown as [
      string,
      FormData,
    ];
    expect(path).toBe("/api/v1/incidents/incident-1/evidence");
    const names = (body as FormData).getAll("files").map((item) => {
      return (item as File).name;
    });
    expect(names).toEqual(["../../a.png", "b.jpg"]);
  });

  it("queries the Phase 11 evidence workspace with context by default", async () => {
    const request = vi.fn(async (_path: string) => {
      void _path;
      return { protocol: "phase11" };
    });
    await getEvidenceWorkspace(request as never);
    await getEvidenceWorkspace(request as never, { includeContext: false });
    expect(request.mock.calls[0]?.[0]).toBe(
      "/api/v1/governance/evidence/workspace?include_context=true",
    );
    expect(request.mock.calls[1]?.[0]).toBe(
      "/api/v1/governance/evidence/workspace?include_context=false",
    );
  });

  it("bounds and paginates the Phase 11 snapshot ledger", async () => {
    const request = vi.fn(async (_path: string) => {
      void _path;
      return { items: [] };
    });
    await getEvidenceSnapshots(request as never, { limit: 10, offset: 20 });
    await getEvidenceSnapshot(request as never, "snapshot-1");
    expect(request.mock.calls[0]?.[0]).toBe(
      "/api/v1/governance/evidence/snapshots?limit=10&offset=20",
    );
    expect(request.mock.calls[1]?.[0]).toBe(
      "/api/v1/governance/evidence/snapshots/snapshot-1",
    );
  });

  it("uses the base64-free signed URL endpoint and metadata list", async () => {
    const request = vi.fn(async (path: string) => ({ path }));
    await listIncidentEvidence(request as never, "incident-1");
    await getEvidenceUrl(request as never, "incident-1", "evidence-1");

    expect(request.mock.calls[0]?.[0]).toBe(
      "/api/v1/incidents/incident-1/evidence",
    );
    expect(request.mock.calls[1]?.[0]).toBe(
      "/api/v1/incidents/incident-1/evidence/evidence-1/url",
    );
  });
});
