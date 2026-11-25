import { ApiError } from "@/lib/api/client";

/**
 * Map backend failures to user-facing messages without ever describing an
 * HTTP 401/403 as a network outage. Public backend messages are preserved for
 * other statuses so operators can diagnose real API failures.
 */
export function profileLoadMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return "Your session has expired. Please sign in again.";
    }
    if (error.status === 403) {
      return "You do not have permission to access this CivicFlow profile.";
    }
    if (error.status !== undefined && error.status >= 500) {
      return "The CivicFlow API is temporarily unavailable. Please try again.";
    }
    if (error.code === "network_error" || error.code === "request_timeout") {
      return "Unable to reach the CivicFlow API. Check that the backend is running.";
    }
    if (error.code === "invalid_response") {
      return "The API returned an invalid response.";
    }
    return error.message;
  }
  return "Unable to load your CivicFlow profile. Please try again.";
}
