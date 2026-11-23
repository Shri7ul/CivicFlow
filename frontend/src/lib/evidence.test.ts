import { describe, expect, it } from "vitest";

import {
  formatFileSize,
  MAX_EVIDENCE_FILE_BYTES,
  validateEvidenceFiles,
} from "@/lib/evidence";

function file(name: string, size: number, type: string) {
  return { name, size, type };
}

describe("evidence validation", () => {
  it("accepts allowed image types within limits", () => {
    expect(
      validateEvidenceFiles([
        file("a.jpg", 1024, "image/jpeg"),
        file("b.webp", MAX_EVIDENCE_FILE_BYTES, "image/webp"),
      ]),
    ).toBeNull();
  });

  it("rejects unsupported, empty, oversized, and excessive files", () => {
    expect(validateEvidenceFiles([])).toContain("Select");
    expect(validateEvidenceFiles([file("a.svg", 10, "image/svg+xml")])).toContain(
      "JPEG",
    );
    expect(validateEvidenceFiles([file("a.png", 0, "image/png")])).toContain(
      "empty",
    );
    expect(
      validateEvidenceFiles([
        file("a.png", MAX_EVIDENCE_FILE_BYTES + 1, "image/png"),
      ]),
    ).toContain("10 MB");
    expect(
      validateEvidenceFiles(
        Array.from({ length: 6 }, (_, index) =>
          file(`${index}.png`, 10, "image/png"),
        ),
      ),
    ).toContain("at most 5");
  });

  it("formats byte counts", () => {
    expect(formatFileSize(512)).toBe("512 B");
    expect(formatFileSize(1536)).toBe("1.5 KB");
    expect(formatFileSize(2 * 1024 * 1024)).toBe("2.0 MB");
  });
});
