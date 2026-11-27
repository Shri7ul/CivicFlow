import type { Profile } from "@/types/auth";
import { apiFetch, ApiError } from "@/lib/api/client";

function authorization(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}` };
}

export function fetchCurrentProfile(token: string): Promise<Profile> {
  return apiFetch<Profile>("/api/v1/auth/me", {
    headers: authorization(token),
  });
}

/**
 * Load the caller's profile, provisioning a CITIZEN profile only when the
 * backend explicitly reports that this verified identity has none. Existing
 * profiles are reused; no role is ever supplied by the browser.
 */
export async function loadOrProvisionProfile(
  token: string,
  fullName?: string | null,
): Promise<Profile> {
  try {
    return await fetchCurrentProfile(token);
  } catch (error) {
    if (
      error instanceof ApiError &&
      error.status === 403 &&
      error.code === "profile_required"
    ) {
      return provisionProfile(token, fullName);
    }
    throw error;
  }
}

export function provisionProfile(
  token: string,
  fullName?: string | null,
): Promise<Profile> {
  const body =
    fullName && fullName.trim().length > 0
      ? JSON.stringify({ full_name: fullName.trim() })
      : JSON.stringify({});
  return apiFetch<Profile>("/api/v1/auth/provision", {
    method: "POST",
    headers: {
      ...authorization(token),
      "Content-Type": "application/json",
    },
    body,
  });
}

export function updateOwnProfile(
  token: string,
  changes: { full_name?: string; phone?: string | null },
): Promise<Profile> {
  return apiFetch<Profile>("/api/v1/auth/me", {
    method: "PATCH",
    headers: {
      ...authorization(token),
      "Content-Type": "application/json",
    },
    body: JSON.stringify(changes),
  });
}
