import { ApiError } from "@/lib/api/client";

/** Return a usable access token or fail with a precise authentication error. */
export function requireAccessToken(token: string | null | undefined): string {
  if (!token || token.trim().length === 0) {
    throw new ApiError("Your session has expired. Please sign in again.", {
      status: 401,
      code: "not_authenticated",
    });
  }
  return token;
}

/** Build the Authorization header for an authenticated backend request. */
export function authorizationHeader(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}` };
}
