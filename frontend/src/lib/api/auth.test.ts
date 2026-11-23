import { afterEach, describe, expect, it, vi } from "vitest";

import {
  fetchCurrentProfile,
  provisionProfile,
  updateOwnProfile,
} from "@/lib/api/auth";
import type { Profile } from "@/types/auth";

const profile: Profile = {
  id: "11111111-1111-4111-8111-111111111111",
  full_name: "Citizen User",
  phone: null,
  role: "CITIZEN",
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("auth API client", () => {
  it("sends the access token only in the Authorization header", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(profile));
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchCurrentProfile("access-token-value")).resolves.toEqual(
      profile,
    );

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://localhost:8000/api/v1/auth/me");
    expect(new Headers(init.headers).get("Authorization")).toBe(
      "Bearer access-token-value",
    );
    expect(JSON.stringify(init.body ?? "")).not.toContain("access-token-value");
  });

  it("provisions a profile without accepting a role from the browser", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(profile));
    vi.stubGlobal("fetch", fetchMock);

    await provisionProfile("token", "New Citizen");

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({ full_name: "New Citizen" });
    expect(String(init.body)).not.toContain("role");
  });

  it("updates only the supplied non-privileged fields", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(profile));
    vi.stubGlobal("fetch", fetchMock);

    await updateOwnProfile("token", { phone: "+1 555 0100" });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(String(init.body))).toEqual({ phone: "+1 555 0100" });
  });

  it("surfaces safe backend errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            error: {
              code: "profile_required",
              message: "No CivicFlow profile exists.",
            },
          },
          403,
        ),
      ),
    );

    await expect(fetchCurrentProfile("token")).rejects.toMatchObject({
      status: 403,
      code: "profile_required",
    });
  });
});
