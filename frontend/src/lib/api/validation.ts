import type { ApiRequester } from "@/lib/api/incidents";
import type {
  ValidationExperimentDetail,
  ValidationOverview,
  ValidationReport,
} from "@/types/validation";

const JSON_HEADERS = { "Content-Type": "application/json" };

export function getValidationOverview(
  request: ApiRequester,
  options: { signal?: AbortSignal } = {},
): Promise<ValidationOverview> {
  return request<ValidationOverview>("/api/v1/validation/overview", {
    signal: options.signal,
  });
}

export function getValidationExperiment(
  request: ApiRequester,
  experimentId: string,
): Promise<ValidationExperimentDetail> {
  return request<ValidationExperimentDetail>(
    `/api/v1/validation/experiments/${experimentId}`,
  );
}

export function getValidationReport(
  request: ApiRequester,
  experimentId: string,
): Promise<ValidationReport> {
  return request<ValidationReport>(
    `/api/v1/validation/experiments/${experimentId}/report`,
  );
}

export function runRiskValidation(
  request: ApiRequester,
  datasetId: string,
): Promise<ValidationExperimentDetail> {
  return request<ValidationExperimentDetail>(
    `/api/v1/validation/experiments/risk/${datasetId}`,
    { method: "POST", headers: JSON_HEADERS, timeoutMs: 180000 },
  );
}

export function runCorrelationValidation(
  request: ApiRequester,
): Promise<ValidationExperimentDetail> {
  return request<ValidationExperimentDetail>(
    "/api/v1/validation/experiments/correlation",
    { method: "POST", headers: JSON_HEADERS, timeoutMs: 30000 },
  );
}

export function runDecisionValidation(
  request: ApiRequester,
): Promise<ValidationExperimentDetail> {
  return request<ValidationExperimentDetail>(
    "/api/v1/validation/experiments/decision",
    { method: "POST", headers: JSON_HEADERS, timeoutMs: 30000 },
  );
}
