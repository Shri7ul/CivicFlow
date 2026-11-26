import type { ApiRequestOptions } from "@/lib/api/client";
import type { ApiRequester } from "@/lib/api/incidents";
import type {
  AdminOverview,
  ApplicationPayload,
  Assignment,
  AssignmentStatus,
  Candidate,
  ListResponse,
  WorkerApplication,
  WorkerApplicationStatus,
  WorkerProfile,
  WorkerStatus,
  WorkforceEventRecord,
  WorkforceNotification,
} from "@/types/workforce";

const JSON_HEADERS = { "Content-Type": "application/json" };

function query(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const encoded = search.toString();
  return encoded ? `?${encoded}` : "";
}

export function submitWorkerApplication(
  request: ApiRequester,
  payload: ApplicationPayload,
): Promise<WorkerApplication> {
  return request("/api/v1/workforce/applications", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify(payload),
  });
}

export function getMyApplication(
  request: ApiRequester,
): Promise<WorkerApplication> {
  return request("/api/v1/workforce/applications/mine");
}

export function getMyWorkerProfile(
  request: ApiRequester,
): Promise<WorkerProfile> {
  return request("/api/v1/workforce/workers/me");
}

export function listWorkerApplications(
  request: ApiRequester,
  filters: {
    status?: WorkerApplicationStatus;
    specialization?: string;
    departmentId?: string;
    limit?: number;
    offset?: number;
  } = {},
): Promise<ListResponse<WorkerApplication>> {
  return request(
    `/api/v1/workforce/applications${query({
      status: filters.status,
      specialization: filters.specialization,
      department_id: filters.departmentId,
      limit: filters.limit,
      offset: filters.offset,
    })}`,
  );
}

export function reviewWorkerApplication(
  request: ApiRequester,
  applicationId: string,
  decision: "APPROVE" | "REJECT" | "REQUEST_INFO" | "UNDER_REVIEW",
  note?: string,
): Promise<WorkerApplication> {
  return request(`/api/v1/workforce/applications/${applicationId}/review`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ decision, ...(note ? { note } : {}) }),
  });
}

export function listWorkers(
  request: ApiRequester,
  filters: {
    status?: WorkerStatus;
    specialization?: string;
    departmentId?: string;
    limit?: number;
    offset?: number;
  } = {},
): Promise<ListResponse<WorkerProfile>> {
  return request(
    `/api/v1/workforce/workers${query({
      status: filters.status,
      specialization: filters.specialization,
      department_id: filters.departmentId,
      limit: filters.limit,
      offset: filters.offset,
    })}`,
  );
}

export function setWorkerStatus(
  request: ApiRequester,
  workerProfileId: string,
  action: "suspend" | "reactivate",
  note?: string,
): Promise<WorkerProfile> {
  const body = action === "suspend" ? JSON.stringify({ note }) : undefined;
  return request(`/api/v1/workforce/workers/${workerProfileId}/${action}`, {
    method: "POST",
    headers: body ? JSON_HEADERS : undefined,
    body,
  });
}

export function getAdminOverview(request: ApiRequester): Promise<AdminOverview> {
  return request("/api/v1/workforce/admin/overview");
}

export function listCandidates(
  request: ApiRequester,
  incidentId: string,
): Promise<{ incident_id: string; items: Candidate[] }> {
  return request(
    `/api/v1/workforce/assignments/candidates${query({ incident_id: incidentId })}`,
  );
}

export function assignIncident(
  request: ApiRequester,
  input: { incidentId: string; workerProfileId: string; note?: string },
): Promise<Assignment> {
  return request("/api/v1/workforce/assignments", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({
      incident_id: input.incidentId,
      worker_profile_id: input.workerProfileId,
      ...(input.note ? { note: input.note } : {}),
    }),
  });
}

export function listAssignments(
  request: ApiRequester,
  filters: {
    incidentId?: string;
    status?: AssignmentStatus;
    limit?: number;
    offset?: number;
  } = {},
): Promise<ListResponse<Assignment>> {
  return request(
    `/api/v1/workforce/assignments${query({
      incident_id: filters.incidentId,
      status: filters.status,
      limit: filters.limit,
      offset: filters.offset,
    })}`,
  );
}

export function assignmentAction(
  request: ApiRequester,
  assignmentId: string,
  action: "accept" | "decline" | "start" | "cancel",
  note?: string,
): Promise<Assignment> {
  return request(`/api/v1/workforce/assignments/${assignmentId}/${action}`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ note: note ?? null }),
  });
}

export function recordProgress(
  request: ApiRequester,
  assignmentId: string,
  note: string,
  progressPercent: number,
): Promise<Assignment> {
  return request(`/api/v1/workforce/assignments/${assignmentId}/progress`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ note, progress_percent: progressPercent }),
  });
}

export function submitCompletion(
  request: ApiRequester,
  assignmentId: string,
  note: string,
  evidenceNote?: string,
): Promise<Assignment> {
  return request(`/api/v1/workforce/assignments/${assignmentId}/complete`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({
      note,
      ...(evidenceNote ? { evidence_note: evidenceNote } : {}),
    }),
  });
}

export function verifyCompletion(
  request: ApiRequester,
  assignmentId: string,
  approve: boolean,
  note?: string,
): Promise<Assignment> {
  return request(`/api/v1/workforce/assignments/${assignmentId}/verify`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ approve, ...(note ? { note } : {}) }),
  });
}

export function listAuditEvents(
  request: ApiRequester,
  entityType?: string,
): Promise<ListResponse<WorkforceEventRecord>> {
  return request(
    `/api/v1/workforce/events${query({ entity_type: entityType, limit: 100 })}`,
  );
}

export function listNotifications(
  request: ApiRequester,
): Promise<{ items: WorkforceNotification[]; total: number; unread: number }> {
  return request("/api/v1/workforce/notifications");
}

export function markNotificationRead(
  request: ApiRequester,
  notificationId: string,
): Promise<WorkforceNotification> {
  return request(`/api/v1/workforce/notifications/${notificationId}/read`, {
    method: "POST",
  });
}

export type { ApiRequestOptions };
