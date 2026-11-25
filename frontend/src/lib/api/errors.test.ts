import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchCurrentProfile } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import { profileLoadMessage } from "@/lib/api/errors";

const fetchMock = vi.fn();

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const PROFILE = {
  id: "11111111-1111-4111-8111-111111111111",
  full_name: "Test User",
  email: "user@example.test",
  role: "CITIZEN",
  is_active: true,
  phone: null,
};

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  fetchMock.mockReset();
});

describe("profileLoadMessage", () => {
  it("reports HTTP 401 as an expired session, never as an unreachable backend", () => {
    const message = profileLoadMessage(new ApiError("Authentication required.", { status: 401 }));
    expect(message).toContain("session has expired");
    expect(message).not.toContain("Unable to reach");
  });

  it("reports HTTP 403 as authorization failure, never as an unreachable backend", () => {
    const message = profileLoadMessage(new ApiError("Forbidden", { status: 403 }));
    expect(message).toContain("permission");
    expect(message).not.toContain("Unable to reach");
  });

  it("reports HTTP 5xx as a temporary API failure", () => {
    const message = profileLoadMessage(new ApiError("Internal error", { status: 503 }));
    expect(message).toContain("temporarily unavailable");
  });

  it("reports genuine network failures as unreachable backend", () => {
    const message = profileLoadMessage(
      new ApiError("Unable to reach the CivicFlow API.", { code: "network_error" }),
    );
    expect(message).toContain("Unable to reach");
  });

  it("reports malformed successful responses as invalid responses", () => {
    const message = profileLoadMessage(new ApiError("bad JSON", { code: "invalid_response" }));
    expect(message).toContain("invalid response");
    expect(message).not.toContain("Unable to reach");
  });
});

describe("fetchCurrentProfile", () => {
  it("sends the bearer token to the versioned profile endpoint", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.test");
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValue(jsonResponse(PROFILE));

    const profile = await fetchCurrentProfile("access-token-123");

    expect(profile).toEqual(PROFILE);
    const call = fetchMock.mock.calls.at(0);
    expect(call).toBeDefined();
    expect(call?.[0]).toBe("https://api.example.test/api/v1/auth/me");
    const headers = call?.[1]?.headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer access-token-123");
  });

  it("keeps HTTP 401 as a structured authentication failure", async () => {
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValue(
      jsonResponse({ error: { code: "authentication_failed", message: "Authentication required." } }, 401),
    );

    await expect(fetchCurrentProfile("expired-token")).rejects.toMatchObject({
      status: 401,
      code: "authentication_failed",
    });
  });

  it("keeps HTTP 403 as a structured authorization failure", async () => {
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValue(
      jsonResponse({ error: { code: "profile_required", message: "Profile required." } }, 403),
    );

    await expect(fetchCurrentProfile("valid-token")).rejects.toMatchObject({
      status: 403,
      code: "profile_required",
    });
  });

  it("keeps HTTP 5xx as a server error with its status", async () => {
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValue(new Response("bad gateway", { status: 502 }));

    await expect(fetchCurrentProfile("valid-token")).rejects.toMatchObject({
      status: 502,
      code: "api_error",
    });
  });

  it("classifies a fetch rejection as a network error", async () => {
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockRejectedValue(new TypeError("fetch failed"));

    await expect(fetchCurrentProfile("valid-token")).rejects.toMatchObject({
      code: "network_error",
    });
  });

  it("classifies an unparsable 200 response as invalid_response, not network_error", async () => {
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValue(new Response("not json", { status: 200 }));

    await expect(fetchCurrentProfile("valid-token")).rejects.toMatchObject({
      status: 200,
      code: "invalid_response",
    });
  });
});
