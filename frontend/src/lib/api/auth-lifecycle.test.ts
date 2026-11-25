import { afterEach, describe, expect, it, vi } from "vitest";

import { loadOrProvisionProfile } from "@/lib/api/auth";

const fetchMock = vi.fn();

const PROFILE = {
  id: "11111111-1111-4111-8111-111111111111",
  full_name: "CivicFlow user",
  email: "user@example.test",
  role: "CITIZEN",
  is_active: true,
  phone: null,
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function profileRequired(): Response {
  return jsonResponse(
    {
      error: {
        code: "profile_required",
        message: "No CivicFlow profile exists for this identity.",
      },
    },
    403,
  );
}

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  fetchMock.mockReset();
});

function stubFetch() {
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.test");
  vi.stubGlobal("fetch", fetchMock);
}

describe("profile load and provisioning lifecycle", () => {
  it("reuses an existing profile without calling provision", async () => {
    stubFetch();
    fetchMock.mockResolvedValueOnce(jsonResponse(PROFILE));

    const profile = await loadOrProvisionProfile("access-token");

    expect(profile).toEqual(PROFILE);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "https://api.example.test/api/v1/auth/me",
    );
  });

  it("provisions a verified new user when the profile is missing", async () => {
    stubFetch();
    fetchMock
      .mockResolvedValueOnce(profileRequired())
      .mockResolvedValueOnce(jsonResponse(PROFILE));

    const profile = await loadOrProvisionProfile("access-token");

    expect(profile).toEqual(PROFILE);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    const secondCall = fetchMock.mock.calls[1];
    expect(secondCall?.[0]).toBe(
      "https://api.example.test/api/v1/auth/provision",
    );
    expect(secondCall?.[1]?.method).toBe("POST");
    const headers = secondCall?.[1]?.headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer access-token");
    expect(secondCall?.[1]?.body).toBe("{}");
  });

  it("loads the profile successfully on a subsequent request after provisioning", async () => {
    stubFetch();
    fetchMock
      .mockResolvedValueOnce(profileRequired())
      .mockResolvedValueOnce(jsonResponse(PROFILE))
      .mockResolvedValueOnce(jsonResponse(PROFILE));

    await loadOrProvisionProfile("access-token");
    const reloaded = await loadOrProvisionProfile("access-token");

    expect(reloaded).toEqual(PROFILE);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[2]?.[0]).toBe(
      "https://api.example.test/api/v1/auth/me",
    );
  });

  it("never provisions on HTTP 401", async () => {
    stubFetch();
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        { error: { code: "authentication_failed", message: "Authentication required." } },
        401,
      ),
    );

    await expect(loadOrProvisionProfile("expired-token")).rejects.toMatchObject({
      status: 401,
      code: "authentication_failed",
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("never provisions on a 403 that is not profile_required", async () => {
    stubFetch();
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        { error: { code: "account_inactive", message: "This account is inactive." } },
        403,
      ),
    );

    await expect(loadOrProvisionProfile("access-token")).rejects.toMatchObject({
      status: 403,
      code: "account_inactive",
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("surfaces a provisioning HTTP 500 with its status", async () => {
    stubFetch();
    fetchMock
      .mockResolvedValueOnce(profileRequired())
      .mockResolvedValueOnce(
        jsonResponse(
          { error: { code: "internal_server_error", message: "An unexpected error occurred." } },
          500,
        ),
      );

    await expect(loadOrProvisionProfile("access-token")).rejects.toMatchObject({
      status: 500,
      code: "internal_server_error",
    });
  });

  it("surfaces a provisioning network failure as a network error", async () => {
    stubFetch();
    fetchMock
      .mockResolvedValueOnce(profileRequired())
      .mockRejectedValueOnce(new TypeError("fetch failed"));

    await expect(loadOrProvisionProfile("access-token")).rejects.toMatchObject({
      code: "network_error",
    });
  });

  it("does not accept a privileged role from the browser during provisioning", async () => {
    stubFetch();
    fetchMock
      .mockResolvedValueOnce(profileRequired())
      .mockResolvedValueOnce(jsonResponse(PROFILE));

    await loadOrProvisionProfile("access-token");

    const body = fetchMock.mock.calls[1]?.[1]?.body;
    expect(body).not.toContain("ADMIN");
    expect(body).not.toContain("role");
  });
});
