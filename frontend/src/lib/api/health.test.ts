import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchBackendHealth, HEALTH_ENDPOINT } from "./health";

const fetchMock = vi.fn();

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  fetchMock.mockReset();
});

describe("fetchBackendHealth", () => {
  it("calls the versioned health endpoint without caching", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValue(
      jsonResponse({
        status: "healthy",
        service: "CivicFlow API",
        environment: "testing",
        version: "v1",
      }),
    );

    const health = await fetchBackendHealth();

    expect(health.service).toBe("CivicFlow API");
    expect(fetchMock).toHaveBeenCalledWith(
      `http://localhost:8000${HEALTH_ENDPOINT}`,
      expect.objectContaining({ cache: "no-store" }),
    );
  });

  it("rejects an unexpected payload instead of assuming health", async () => {
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValue(
      jsonResponse({ status: "degraded", service: "CivicFlow API" }),
    );

    await expect(fetchBackendHealth()).rejects.toMatchObject({
      code: "invalid_response",
    });
  });
});
