import type { ApiRequester } from "@/lib/api/incidents";
import type {
  AlertRecord,
  AlertRuleCreateInput,
  Dashboard,
  DataSourceRecord,
  NotificationRecord,
  QualityItem,
  ReviewDecision,
  ReviewRecord,
  SourceCreateInput,
} from "@/types/operations";

const JSON_HEADERS = { "Content-Type": "application/json" };

export function getOperationsDashboard(request: ApiRequester): Promise<Dashboard> {
  return request<Dashboard>("/api/v1/operations/dashboard");
}

export function listDataSources(request: ApiRequester): Promise<DataSourceRecord[]> {
  return request<DataSourceRecord[]>("/api/v1/operations/sources");
}

export function createDataSource(
  request: ApiRequester,
  input: SourceCreateInput,
): Promise<DataSourceRecord> {
  return request<DataSourceRecord>("/api/v1/operations/sources", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify(input),
  });
}

export function listDataQuality(request: ApiRequester): Promise<QualityItem[]> {
  return request<QualityItem[]>("/api/v1/operations/quality");
}

export function createAlertRule(
  request: ApiRequester,
  input: AlertRuleCreateInput,
): Promise<unknown> {
  return request("/api/v1/operations/alerts/rules", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify(input),
  });
}

export function evaluateAlerts(request: ApiRequester): Promise<AlertRecord[]> {
  return request<AlertRecord[]>("/api/v1/operations/alerts/evaluate", {
    method: "POST",
  });
}

export function listAlerts(request: ApiRequester): Promise<AlertRecord[]> {
  return request<AlertRecord[]>("/api/v1/operations/alerts");
}

export function acknowledgeAlert(
  request: ApiRequester,
  alertId: string,
): Promise<AlertRecord> {
  return request<AlertRecord>(`/api/v1/operations/alerts/${encodeURIComponent(alertId)}/acknowledge`, {
    method: "POST",
  });
}

export function resolveAlert(
  request: ApiRequester,
  alertId: string,
): Promise<AlertRecord> {
  return request<AlertRecord>(`/api/v1/operations/alerts/${encodeURIComponent(alertId)}/resolve`, {
    method: "POST",
  });
}

export function listNotifications(request: ApiRequester): Promise<NotificationRecord[]> {
  return request<NotificationRecord[]>("/api/v1/operations/notifications");
}

export function markNotificationRead(
  request: ApiRequester,
  notificationId: string,
): Promise<NotificationRecord> {
  return request<NotificationRecord>(
    `/api/v1/operations/notifications/${encodeURIComponent(notificationId)}/read`,
    { method: "POST" },
  );
}

export function listPendingReviews(request: ApiRequester): Promise<ReviewRecord[]> {
  return request<ReviewRecord[]>("/api/v1/decisions/reviews/pending");
}

export function decideReview(
  request: ApiRequester,
  reviewId: string,
  decision: ReviewDecision,
  comment?: string,
): Promise<ReviewRecord> {
  return request<ReviewRecord>(`/api/v1/decisions/reviews/${encodeURIComponent(reviewId)}/decision`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ decision, comment: comment ?? null }),
  });
}

export function listScenarioReviews(
  request: ApiRequester,
  scenarioId: string,
): Promise<ReviewRecord[]> {
  return request<ReviewRecord[]>(
    `/api/v1/decisions/scenarios/${encodeURIComponent(scenarioId)}/reviews`,
  );
}

export function submitScenarioReview(
  request: ApiRequester,
  scenarioId: string,
  simulationId: string,
  comment?: string,
): Promise<ReviewRecord> {
  return request<ReviewRecord>(
    `/api/v1/decisions/scenarios/${encodeURIComponent(scenarioId)}/reviews`,
    {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify({
        simulation_id: simulationId,
        title: "Plan review",
        comment: comment ?? null,
      }),
    },
  );
}
