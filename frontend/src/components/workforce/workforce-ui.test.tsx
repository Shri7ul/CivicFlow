import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import {
  EmptyState,
  ErrorNotice,
  LoadingBlock,
  StatusPill,
  applicationStatusLabel,
  applicationTone,
  assignmentStatusLabel,
  assignmentTone,
  formatDateTime,
  shortId,
  workerStatusLabel,
} from "./workforce-ui";

describe("workforce presentation", () => {
  it("labels every application status without leaking raw enum values", () => {
    const statuses = [
      "PENDING",
      "UNDER_REVIEW",
      "APPROVED",
      "REJECTED",
      "ADDITIONAL_INFORMATION_REQUIRED",
      "SUSPENDED",
    ] as const;
    for (const status of statuses) {
      expect(applicationStatusLabel[status]).toBeTruthy();
      expect(applicationStatusLabel[status]).not.toBe(status);
    }
    expect(applicationTone("APPROVED")).toBe("good");
    expect(applicationTone("PENDING")).toBe("info");
    expect(applicationTone("ADDITIONAL_INFORMATION_REQUIRED")).toBe("warn");
    expect(applicationTone("REJECTED")).toBe("bad");
  });

  it("labels every assignment and worker status", () => {
    const statuses = [
      "OFFERED",
      "ACCEPTED",
      "DECLINED",
      "IN_PROGRESS",
      "COMPLETION_SUBMITTED",
      "VERIFIED_COMPLETED",
      "CANCELLED",
    ] as const;
    for (const status of statuses) {
      expect(assignmentStatusLabel[status]).toBeTruthy();
      expect(assignmentStatusLabel[status]).not.toBe(status);
    }
    expect(assignmentTone("VERIFIED_COMPLETED")).toBe("good");
    expect(assignmentTone("OFFERED")).toBe("warn");
    expect(assignmentTone("CANCELLED")).toBe("bad");
    expect(workerStatusLabel.ACTIVE).toBe("Active");
    expect(workerStatusLabel.SUSPENDED).toBe("Suspended");
  });

  it("renders explicit status, loading, empty, and error states", () => {
    const onRetry = vi.fn();
    const markup = renderToStaticMarkup(
      <div>
        <StatusPill label="Approved" tone="good" />
        <LoadingBlock label="Loading assignments…" />
        <EmptyState message="No assignments yet." />
        <ErrorNotice message="API unavailable" onRetry={onRetry} />
      </div>,
    );
    expect(markup).toContain("Approved");
    expect(markup).toContain("Loading assignments…");
    expect(markup).toContain("No assignments yet.");
    expect(markup).toContain("API unavailable");
    expect(markup).toContain("Retry");
  });

  it("renders unknown timestamps as a dash and shortens identifiers", () => {
    expect(formatDateTime(null)).toBe("—");
    expect(formatDateTime("not-a-date")).toBe("—");
    expect(shortId("12345678-abcd-1234-abcd-123456789012")).toBe("12345678");
  });
});
