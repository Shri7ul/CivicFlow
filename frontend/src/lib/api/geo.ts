import type { ApiRequester } from "@/lib/api/incidents";
import type {
  DhakaReadinessReport,
  GeographicContextList,
  PilotAreaSelection,
} from "@/types/geography";

const BASE = "/api/v1/governance/geography";

export function getGeographicContexts(
  request: ApiRequester,
  options: { signal?: AbortSignal } = {},
): Promise<GeographicContextList> {
  return request<GeographicContextList>(`${BASE}/contexts`, {
    signal: options.signal,
  });
}

export function getPilotAreaCandidates(
  request: ApiRequester,
  options: { signal?: AbortSignal } = {},
): Promise<PilotAreaSelection> {
  return request<PilotAreaSelection>(`${BASE}/pilot-areas`, {
    signal: options.signal,
  });
}

export function getDhakaReadiness(
  request: ApiRequester,
  options: { signal?: AbortSignal } = {},
): Promise<DhakaReadinessReport> {
  return request<DhakaReadinessReport>(`${BASE}/readiness/dhaka`, {
    signal: options.signal,
  });
}

export function getScopedWorkspace(
  request: ApiRequester,
  geographicContext: string,
  options: { signal?: AbortSignal } = {},
): Promise<Record<string, unknown>> {
  const params = new URLSearchParams({ geographic_context: geographicContext });
  return request<Record<string, unknown>>(
    `/api/v1/governance/evidence/workspace?${params.toString()}`,
    { signal: options.signal },
  );
}
