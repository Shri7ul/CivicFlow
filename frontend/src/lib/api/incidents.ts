import type { ApiRequestOptions } from "@/lib/api/client";
import type {
  Department,
  Incident,
  IncidentCreateInput,
  IncidentFilters,
  IncidentList,
  IncidentStatus,
  IncidentUpdateInput,
} from "@/types/incidents";

export type ApiRequester = <T>(
  path: string,
  options?: ApiRequestOptions,
) => Promise<T>;

const JSON_HEADERS = { "Content-Type": "application/json" };

export function buildIncidentQuery(filters: IncidentFilters = {}): string {
  const params = new URLSearchParams();
  const page = filters.page ?? 1;
  const pageSize = filters.pageSize ?? 20;
  params.set("page", String(page));
  params.set("page_size", String(pageSize));
  if (filters.status) params.set("status", filters.status);
  if (filters.category) params.set("category", filters.category);
  if (filters.severity) params.set("severity", filters.severity);
  if (filters.departmentId) params.set("department_id", filters.departmentId);
  if (filters.query?.trim()) params.set("q", filters.query.trim());
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
  return params.toString();
}

export function listIncidents(
  request: ApiRequester,
  filters: IncidentFilters = {},
  options: { signal?: AbortSignal } = {},
): Promise<IncidentList> {
  return request<IncidentList>(`/api/v1/incidents?${buildIncidentQuery(filters)}`, {
    signal: options.signal,
  });
}

export function getIncident(
  request: ApiRequester,
  incidentId: string,
): Promise<Incident> {
  return request<Incident>(`/api/v1/incidents/${incidentId}`);
}

export function createIncident(
  request: ApiRequester,
  input: IncidentCreateInput,
): Promise<Incident> {
  return request<Incident>("/api/v1/incidents", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify(input),
  });
}

export function updateIncident(
  request: ApiRequester,
  incidentId: string,
  input: IncidentUpdateInput,
): Promise<Incident> {
  return request<Incident>(`/api/v1/incidents/${incidentId}`, {
    method: "PATCH",
    headers: JSON_HEADERS,
    body: JSON.stringify(input),
  });
}

export function changeIncidentStatus(
  request: ApiRequester,
  incidentId: string,
  input: {
    status: IncidentStatus;
    department_id?: string | null;
    note?: string | null;
  },
): Promise<Incident> {
  return request<Incident>(`/api/v1/incidents/${incidentId}/status`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify(input),
  });
}

export function listDepartments(request: ApiRequester): Promise<Department[]> {
  return request<Department[]>("/api/v1/departments");
}
