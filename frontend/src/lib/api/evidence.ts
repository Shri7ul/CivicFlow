import type { ApiRequester } from "@/lib/api/incidents";
import type { UploadProgress } from "@/lib/api/client";
import type { Evidence, EvidenceUrl } from "@/types/incidents";

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
