import type { ApiRequester } from "@/lib/api/incidents";
import type { UploadProgress } from "@/lib/api/client";
import type { Evidence, EvidenceUrl } from "@/types/incidents";
import type {
  EvidenceSnapshot,
  EvidenceSnapshotList,
  EvidenceWorkspace,
} from "@/types/evidence";

export type UploadRequester = <T>(
  path: string,
  formData: FormData,
  onProgress?: UploadProgress,
) => Promise<T>;

export function uploadIncidentEvidence(
  request: UploadRequester,
  incidentId: string,
  files: File[],
  onProgress?: UploadProgress,
): Promise<Evidence[]> {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file, file.name);
  }
  return request<Evidence[]>(
    `/api/v1/incidents/${incidentId}/evidence`,
    formData,
    onProgress,
  );
}

export function listIncidentEvidence(
  request: ApiRequester,
  incidentId: string,
): Promise<Evidence[]> {
  return request<Evidence[]>(`/api/v1/incidents/${incidentId}/evidence`);
}

export function getEvidenceUrl(
  request: ApiRequester,
  incidentId: string,
  evidenceId: string,
): Promise<EvidenceUrl> {
  return request<EvidenceUrl>(
    `/api/v1/incidents/${incidentId}/evidence/${evidenceId}/url`,
  );
}

export function getEvidenceWorkspace(
  request: ApiRequester,
  options: { signal?: AbortSignal; includeContext?: boolean } = {},
): Promise<EvidenceWorkspace> {
  const includeContext = options.includeContext ?? true;
  return request<EvidenceWorkspace>(
    "/api/v1/governance/evidence/workspace?include_context=" +
      String(includeContext),
    { signal: options.signal },
  );
}

export function getEvidenceSnapshots(
  request: ApiRequester,
  options: { signal?: AbortSignal; limit?: number; offset?: number } = {},
): Promise<EvidenceSnapshotList> {
  const limit = options.limit ?? 25;
  const offset = options.offset ?? 0;
  return request<EvidenceSnapshotList>(
    "/api/v1/governance/evidence/snapshots?limit=" +
      limit +
      "&offset=" +
      offset,
    { signal: options.signal },
  );
}

export function getEvidenceSnapshot(
  request: ApiRequester,
  snapshotId: string,
  options: { signal?: AbortSignal } = {},
): Promise<EvidenceSnapshot> {
  return request<EvidenceSnapshot>(
    "/api/v1/governance/evidence/snapshots/" + snapshotId,
    { signal: options.signal },
  );
}
