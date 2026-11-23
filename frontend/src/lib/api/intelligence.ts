import type { ApiRequestOptions } from "@/lib/api/client";
import type { ApiRequester } from "@/lib/api/incidents";
import type {
  IncidentIntelligence,
  IncidentRelationship,
  InfrastructureAsset,
  RelationshipReviewInput,
} from "@/types/intelligence";

export function getIncidentIntelligence(
  request: ApiRequester,
  incidentId: string,
  options: Pick<ApiRequestOptions, "signal"> = {},
): Promise<IncidentIntelligence> {
  return request<IncidentIntelligence>(
    `/api/v1/incidents/${incidentId}/intelligence`,
    { signal: options.signal },
  );
}

export function listIncidentRelationships(
  request: ApiRequester,
  incidentId: string,
): Promise<IncidentRelationship[]> {
  return request<IncidentRelationship[]>(
    `/api/v1/incidents/${incidentId}/relationships`,
  );
}

export function reviewIncidentRelationship(
  request: ApiRequester,
  incidentId: string,
  input: RelationshipReviewInput,
): Promise<IncidentRelationship> {
  return request<IncidentRelationship>(
    `/api/v1/incidents/${incidentId}/relationships`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    },
  );
}

export function listInfrastructureAssets(
  request: ApiRequester,
): Promise<InfrastructureAsset[]> {
  return request<InfrastructureAsset[]>(
    "/api/v1/infrastructure/assets?limit=100",
  );
}
