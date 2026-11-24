import type { ApiRequestOptions } from "@/lib/api/client";
import type { ApiRequester } from "@/lib/api/incidents";
import type {
  RiskCellDetail,
  RiskCellsResponse,
  RiskConfig,
  RiskFilters,
  RiskGeoJSON,
  RiskInfrastructureSummary,
  RiskSummary,
  RiskTrendsResponse,
} from "@/types/risk";

export function buildRiskQuery(filters: RiskFilters = {}): string {
  const params = new URLSearchParams();
  if (filters.resolution) params.set("resolution", String(filters.resolution));
  if (filters.window) params.set("window", filters.window);
  if (typeof filters.minScore === "number") {
    params.set("min_score", String(filters.minScore));
  }
  if (filters.category) params.set("category", filters.category);
  const { minLatitude, minLongitude, maxLatitude, maxLongitude } = filters;
  if (
    typeof minLatitude === "number" &&
    typeof minLongitude === "number" &&
    typeof maxLatitude === "number" &&
    typeof maxLongitude === "number" &&
    minLatitude < maxLatitude &&
    minLongitude < maxLongitude
  ) {
    params.set("min_latitude", String(minLatitude));
    params.set("min_longitude", String(minLongitude));
    params.set("max_latitude", String(maxLatitude));
    params.set("max_longitude", String(maxLongitude));
  }
  if (filters.limit) params.set("limit", String(filters.limit));
  if (filters.offset) params.set("offset", String(filters.offset));
  return params.toString();
}

export function getRiskConfig(
  request: ApiRequester,
): Promise<RiskConfig> {
  return request<RiskConfig>("/api/v1/risk/config");
}

export function listRiskCells(
  request: ApiRequester,
  filters: RiskFilters = {},
  options: Pick<ApiRequestOptions, "signal"> = {},
): Promise<RiskCellsResponse> {
  return request<RiskCellsResponse>(`/api/v1/risk/cells?${buildRiskQuery(filters)}`, {
    signal: options.signal,
  });
}

export function getRiskCellsGeoJSON(
  request: ApiRequester,
  filters: RiskFilters = {},
  options: Pick<ApiRequestOptions, "signal"> = {},
): Promise<RiskGeoJSON> {
  const params = new URLSearchParams(buildRiskQuery(filters));
  params.set("format", "geojson");
  return request<RiskGeoJSON>(`/api/v1/risk/cells?${params.toString()}`, {
    signal: options.signal,
  });
}

export function getRiskSummary(
  request: ApiRequester,
  filters: RiskFilters = {},
  options: Pick<ApiRequestOptions, "signal"> = {},
): Promise<RiskSummary> {
  return request<RiskSummary>(`/api/v1/risk/summary?${buildRiskQuery(filters)}`, {
    signal: options.signal,
  });
}

export function getRiskCell(
  request: ApiRequester,
  cellId: string,
  filters: RiskFilters = {},
  options: Pick<ApiRequestOptions, "signal"> = {},
): Promise<RiskCellDetail> {
  const params = new URLSearchParams();
  if (filters.resolution) params.set("resolution", String(filters.resolution));
  if (filters.window) params.set("window", filters.window);
  return request<RiskCellDetail>(
    `/api/v1/risk/cells/${encodeURIComponent(cellId)}?${params.toString()}`,
    { signal: options.signal },
  );
}

export function getRiskTrends(
  request: ApiRequester,
  filters: RiskFilters = {},
): Promise<RiskTrendsResponse> {
  return request<RiskTrendsResponse>(
    `/api/v1/risk/trends?${buildRiskQuery(filters)}`,
  );
}

export function getRiskInfrastructureExposure(
  request: ApiRequester,
  filters: RiskFilters = {},
): Promise<RiskInfrastructureSummary> {
  return request<RiskInfrastructureSummary>(
    `/api/v1/risk/infrastructure-exposure?${buildRiskQuery(filters)}`,
  );
}

export type RiskDataQuality = {
  source_id: string;
  source_key: string;
  name: string;
  reliability: string;
  status: string;
  freshness_minutes: number | null;
  issues: string[];
};

export function getRiskDataQuality(
  request: ApiRequester,
): Promise<RiskDataQuality[]> {
  return request<RiskDataQuality[]>("/api/v1/risk/data-quality");
}
