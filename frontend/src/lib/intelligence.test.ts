import { describe, expect, it } from "vitest";

import {
  candidateLabel,
  confidenceTone,
  formatConfidence,
  formatDistance,
  formatTimeDelta,
  impactTypeLabels,
  relationshipStatusLabels,
} from "@/lib/intelligence";

describe("intelligence presentation helpers", () => {
  it("formats confidence, distance, and time without overstating precision", () => {
    expect(formatConfidence(0.826)).toBe("83%");
    expect(formatDistance(84.4)).toBe("84 m");
    expect(formatDistance(1500)).toBe("1.5 km");
    expect(formatTimeDelta(90)).toBe("2 min");
    expect(formatTimeDelta(5400)).toBe("1.5 h");
    expect(formatTimeDelta(172800)).toBe("2.0 d");
  });

  it("labels suggestions with confidence, distance, and timing", () => {
    expect(
      candidateLabel({
        incident: {
          id: "incident-2",
          title: "Blocked drain",
          category: "DRAINAGE",
          severity: "HIGH",
          status: "OPEN",
        },
        distance_m: 48,
        time_delta_seconds: 720,
        text_similarity: 0.8,
        confidence: 0.79,
        reasons: [],
        signals: [],
      }),
    ).toBe("79% confidence · 48 m away · 12 min apart");
  });

  it("uses a different tone above the stronger candidate threshold", () => {
    expect(confidenceTone(0.8)).toContain("amber");
    expect(confidenceTone(0.6)).toContain("sky");
    expect(confidenceTone(0.4)).toContain("slate");
  });

  it("makes facts versus inferences explicit in labels", () => {
    expect(impactTypeLabels.GEOSPATIAL_ASSOCIATION).toBe(
      "Spatial association",
    );
    expect(impactTypeLabels.INFERRED_POTENTIAL).toBe("Inferred potential");
    expect(relationshipStatusLabels.CONFIRMED).toBe("Confirmed by staff");
  });
});
