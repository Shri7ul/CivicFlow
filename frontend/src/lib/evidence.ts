export const MAX_EVIDENCE_FILES = 5;
export const MAX_EVIDENCE_FILE_BYTES = 10 * 1024 * 1024;
export const ALLOWED_EVIDENCE_TYPES: readonly string[] = [
  "image/jpeg",
  "image/png",
  "image/webp",
];

export type EvidenceFileLike = Pick<File, "name" | "size" | "type">;

export function validateEvidenceFiles(
  files: readonly EvidenceFileLike[],
): string | null {
  if (files.length === 0) {
    return "Select at least one image.";
  }
  if (files.length > MAX_EVIDENCE_FILES) {
    return `Upload at most ${MAX_EVIDENCE_FILES} files at once.`;
  }
  for (const file of files) {
    if (!ALLOWED_EVIDENCE_TYPES.includes(file.type)) {
      return `${file.name} is not a JPEG, PNG, or WebP image.`;
    }
    if (file.size <= 0) {
      return `${file.name} is empty.`;
    }
    if (file.size > MAX_EVIDENCE_FILE_BYTES) {
      return `${file.name} is larger than 10 MB.`;
    }
  }
  return null;
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
