import { describe, expect, it } from "vitest";

import {
  allowedNextStatuses,
  formatCoordinates,
  statusLabels,
} from "@/lib/incidents";

describe("incident lifecycle helpers", () => {
  it("exposes the forward-only lifecycle", () => {
    expect(allowedNextStatuses("OPEN")).toEqual([
      "ACKNOWLEDGED",
      "IN_PROGRESS",
    ]);
    expect(allowedNextStatuses("ACKNOWLEDGED")).toEqual(["IN_PROGRESS"]);
    expect(allowedNextStatuses("IN_PROGRESS")).toEqual(["RESOLVED"]);
    expect(allowedNextStatuses("RESOLVED")).toEqual(["CLOSED"]);
    expect(allowedNextStatuses("CLOSED")).toEqual([]);
  });

  it("formats labels and coordinates", () => {
    expect(statusLabels.IN_PROGRESS).toBe("In progress");
    expect(formatCoordinates(23.8103, 90.4125)).toBe("23.81030, 90.41250");
  });
});
