import { describe, expect, it } from "vitest";

import {
  allowedNextStatuses,
  formatCoordinates,
  statusLabels,
  statusTones,
} from "@/lib/incidents";

describe("incident lifecycle helpers", () => {
  it("mirrors the backend workforce-aware state machine", () => {
    expect(allowedNextStatuses("OPEN")).toEqual([
      "ACKNOWLEDGED",
      "IN_PROGRESS",
      "VERIFIED",
    ]);
    expect(allowedNextStatuses("VERIFIED")).toEqual(["ASSIGNED", "OPEN"]);
    expect(allowedNextStatuses("ASSIGNED")).toEqual(["ACCEPTED", "VERIFIED"]);
    expect(allowedNextStatuses("ACCEPTED")).toEqual(["IN_PROGRESS", "ASSIGNED"]);
    expect(allowedNextStatuses("ACKNOWLEDGED")).toEqual(["IN_PROGRESS"]);
    expect(allowedNextStatuses("IN_PROGRESS")).toEqual([
      "RESOLVED",
      "COMPLETION_SUBMITTED",
      "ASSIGNED",
    ]);
    expect(allowedNextStatuses("COMPLETION_SUBMITTED")).toEqual([
      "VERIFIED_COMPLETED",
      "IN_PROGRESS",
      "ASSIGNED",
    ]);
    expect(allowedNextStatuses("VERIFIED_COMPLETED")).toEqual([
      "RESOLVED",
      "IN_PROGRESS",
    ]);
    expect(allowedNextStatuses("RESOLVED")).toEqual(["CLOSED"]);
    expect(allowedNextStatuses("CLOSED")).toEqual([]);
  });

  it("renders every workforce status with a label and tone", () => {
    const statuses = [
      "OPEN",
      "VERIFIED",
      "ASSIGNED",
      "ACCEPTED",
      "ACKNOWLEDGED",
      "IN_PROGRESS",
      "COMPLETION_SUBMITTED",
      "VERIFIED_COMPLETED",
      "RESOLVED",
      "CLOSED",
    ] as const;
    for (const status of statuses) {
      expect(statusLabels[status]).toBeTruthy();
      expect(statusTones[status]).toBeTruthy();
    }
  });

  it("formats labels and coordinates", () => {
    expect(statusLabels.IN_PROGRESS).toBe("In progress");
    expect(formatCoordinates(23.8103, 90.4125)).toBe("23.81030, 90.41250");
  });
});
