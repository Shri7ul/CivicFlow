import { afterEach, describe, expect, it, vi } from "vitest";

import { apiFetch, ApiError, getApiBaseUrl } from "./client";

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

describe("getApiBaseUrl", () => {
  it("falls back to the local API when no environment value is set", () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "");
    expect(getApiBaseUrl()).toBe("http://localhost:8000");
  });

  it("trims trailing slashes from a configured base URL", () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.test/");
    expect(getApiBaseUrl()).toBe("https://api.example.test");
  });
});

describe("apiFetch", () => {
  it("requests the configured API and returns parsed JSON", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test:9000");
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValue(jsonResponse({ ok: true }));

    const result = await apiFetch<{ ok: boolean }>("/v1/test");

    expect(result).toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test:9000/v1/test",
      expect.objectContaining({
        signal: expect.any(AbortSignal),
        headers: expect.any(Headers),
      }),
    );
  });

  it("throws a typed error for non-success responses", async () => {
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValue(
      jsonResponse(
        { error: { code: "not_found", message: "Missing resource" } },
        404,
      ),
    );

    await expect(apiFetch("/missing")).rejects.toMatchObject({
      name: "ApiError",
      status: 404,
      code: "not_found",
      message: "Missing resource",
    });
  });

  it("falls back to a status message for non-JSON errors", async () => {
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValue(new Response("bad gateway", { status: 502 }));

    await expect(apiFetch("/broken")).rejects.toMatchObject({
      status: 502,
      code: "api_error",
      message: "The API responded with status 502.",
    });
  });

  it("maps network failures to a safe ApiError", async () => {
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockRejectedValue(new TypeError("fetch failed"));

    await expect(apiFetch("/health")).rejects.toMatchObject({
      code: "network_error",
    });
    await expect(apiFetch("/health")).rejects.toBeInstanceOf(ApiError);
  });
});
