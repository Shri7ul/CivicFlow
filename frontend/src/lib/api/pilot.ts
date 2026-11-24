import type { ApiRequester } from "@/lib/api/incidents";
import type {
  CorrelationCandidateList,
  CorrelationMetrics,
  InfrastructureCoverage,
  InfrastructureSource,
  InfrastructureSourceList,
  Pilot,
  PilotList,
  ReadinessReport,
  RiskReviewCase,
  RiskReviewList,
  RiskTrace,
  SimulationAudit,
  TraceRunSummary,
} from "@/types/pilot";

const JSON_HEADERS = { "Content-Type": "application/json" };

export function getReadiness(
  request: ApiRequester,
  options: { signal?: AbortSignal } = {},
): Promise<ReadinessReport> {
  return request<ReadinessReport>("/api/v1/governance/readiness", {
    signal: options.signal,
  });
}

export function getPilotReadiness(
  request: ApiRequester,
  pilotId: string,
): Promise<ReadinessReport> {
  return request<ReadinessReport>(
    "/api/v1/governance/pilots/" + pilotId + "/readiness",
  );
}

export function getPilots(
  request: ApiRequester,
  options: { signal?: AbortSignal; limit?: number; offset?: number } = {},
): Promise<PilotList> {
  const limit = options.limit ?? 25;
  const offset = options.offset ?? 0;
  return request<PilotList>(
    "/api/v1/governance/pilots?limit=" + limit + "&offset=" + offset,
    { signal: options.signal },
  );
}

export function getPilot(
  request: ApiRequester,
  pilotId: string,
): Promise<Pilot> {
  return request<Pilot>("/api/v1/governance/pilots/" + pilotId);
}

export function transitionPilot(
  request: ApiRequester,
  pilotId: string,
  action: string,
  note?: string,
): Promise<Pilot> {
  return request<Pilot>(
    "/api/v1/governance/pilots/" + pilotId + "/transition",
    {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify({ action, note: note || null }),
    },
  );
}

export function getRiskReviews(
  request: ApiRequester,
  options: {
    signal?: AbortSignal;
    status?: string;
    pilotId?: string;
    limit?: number;
    offset?: number;
  } = {},
): Promise<RiskReviewList> {
  const params = new URLSearchParams({
    limit: String(options.limit ?? 25),
    offset: String(options.offset ?? 0),
  });
  if (options.status) params.set("status", options.status);
  if (options.pilotId) params.set("pilot_id", options.pilotId);
  return request<RiskReviewList>(
    "/api/v1/governance/reviews?" + params.toString(),
    { signal: options.signal },
  );
}

export function getRiskReview(
  request: ApiRequester,
  caseId: string,
): Promise<RiskReviewCase> {
  return request<RiskReviewCase>("/api/v1/governance/reviews/" + caseId);
}

export function decideRiskReview(
  request: ApiRequester,
  caseId: string,
  payload: {
    status: string;
    note: string;
    requested_evidence?: string | null;
  },
): Promise<RiskReviewCase> {
  return request<RiskReviewCase>(
    "/api/v1/governance/reviews/" + caseId + "/decisions",
    {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify(payload),
    },
  );
}

export function getCorrelationCandidates(
  request: ApiRequester,
  options: {
    signal?: AbortSignal;
    universeKey?: string;
    reviewed?: boolean;
    limit?: number;
    offset?: number;
  } = {},
): Promise<CorrelationCandidateList> {
  const params = new URLSearchParams({
    limit: String(options.limit ?? 50),
    offset: String(options.offset ?? 0),
  });
  if (options.universeKey) params.set("universe_key", options.universeKey);
  if (options.reviewed !== undefined) {
    params.set("reviewed", String(options.reviewed));
  }
  return request<CorrelationCandidateList>(
    "/api/v1/governance/correlation/candidates?" + params.toString(),
    { signal: options.signal },
  );
}

export function getCorrelationMetrics(
  request: ApiRequester,
  universeKey: string,
): Promise<CorrelationMetrics> {
  return request<CorrelationMetrics>(
    "/api/v1/governance/correlation/metrics?universe_key=" +
      encodeURIComponent(universeKey),
  );
}

export function reviewCorrelationCandidate(
  request: ApiRequester,
  candidateId: string,
  payload: { decision: string; explanation: string; note?: string | null },
): Promise<{ id: string; decision: string }> {
  return request<{ id: string; decision: string }>(
    "/api/v1/governance/correlation/candidates/" + candidateId + "/reviews",
    {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify(payload),
    },
  );
}

export function getInfrastructureSources(
  request: ApiRequester,
  options: { signal?: AbortSignal; category?: string } = {},
): Promise<InfrastructureSourceList> {
  const params = new URLSearchParams({ limit: "100", offset: "0" });
  if (options.category) params.set("category", options.category);
  return request<InfrastructureSourceList>(
    "/api/v1/governance/infrastructure/sources?" + params.toString(),
    { signal: options.signal },
  );
}

export function getInfrastructureSource(
  request: ApiRequester,
  sourceId: string,
): Promise<InfrastructureSource> {
  return request<InfrastructureSource>(
    "/api/v1/governance/infrastructure/sources/" + sourceId,
  );
}

export function getInfrastructureCoverage(
  request: ApiRequester,
  options: { signal?: AbortSignal } = {},
): Promise<InfrastructureCoverage> {
  return request<InfrastructureCoverage>(
    "/api/v1/governance/infrastructure/coverage",
    { signal: options.signal },
  );
}

export function validateInfrastructureSource(
  request: ApiRequester,
  sourceId: string,
  payload: { status: string; note: string },
): Promise<InfrastructureSource> {
  return request<InfrastructureSource>(
    "/api/v1/governance/infrastructure/sources/" + sourceId + "/validation",
    {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify(payload),
    },
  );
}

export function getSimulationAudit(
  request: ApiRequester,
  options: { signal?: AbortSignal } = {},
): Promise<SimulationAudit> {
  return request<SimulationAudit>("/api/v1/governance/simulation/audit", {
    signal: options.signal,
  });
}

export function getTraceRuns(
  request: ApiRequester,
  options: { signal?: AbortSignal; limit?: number } = {},
): Promise<{ items: TraceRunSummary[] }> {
  return request<{ items: TraceRunSummary[] }>(
    "/api/v1/governance/traceability/runs?limit=" + (options.limit ?? 25),
    { signal: options.signal },
  );
}

export function getRiskTrace(
  request: ApiRequester,
  runId: string,
): Promise<RiskTrace> {
  return request<RiskTrace>(
    "/api/v1/governance/traceability/runs/" + runId,
  );
}

export async function downloadRiskTrace(
  request: ApiRequester,
  runId: string,
): Promise<RiskTrace> {
  return request<RiskTrace>(
    "/api/v1/governance/traceability/runs/" + runId + "/export?cell_limit=500",
  );
}
