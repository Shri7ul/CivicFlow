import { describe, expect, it, vi } from "vitest";

import { ApiError, apiFetch } from "@/lib/api/client";

describe("apiFetch", () => {
  it("preserves structured API error codes", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            error: { code: "incident_not_found", message: "Incident not found." },
          }),
          { status: 404, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    await expect(apiFetch("/api/v1/incidents/missing")).rejects.toMatchObject({
      name: "ApiError",
      status: 404,
      code: "incident_not_found",
      message: "Incident not found.",
    });
    vi.unstubAllGlobals();
  });

  it("wraps network failures", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Promise.reject(new Error("offline"))),
    );

    await expect(apiFetch("/api/v1/health")).rejects.toBeInstanceOf(ApiError);
    vi.unstubAllGlobals();
  });
});
