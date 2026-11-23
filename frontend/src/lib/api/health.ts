import { apiFetch, ApiError } from "@/lib/api/client";
import type { BackendHealth } from "@/types/health";

export const HEALTH_ENDPOINT = "/api/v1/health";

export async function fetchBackendHealth(): Promise<BackendHealth> {
  const health = await apiFetch<BackendHealth>(HEALTH_ENDPOINT, {
    cache: "no-store",
    timeoutMs: 5000,
  });

  if (health.status !== "healthy" || typeof health.service !== "string") {
    throw new ApiError("The API returned an unexpected health response.", {
      code: "invalid_response",
    });
  }

  return health;
}
